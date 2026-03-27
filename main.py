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

import sys
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from dotenv import load_dotenv

load_dotenv()

from portal import PortalClient, Ticket
from exceptions import AuthError, APIError
from utils import setup_logging, get_logger, format_ticket_export

logger = get_logger(__name__)
console = Console()


_logo_printed = False


def _print_logo() -> None:
    """Affiche logo.png en blocs Unicode via Rich, adapté à la largeur du terminal."""
    global _logo_printed
    if _logo_printed:
        return
    _logo_printed = True
    logo_path = Path(__file__).parent / "static" / "logo.png"
    if not logo_path.exists():
        return
    try:
        from PIL import Image as PILImage
        img = PILImage.open(logo_path).convert("RGBA")
        width = min(80, console.width - 2)
        aspect = img.height / img.width
        height = int(width * aspect)
        if height % 2 != 0:
            height += 1
        img = img.resize((width, height), PILImage.LANCZOS)
        px = img.load()
        for y in range(0, height, 2):
            line = ""
            for x in range(width):
                _, _, _, a1 = px[x, y]
                _, _, _, a2 = px[x, y + 1] if y + 1 < height else (0, 0, 0, 0)
                top, bot = a1 > 30, a2 > 30
                if top and bot:
                    line += "█"
                elif top:
                    line += "▀"
                elif bot:
                    line += "▄"
                else:
                    line += " "
            console.print(f"[bold white]{line}[/]")
        console.print()
    except Exception:
        pass

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

class LogoGroup(click.Group):
    def invoke(self, ctx):
        _print_logo()
        super().invoke(ctx)

    def get_help(self, ctx):
        _print_logo()
        return super().get_help(ctx)


@click.group(cls=LogoGroup)
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
    """📋 Lister les tickets du Portail IRIS (clos inclus par défaut)."""
    portal = PortalClient()

    with console.status("Récupération des tickets..."):
        try:
            tickets = portal.list_tickets(
                include_closed=not open_only,
                limit=limit,
                page=page,
                fetch_all=fetch_all,
            )
        except AuthError as e:
            console.print(f"[red]❌ Authentification :[/red] {e}")
            sys.exit(1)
        except APIError as e:
            console.print(f"[red]❌ Erreur API :[/red] {e}")
            sys.exit(1)

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

    for t in tickets:
        st_style = _status_style(t.status)
        pr_style = _priority_style(t.priority)
        table.add_row(
            t.code,
            t.type_ticket,
            Text(t.status, style=st_style),
            Text(t.priority, style=pr_style),
            t.titre[:50],
            t.author or "—",
            (t.updated_at[:16] if t.updated_at else "—").replace("T", " "),
        )

    console.print(table)
    console.print(f"[dim]Page {page} · {len(tickets)} ticket(s) affiché(s)[/dim]")


# ── show ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--json-output", "json_out", is_flag=True)
def show(code_or_id, json_out):
    """🔍 Afficher le détail d'un ticket (par référence ou ID)."""
    portal = PortalClient()
    ticket_id = _resolve_id(portal, code_or_id)

    with console.status(f"Chargement du ticket {code_or_id}..."):
        try:
            ticket = portal.get_ticket(ticket_id)
        except (AuthError, APIError) as e:
            console.print(f"[red]❌ {e}[/red]")
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
                title=f"{msg.type_label} — {msg.created_at[:16].replace('T',' ') if msg.created_at else ''}",
                border_style="dim",
            ))


# ── messages ──────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--limit", "-n", default=20, show_default=True)
@click.option("--json-output", "json_out", is_flag=True)
def messages(code_or_id, limit, json_out):
    """💬 Afficher tous les messages d'un ticket."""
    portal = PortalClient()
    ticket_id = _resolve_id(portal, code_or_id)

    with console.status("Chargement des messages..."):
        try:
            msgs = portal.get_messages(ticket_id, limit=limit)
        except (AuthError, APIError) as e:
            console.print(f"[red]❌ {e}[/red]")
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
            title=f"[bold]{msg.type_label}[/bold] — {msg.created_at[:16].replace('T',' ') if msg.created_at else ''}{has_attach}",
            title_align="left",
            border_style="blue" if "entrant" in msg.type_label.lower() else "dim",
        ))


# ── reply ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--title", "-t", default=None, help="Titre du message")
@click.option("--message", "-m", default=None, help="Corps du message")
def reply(code_or_id, title, message):
    """✏️  Ajouter un message à un ticket."""
    if not title:
        title = click.prompt("📝 Titre du message")
    if not message:
        message = click.prompt("✉️  Votre message")

    if not message.strip():
        console.print("[yellow]Message vide, annulé.[/yellow]")
        return

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
        except (AuthError, APIError) as e:
            console.print(f"[red]❌ {e}[/red]")
            sys.exit(1)

    console.print(f"[green]✅ Message envoyé[/green] (ID: {msg.id or 'N/A'})")


# ── export ────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code_or_id")
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown", show_default=True, help="Format de sortie")
def export(code_or_id, fmt):
    """📤 Exporter un ticket en format structuré (prêt pour un agent DUST)."""
    portal = PortalClient()
    ticket_id = _resolve_id(portal, code_or_id)

    with console.status(f"Chargement du ticket {code_or_id}..."):
        try:
            ticket = portal.get_ticket(ticket_id)
        except (AuthError, APIError) as e:
            console.print(f"[red]❌ {e}[/red]")
            sys.exit(1)

    click.echo(format_ticket_export(ticket, fmt))


# ── sync ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--all", "sync_all", is_flag=True, help="Tous les tickets (pas seulement les nouveautés)")
@click.option("--closed", is_flag=True, help="Inclure les tickets clos")
@click.option("--dry-run",  is_flag=True, help="Simuler sans rien marquer")
def sync(sync_all, closed, dry_run):
    """🔄 Détecter les nouveaux tickets et mettre à jour l'état local."""
    portal = PortalClient()

    if dry_run:
        console.print("[yellow]⚠ Mode DRY-RUN — simulation uniquement[/yellow]")

    # 1. Récupérer les tickets
    with console.status("Récupération des tickets..."):
        try:
            all_tickets = portal.list_tickets(include_closed=True, limit=50, fetch_all=True)
        except (AuthError, APIError) as e:
            console.print(f"[red]❌ {e}[/red]")
            sys.exit(1)

    console.print(f"  → {len(all_tickets)} ticket(s) récupéré(s)")

    # 2. Filtrer nouveaux/modifiés
    if sync_all:
        to_sync = all_tickets
        console.print("  → Traitement de tous les tickets")
    else:
        to_sync = portal.get_new_or_updated(all_tickets)
        console.print(f"  → {len(to_sync)} nouveau(x)/modifié(s) depuis la dernière synchro")

    if not to_sync:
        console.print("[green]✅ Tout est à jour, rien à synchroniser.[/green]")
        return

    # 3. Tableau récap
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
def status():
    """🔗 Vérifier la connexion et l'état du compte."""
    portal = PortalClient()

    with console.status("Connexion au portail IRIS..."):
        try:
            account = portal.get_account()
        except (AuthError, APIError) as e:
            console.print(f"[red]❌ {e}[/red]")
            sys.exit(1)

    console.print("[green]✅ Connexion réussie[/green]")
    console.print(f"  Email    : {account.get('email', '—')}")
    console.print(f"  Statut   : {account.get('status', {}).get('label', '—')}")
    console.print(f"  Dernière connexion : {account.get('lastLogin', '—')}")

    # Compter les tickets ouverts
    with console.status("Comptage des tickets..."):
        tickets = portal.list_tickets(limit=100)

    by_status = {}
    for t in tickets:
        by_status[t.status] = by_status.get(t.status, 0) + 1

    console.print(f"\n  [bold]Tickets ouverts : {len(tickets)}[/bold]")
    for st, count in sorted(by_status.items(), key=lambda x: -x[1]):
        style = _status_style(st)
        console.print(f"    [{style}]{st}[/{style}] : {count}")


# ── Entrée principale ─────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
