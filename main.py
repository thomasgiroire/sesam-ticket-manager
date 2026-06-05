#!/usr/bin/env python3
"""
main.py – CLI de gestion des tickets Portail IRIS (SESAM-Vitale)
================================================================
Usage :
  python main.py list                         # Liste tous les tickets ouverts
  python main.py list --closed                # Inclure les tickets clos
  python main.py list --status "En cours"     # Filtrer par statut
  python main.py list --type Incident         # Filtrer par type
  python main.py show <CODE_OU_ID>            # Détail d'un ticket
  python main.py messages <CODE_OU_ID>        # Messages d'un ticket
  python main.py reply <CODE_OU_ID>           # Répondre à un ticket
  python main.py sync                         # Détecter les nouveaux tickets
  python main.py sync --all                   # Traiter tous les tickets
  python main.py sync --dry-run               # Simuler sans rien créer

Notes :
  - La référence (code) est au format XX-YYY-NNNNNN (ex: 26-083-026025)
  - L'ID interne est hexadécimal (ex: 00294000001e8cbd)
  - Les deux formats sont acceptés par les commandes show/messages/reply
"""

import getpass
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from dotenv import load_dotenv

load_dotenv()

PORTAL_BASE_URL = os.getenv(
    "PORTAL_BASE_URL",
    "https://portail-support.sesam-vitale.fr/gsvextranet",
)

from portal import PortalClient, Ticket
from exceptions import AuthError, APIError, ConfigError
from utils import setup_logging, get_logger, format_ticket_export


def _read_version() -> str:
    try:
        return (Path(__file__).parent / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


def _emit_error_json(exc: Exception) -> None:
    """Imprime une erreur structurée sur stdout pour les agents.

    Pour les erreurs d'auth/config, ajoute `action: "run_login"` afin que
    l'agent puisse demander à l'utilisateur de lancer `sesam login`.
    """
    payload: dict = {"ok": False, "error": str(exc)}
    if isinstance(exc, (AuthError, ConfigError)):
        payload["action"] = "run_login"
        payload["hint"] = "Lancez `sesam login` dans un terminal pour vous (re)connecter."
    print(json.dumps(payload, ensure_ascii=False))


def _print_error_human(exc: Exception) -> None:
    """Affiche une erreur sur la console et suggère `sesam login` si pertinent."""
    console.print(f"[red]❌ {exc}[/red]")
    if isinstance(exc, (AuthError, ConfigError)):
        console.print("[dim]→ Lancez [cyan]sesam login[/cyan] pour vous (re)connecter.[/dim]")

logger = get_logger(__name__)
console = Console()


# ─── Statuts et styles ──────────────────────────────────────────────────────

STATUS_STYLE = {
    "nouveau":          "bold green",
    "en cours":         "bold blue",
    "en attente":       "bold yellow",
    "expertise externe":"bold magenta",
    "en expertise":     "bold magenta",
    "résolu":           "dim green",
    "résolu (clôturé)": "dim",
    "clôturé":          "dim",
    "fermé":            "dim",
}

PRIORITY_STYLE = {
    "normal":   "white",
    "haute":    "bold yellow",
    "urgente":  "bold orange3",
    "critique": "bold red",
}

def _status_style(status: str) -> str:
    """Retourne le style Rich correspondant au statut du ticket."""
    return STATUS_STYLE.get(status.lower(), "white")

def _priority_style(priority: str) -> str:
    """Retourne le style Rich correspondant à la priorité du ticket."""
    return PRIORITY_STYLE.get(priority.lower(), "white")


_MSG_LABEL = {
    "inextranet": "Message éditeur",
    "exextranet": "Message GIE SESAM-Vitale",
}

_MSG_LABEL_BY_API_LABEL = {
    "extranet sortant": "Réponse du GIE",
    "extranet entrant": "Message éditeur",
}

def _msg_label(msg) -> str:
    """Retourne le label lisible d'un message selon son type_code."""
    by_code = _MSG_LABEL.get(msg.type_code.lower())
    if by_code:
        return by_code
    return _MSG_LABEL_BY_API_LABEL.get((msg.type_label or "").lower(), msg.type_label or msg.type_code)

def _msg_is_inbound(msg) -> bool:
    """Vrai si le message est envoyé par l'éditeur (entrant pour le GIE)."""
    return msg.type_code.lower() == "inextranet"

def _age_style(dt_str: str) -> str:
    """Retourne le style Rich selon l'ancienneté du ticket."""
    if not dt_str:
        return "dim"
    try:
        created = datetime.fromisoformat(dt_str[:19]).replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days > 30:
            return "red"
        if age_days > 7:
            return "yellow"
        return "dim"
    except (ValueError, TypeError):
        return "dim"

def _resolve_id(portal: PortalClient, code_or_id: str) -> str:
    """
    Résout une référence ou un ID hexadécimal en ID hexadécimal interne.
    Exemples :
      "26-083-026025" → tous statuts confondus → retourne l'id hex
      "00294000001e8cbd" → retourné directement
    """
    if "-" not in code_or_id or len(code_or_id) >= 20:
        return code_or_id  # C'est déjà un ID hex

    with console.status(f"Recherche du ticket {code_or_id}..."):
        ticket = portal.get_ticket_by_code(code_or_id)

    if ticket is None:
        console.print(f"[red]❌ Ticket {code_or_id} introuvable.[/red]")
        sys.exit(1)

    return ticket.id


# ─── Groupe CLI ──────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version=_read_version(), prog_name="sesam")
@click.option("--verbose", "-v", is_flag=True, help="Activer le mode debug (logging détaillé)")
def cli(verbose):
    """Portail IRIS SESAM-Vitale"""
    log_level = "DEBUG" if verbose else "WARNING"
    setup_logging(log_level)


# ── list ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--open-only", is_flag=True, help="Afficher uniquement les tickets ouverts")
@click.option("--status", "-s", default=None, help="Filtrer par statut (ex: 'En cours', 'En attente')")
@click.option("--type", "ticket_type", default=None, type=click.Choice(["Incident", "Demande"], case_sensitive=False), help="Filtrer par type")
@click.option("--limit", "-n", default=50, show_default=True, help="Nombre de tickets par page")
@click.option("--page", "-p", default=1, show_default=True, help="Numéro de page")
@click.option("--fetch-all", "fetch_all", is_flag=True, help="Récupérer toutes les pages")
@click.option("--json-output", "json_out", is_flag=True, help="Sortie JSON brut")
def list(open_only, status, ticket_type, limit, page, fetch_all, json_out):
    """Lister les tickets du Portail IRIS.

    \b
    Exemples :
      sesam list
      sesam list --open-only
      sesam list --status "En attente"
      sesam list --type Incident --page 2
      sesam list --fetch-all --json-output
    """
    portal = PortalClient()

    is_first_run = not portal.state.known_tickets
    if is_first_run:
        fetch_all = True
        console.print("[dim]Première exécution détectée — récupération de tous les tickets.[/dim]")

    with console.status("Récupération des tickets..."):
        try:
            tickets = portal.list_tickets(
                include_closed=not open_only,
                limit=limit,
                page=page,
                fetch_all=fetch_all,
            )
        except AuthError as e:
            _print_error_human(e)
            sys.exit(1)
        except APIError as e:
            console.print(f"[red]❌ Erreur API :[/red] {e}")
            sys.exit(1)

    if is_first_run:
        portal.state.update_known_tickets(tickets)

    # Filtres locaux
    if status:
        tickets = [t for t in tickets if status.lower() in t.status.lower()]
    if ticket_type:
        tickets = [t for t in tickets if ticket_type.lower() in t.type_ticket.lower()]

    if json_out:
        print(json.dumps([t.to_dict() for t in tickets], indent=2, ensure_ascii=False))
        return

    if not tickets:
        console.print("[yellow]Aucun ticket trouvé.[/yellow]")
        return

    table = Table(
        title=f"Tickets Portail IRIS ({len(tickets)})",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Référence",    style="bold", width=16)
    table.add_column("Type",         width=10)
    table.add_column("Statut",       width=18)
    table.add_column("Priorité",     width=10)
    table.add_column("Titre",        max_width=50)
    table.add_column("Demandeur",    max_width=20)
    table.add_column("Mis à jour",   width=17)
    table.add_column("Créé le",      width=17)

    for t in tickets:
        st_style = _status_style(t.status)
        pr_style = _priority_style(t.priority)
        age_style = _age_style(t.created_at) if not t.closed_at else "dim"
        table.add_row(
            t.code,
            t.type_ticket,
            Text(t.status, style=st_style),
            Text(t.priority, style=pr_style),
            t.titre[:50],
            t.author or "—",
            (t.updated_at[:16] if t.updated_at else "—").replace("T", " "),
            Text((t.created_at[:16] if t.created_at else "—").replace("T", " "), style=age_style),
        )

    console.print(table)

    nav_parts = [f"Page {page}", f"{len(tickets)} ticket(s)"]
    if len(tickets) == limit:
        nav_parts.append(f"[cyan]--page {page + 1}[/cyan] → page suivante")
    if page > 1:
        nav_parts.append(f"[cyan]--page {page - 1}[/cyan] → page précédente")
    if not fetch_all:
        nav_parts.append("[cyan]--fetch-all[/cyan] → tout récupérer")
    console.print("  ".join(f"[dim]{p}[/dim]" if i == 0 else p for i, p in enumerate(nav_parts)))


# ── show ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--json-output", "json_out", is_flag=True)
def show(code_or_id, json_out):
    """Afficher le détail d'un ticket.

    \b
    Exemples :
      sesam show 26-083-026025
      sesam show 26-083-026025 --refresh
      sesam show 26-083-026025 --json-output
    """
    portal = PortalClient()
    ticket_id = _resolve_id(portal, code_or_id)

    with console.status(f"Chargement du ticket {code_or_id}..."):
        try:
            ticket = portal.get_ticket(ticket_id)
        except (AuthError, APIError, ConfigError) as e:
            _print_error_human(e)
            sys.exit(1)

    if json_out:
        print(json.dumps(ticket.to_dict(), indent=2, ensure_ascii=False))
        return

    st_style = _status_style(ticket.status)
    pr_style = _priority_style(ticket.priority)

    console.print(Panel(
        f"[bold]{ticket.titre}[/bold]\n\n"
        f"  Référence  : [bold yellow]{ticket.code}[/bold yellow]\n"
        f"  Type       : {ticket.type_ticket}\n"
        f"  Statut     : [{st_style}]{ticket.status}[/{st_style}]\n"
        f"  Priorité   : [{pr_style}]{ticket.priority}[/{pr_style}]\n"
        f"  Service    : {ticket.service or '—'}\n"
        f"  Demandeur  : {ticket.author or '—'}\n"
        f"  Créé le    : {ticket.created_at[:16].replace('T',' ') if ticket.created_at else '—'}\n"
        f"  Mis à jour : {ticket.updated_at[:16].replace('T',' ') if ticket.updated_at else '—'}"
        + (f"\n  Clos le    : {ticket.closed_at[:16].replace('T',' ')}" if ticket.closed_at else ""),
        title=f"Ticket #{ticket.code}",
        border_style="cyan",
    ))

    if ticket.description:
        console.print(Panel(
            ticket.description[:1500] + ("…" if len(ticket.description) > 1500 else ""),
            title="Description",
            border_style="dim",
        ))

    if ticket.messages:
        console.print(f"\n[bold cyan]💬 Derniers messages ({len(ticket.messages)})[/bold cyan]")
        for msg in ticket.messages[-3:]:  # Afficher les 3 derniers
            console.print(Panel(
                msg.body[:500] + ("…" if len(msg.body) > 500 else ""),
                title=f"{_msg_label(msg)} — {msg.created_at[:16].replace('T',' ') if msg.created_at else ''}",
                border_style="blue" if _msg_is_inbound(msg) else "dim",
            ))


# ── messages ──────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json-output", "json_out", is_flag=True)
def messages(code_or_id, limit, json_out):
    """Afficher les messages d'un ticket.

    \b
    Exemples :
      sesam messages 26-083-026025
      sesam messages 26-083-026025 --limit 50
      sesam messages 26-083-026025 --json-output
    """
    portal = PortalClient()
    ticket_id = _resolve_id(portal, code_or_id)

    with console.status("Chargement des messages..."):
        try:
            msgs = portal.get_messages(ticket_id, limit=limit)
        except (AuthError, APIError, ConfigError) as e:
            _print_error_human(e)
            sys.exit(1)

    if json_out:
        print(json.dumps([vars(m) for m in msgs], indent=2, ensure_ascii=False))
        return

    if not msgs:
        console.print("[yellow]Aucun message sur ce ticket.[/yellow]")
        return

    console.print(f"\n[bold cyan]💬 {len(msgs)} message(s) — Ticket {code_or_id}[/bold cyan]\n")
    for msg in msgs:
        has_attach = f" 📎 {len(msg.attachments)} pièce(s)" if msg.attachments else ""
        console.print(Panel(
            msg.body or "[italic dim](pas de contenu)[/italic dim]",
            title=f"[bold]{_msg_label(msg)}[/bold] — {msg.created_at[:16].replace('T',' ') if msg.created_at else ''}{has_attach}",
            title_align="left",
            border_style="blue" if _msg_is_inbound(msg) else "dim",
        ))


# ── reply ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--title", "-t", default=None, help="Titre du message")
@click.option("--message", "-m", default=None, help="Corps du message")
@click.option("--yes", "-y", "assume_yes", is_flag=True, help="Ne pas demander confirmation (mode non-interactif)")
@click.option("--json-output", "json_out", is_flag=True, help="Sortie JSON brut (implique --yes)")
def reply(code_or_id, title, message, assume_yes, json_out):
    """Répondre à un ticket (ajouter un message).

    \b
    Exemples :
      sesam reply 26-083-026025
      sesam reply 26-083-026025 --title "Suivi" --message "Bonjour..."
      sesam reply 26-083-026025 --title "Suivi" --message "..." --yes
      sesam reply 26-083-026025 --title "Suivi" --message "..." --json-output
    """
    non_interactive = assume_yes or json_out

    if not title:
        if non_interactive:
            console.print("[red]❌ --title requis en mode non-interactif[/red]")
            sys.exit(2)
        title = click.prompt("📝 Titre du message")
    if not message:
        if non_interactive:
            console.print("[red]❌ --message requis en mode non-interactif[/red]")
            sys.exit(2)
        message = click.prompt("✉️  Votre message")

    if not message.strip():
        console.print("[yellow]Message vide, annulé.[/yellow]")
        sys.exit(2)

    if not non_interactive:
        console.print(f"\n[bold]Récapitulatif[/bold]")
        console.print(f"  Ticket  : {code_or_id}")
        console.print(f"  Titre   : {title}")
        console.print(f"  Message : {message[:80]}{'…' if len(message) > 80 else ''}")

        if not click.confirm("\nEnvoyer ce message ?", default=True):
            console.print("[yellow]Annulé.[/yellow]")
            return

    portal = PortalClient()
    ticket_id = _resolve_id(portal, code_or_id)

    with console.status("Envoi du message..."):
        try:
            msg = portal.add_message(ticket_id, title=title, body=message)
        except (AuthError, APIError, ConfigError) as e:
            if json_out:
                _emit_error_json(e)
            else:
                _print_error_human(e)
            sys.exit(1)

    if json_out:
        print(json.dumps({"ok": True, "message_id": msg.id, "ticket": code_or_id}, ensure_ascii=False))
    else:
        console.print(f"[green]✅ Message envoyé[/green] (ID: {msg.id or 'N/A'})")


# ── export ────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown", show_default=True, help="Format de sortie")
def export(code_or_id, fmt):
    """Exporter un ticket en format structuré.

    \b
    Exemples :
      sesam export 26-083-026025
      sesam export 26-083-026025 --format json
    """
    portal = PortalClient()
    ticket_id = _resolve_id(portal, code_or_id)

    with console.status(f"Chargement du ticket {code_or_id}..."):
        try:
            ticket = portal.get_ticket(ticket_id)
        except (AuthError, APIError, ConfigError) as e:
            _print_error_human(e)
            sys.exit(1)

    click.echo(format_ticket_export(ticket, fmt))


# ── sync ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--all", "sync_all", is_flag=True, help="Tous les tickets (pas seulement les nouveautés)")
@click.option("--closed", is_flag=True, help="Inclure les tickets clos")
@click.option("--dry-run",  is_flag=True, help="Simuler sans rien marquer")
@click.option("--json-output", "json_out", is_flag=True, help="Sortie JSON brut")
def sync(sync_all, closed, dry_run, json_out):
    """Synchroniser les tickets avec le portail.

    \b
    Exemples :
      sesam sync
      sesam sync --all
      sesam sync --dry-run
      sesam sync --json-output
    """
    portal = PortalClient()

    if dry_run and not json_out:
        console.print("[yellow]⚠ Mode DRY-RUN — simulation uniquement[/yellow]")

    # 1. Récupérer les tickets
    try:
        if json_out:
            all_tickets = portal.list_tickets(include_closed=True, limit=50, fetch_all=True)
        else:
            with console.status("Récupération des tickets..."):
                all_tickets = portal.list_tickets(include_closed=True, limit=50, fetch_all=True)
    except (AuthError, APIError, ConfigError) as e:
        if json_out:
            _emit_error_json(e)
        else:
            _print_error_human(e)
        sys.exit(1)

    if not json_out:
        console.print(f"  → {len(all_tickets)} ticket(s) récupéré(s)")

    # 2. Filtrer nouveaux/modifiés
    if sync_all:
        to_sync = all_tickets
        if not json_out:
            console.print("  → Traitement de tous les tickets")
    else:
        to_sync = portal.get_new_or_updated(all_tickets)
        if not json_out:
            console.print(f"  → {len(to_sync)} nouveau(x)/modifié(s) depuis la dernière synchro")

    if not to_sync:
        if json_out:
            print(json.dumps({"ok": True, "synced": 0, "dry_run": dry_run, "tickets": []}, ensure_ascii=False))
        else:
            console.print("[green]✅ Tout est à jour, rien à synchroniser.[/green]")
        return

    if json_out:
        if not dry_run:
            portal.mark_synced(to_sync)
        print(json.dumps({
            "ok": True,
            "synced": 0 if dry_run else len(to_sync),
            "dry_run": dry_run,
            "tickets": [t.to_dict() for t in to_sync],
        }, ensure_ascii=False))
        return

    # 3. Tableau récap (mode interactif)
    table = Table(box=box.SIMPLE, header_style="bold cyan")
    table.add_column("Référence", width=16)
    table.add_column("Statut",    width=18)
    table.add_column("Titre",     max_width=55)
    for t in to_sync:
        table.add_row(t.code, t.status, t.titre[:55])
    console.print(table)

    if dry_run:
        console.print("[yellow]→ DRY-RUN : aucune action effectuée.[/yellow]")
        return

    # 4. Marquer comme synchronisés
    portal.mark_synced(to_sync)

    console.print(f"\n[green]✅ {len(to_sync)} ticket(s) marqué(s) comme synchronisés.[/green]")


# ── status ────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--json-output", "json_out", is_flag=True, help="Sortie JSON brut")
def status(json_out):
    """Vérifier la connexion et l'état du compte.

    \b
    Exemples :
      sesam status
      sesam status --json-output
    """
    portal = PortalClient()

    try:
        if json_out:
            account = portal.get_account()
            tickets = portal.list_tickets(limit=100)
        else:
            with console.status("Connexion au portail IRIS..."):
                account = portal.get_account()
            with console.status("Comptage des tickets..."):
                tickets = portal.list_tickets(limit=100)
    except (AuthError, APIError, ConfigError) as e:
        if json_out:
            _emit_error_json(e)
        else:
            _print_error_human(e)
        sys.exit(1)

    by_status: dict[str, int] = {}
    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1

    if json_out:
        print(json.dumps({
            "ok": True,
            "account": {
                "email": account.get("email"),
                "status": account.get("status", {}).get("label"),
                "last_login": account.get("lastLogin"),
            },
            "open_tickets": len(tickets),
            "by_status": by_status,
        }, ensure_ascii=False))
        return

    console.print("[green]✅ Connexion réussie[/green]")
    console.print(f"  Email    : {account.get('email', '—')}")
    console.print(f"  Statut   : {account.get('status', {}).get('label', '—')}")
    console.print(f"  Dernière connexion : {account.get('lastLogin', '—')}")

    console.print(f"\n  [bold]Tickets ouverts : {len(tickets)}[/bold]")
    for st, count in sorted(by_status.items(), key=lambda x: -x[1]):
        style = _status_style(st)
        console.print(f"    [{style}]{st}[/{style}] : {count}")


# ── login / logout ────────────────────────────────────────────────────────

def _resolve_env_path() -> Path:
    """Localise le fichier .env utilisé par l'application.

    Priorité : SESAM_HOME/run/.env, ~/.sesam/home → <home>/run/.env, sinon
    ./run/.env relatif au script.
    """
    sesam_home = os.getenv("SESAM_HOME")
    if sesam_home:
        p = Path(sesam_home) / "run" / ".env"
        if p.parent.exists():
            return p

    home_marker = Path.home() / ".sesam" / "home"
    if home_marker.exists():
        h = home_marker.read_text(encoding="utf-8").strip()
        if h:
            p = Path(h) / "run" / ".env"
            if p.parent.exists():
                return p

    return Path(__file__).resolve().parent / "run" / ".env"


def _resolve_state_path() -> Path:
    """Localise le fichier .sesam_state.json en se basant sur STATE_FILE."""
    state_file = os.getenv("STATE_FILE", ".sesam_state.json")
    p = Path(state_file)
    if p.is_absolute():
        return p
    # Relatif au répertoire du projet (parent du .env)
    return _resolve_env_path().parent.parent / state_file


def _write_env_var(env_path: Path, key: str, value: str) -> None:
    """Met à jour ou ajoute une variable dans un fichier .env."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    escaped = value.replace("'", "'\\''")
    new_line = f"{key}='{escaped}'"

    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = new_line
            found = True
            break
    if not found:
        lines.append(new_line)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@cli.command()
def login():
    """Configurer ou mettre à jour les identifiants Portail IRIS.

    \b
    Exemple :
      sesam login
    """
    env_path = _resolve_env_path()

    if not env_path.parent.exists():
        console.print(f"[red]❌ Dossier d'installation introuvable : {env_path.parent}[/red]")
        console.print("  Lancez d'abord [cyan]./install.sh[/cyan] depuis le projet.")
        sys.exit(1)

    # Afficher l'utilisateur courant s'il existe
    current_user = os.getenv("SESAM_USERNAME", "")
    if current_user:
        console.print(f"[dim]Utilisateur actuel : {current_user}[/dim]")
        console.print("[dim](laissez vide pour conserver le même)[/dim]\n")

    username = click.prompt("Identifiant", default=current_user or None, show_default=bool(current_user))
    if not username:
        console.print("[yellow]Annulé.[/yellow]")
        sys.exit(2)

    password = getpass.getpass("Mot de passe : ")
    if not password:
        console.print("[yellow]Annulé.[/yellow]")
        sys.exit(2)

    # Test de connexion
    with console.status("Vérification des identifiants..."):
        try:
            r = requests.post(
                f"{PORTAL_BASE_URL}/api/authenticate",
                json={"username": username, "password": password, "rememberMe": True},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=15,
            )
        except requests.RequestException as e:
            console.print(f"[red]❌ Impossible de joindre le portail :[/red] {e}")
            sys.exit(1)

    if r.status_code == 401:
        console.print("[red]❌ Identifiants incorrects.[/red]")
        sys.exit(1)
    if r.status_code != 200:
        console.print(f"[red]❌ Erreur inattendue (HTTP {r.status_code}).[/red]")
        sys.exit(1)

    console.print("[green]✅ Connexion réussie.[/green]")

    # Écriture du .env
    _write_env_var(env_path, "SESAM_USERNAME", username)
    _write_env_var(env_path, "SESAM_PASSWORD", password)
    console.print(f"  Identifiants enregistrés dans [cyan]{env_path}[/cyan]")

    # Purger l'ancien état (cookies/session de l'utilisateur précédent)
    state_path = _resolve_state_path()
    if state_path.exists():
        try:
            state_path.unlink()
            console.print(f"  Session précédente purgée ([dim]{state_path.name}[/dim])")
        except OSError as e:
            console.print(f"[yellow]⚠ Impossible de supprimer {state_path} : {e}[/yellow]")

    console.print(f"\n[green]Vous êtes connecté en tant que [bold]{username}[/bold].[/green]")


@cli.command()
def logout():
    """Déconnecter (supprime la session, conserve les identifiants).

    \b
    Exemple :
      sesam logout
    """
    state_path = _resolve_state_path()

    if not state_path.exists():
        console.print("[yellow]Aucune session active.[/yellow]")
        return

    try:
        state_path.unlink()
    except OSError as e:
        console.print(f"[red]❌ Impossible de supprimer {state_path} :[/red] {e}")
        sys.exit(1)

    console.print(f"[green]✅ Session supprimée[/green] ({state_path})")
    console.print("[dim]Les identifiants sont conservés. Lancez `sesam login` pour les changer.[/dim]")


# ── Entrée principale ─────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
