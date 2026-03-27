"""
web_app.py – Interface web FastAPI pour SESAM Ticket Manager
============================================================
Stack : FastAPI + Jinja2 + Tailwind CSS CDN + Alpine.js + HTMX
Lancement : uvicorn web_app:app --reload --port 8473
"""

import asyncio
import json
import math
import os
import re
import time
from collections import Counter, OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from typing import List
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from exceptions import AuthError, APIError
from portal import PortalClient, Ticket
from utils import format_ticket_export, format_iso_date, get_logger

logger = get_logger(__name__)

_initializing: bool = False  # True durant le fetch initial au démarrage


async def _async_initial_fetch():
    """Lance le delta refresh dans un thread pour ne pas bloquer l'event loop."""
    global _initializing
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: _delta_refresh(_get_client()))
        logger.info("Initial fetch completed.")
    except Exception as e:
        logger.warning(f"Initial fetch failed: {e}")
    finally:
        _initializing = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _initializing
    if not _DISK_CACHE_FILE.exists():
        _initializing = True
        logger.info("Cache absent — fetch initial en cours en arrière-plan...")
        asyncio.create_task(_async_initial_fetch())
    yield


app = FastAPI(title="SESAM Ticket Manager", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    logo = Path(__file__).parent / "static" / "logo.png"
    if not logo.exists():
        raise HTTPException(status_code=404)
    return Response(content=logo.read_bytes(), media_type="image/png")

# ─── Cache (mémoire + disque) ─────────────────────────────────────────────────

_DISK_CACHE_FILE = Path(".sesam_web_cache.json")
_DISK_CACHE_TTL = 3600  # 1 heure
_MEM_CACHE_MAX = 500    # Taille maximale du cache mémoire (entrées LRU)
_LAZY_REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "900"))  # 15 min par défaut

# Cache LRU borné : OrderedDict conserve l'ordre d'insertion/accès.
# Format : {key: (timestamp, data)}
_mem_cache: OrderedDict = OrderedDict()

# Dernier résultat de refresh delta : liste de dicts {code, title, old_status, new_status}
_last_refresh: dict = {}  # {timestamp, changes: list}


def _cache_set(key: str, value: tuple):
    """Insère ou met à jour une entrée dans le cache LRU. Évince le plus ancien si plein."""
    if key in _mem_cache:
        _mem_cache.move_to_end(key)
    _mem_cache[key] = value
    if len(_mem_cache) > _MEM_CACHE_MAX:
        _mem_cache.popitem(last=False)  # Supprime le plus ancien (FIFO)


def _disk_load() -> dict:
    """Load persisted cache from disk. Returns {} if missing or expired."""
    try:
        if not _DISK_CACHE_FILE.exists():
            return {}
        raw = json.loads(_DISK_CACHE_FILE.read_text(encoding="utf-8"))
        if time.time() - raw.get("ts", 0) > _DISK_CACHE_TTL:
            return {}
        return raw.get("data", {})
    except Exception:
        return {}


def _disk_save(data: dict):
    """Persist cache data to disk."""
    try:
        _DISK_CACHE_FILE.write_text(
            json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Failed to persist cache to disk: {e}")


def _disk_invalidate():
    """Delete the disk cache file."""
    try:
        _DISK_CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _cached(key: str, ttl: int, fn, persist: bool = False):
    """
    Return cached value. Checks memory first, then disk (if persist=True), then calls fn().
    persist=True writes to disk so the cache survives server restarts.
    """
    now = time.time()
    # 1. Memory cache
    if key in _mem_cache and now - _mem_cache[key][0] < ttl:
        _mem_cache.move_to_end(key)
        return _mem_cache[key][1]
    # 2. Disk cache (for ticket list only)
    if persist:
        disk = _disk_load()
        if key in disk:
            data = _deserialize_tickets(disk[key])
            _cache_set(key, (now, data))
            return data
    # 3. Fetch from portal
    data = fn()
    _cache_set(key, (now, data))
    if persist:
        disk = _disk_load() or {}
        disk[key] = _serialize_tickets(data)
        _disk_save(disk)
    return data


def _invalidate(prefix: str = ""):
    """Clear memory cache (and disk cache if full invalidation)."""
    keys = [k for k in _mem_cache if k.startswith(prefix)]
    for k in keys:
        del _mem_cache[k]
    if not prefix:
        _disk_invalidate()


def _serialize_tickets(tickets) -> list:
    """Convert Ticket objects to JSON-serializable dicts."""
    return [t.to_dict() for t in tickets]


def _deserialize_tickets(data: list):
    """Reconstruct Ticket objects from dicts."""
    result = []
    for d in data:
        d.pop("raw", None)
        try:
            result.append(Ticket(**{k: v for k, v in d.items() if k != "raw"}))
        except Exception as e:
            logger.warning(f"Skipping malformed ticket from cache: {e}")
    return result


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _filter_tickets(
    tickets: list[Ticket],
    status: str | None = None,
    type_: str | None = None,
    q: str | None = None,
) -> list[Ticket]:
    """Filtre une liste de tickets par statut, type et recherche textuelle."""
    filtered = tickets
    if status:
        filtered = [t for t in filtered if t.status == status]
    if type_:
        filtered = [t for t in filtered if t.type_ticket == type_]
    if q:
        q_lower = q.lower()
        filtered = [
            t for t in filtered
            if q_lower in t.titre.lower()
            or q_lower in t.code.lower()
            or q_lower in (t.author or "").lower()
            or q_lower in (t.service or "").lower()
        ]
    return filtered


def _get_client() -> PortalClient:
    """Instancie un PortalClient avec la configuration courante."""
    return PortalClient()


def _get_all_tickets(client: PortalClient):
    """
    Retourne la liste complète des tickets (ouverts + clos) depuis le cache.

    Le cache mémoire a une durée de vie de _DISK_CACHE_TTL secondes.
    Si le cache mémoire est vide, tente de lire le cache disque.
    En dernier recours, interroge le portail IRIS.
    """
    return _cached(
        "tickets:all",
        ttl=_DISK_CACHE_TTL,
        fn=lambda: client.list_tickets(include_closed=True, fetch_all=True),
        persist=True,
    )


def _get_ticket_messages(client: PortalClient, ticket_id: str):
    """
    Retourne les messages d'un ticket enrichis avec les métadonnées des pièces jointes.

    Utilise un cache mémoire de 30 secondes par ticket pour éviter les appels
    répétés lors du rechargement de la page détail.
    """
    return _cached(
        f"messages:{ticket_id}",
        ttl=30,
        fn=lambda: client.get_enriched_messages(ticket_id),
    )


def _format_date(dt_str: str) -> str:
    """Format ISO date string to DD/MM/YYYY HH:MM."""
    return format_iso_date(dt_str, fmt="%d/%m/%Y %H:%M")


def _format_date_short(dt_str: str) -> str:
    """Format ISO date string to DD/MM/YYYY."""
    return format_iso_date(dt_str, fmt="%d/%m/%Y")


def _clean_body(text: str) -> str:
    """Normalize line endings and collapse consecutive blank lines to at most one."""
    if not text:
        return ""
    # Normalize \r\n and \r to \n, strip trailing spaces on each line
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.splitlines()]
    # Collapse 2+ consecutive blank lines to a single blank line
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return result.strip()


# Register filters in Jinja2
templates.env.filters["format_date"] = _format_date
templates.env.filters["format_date_short"] = _format_date_short
templates.env.filters["clean_body"] = _clean_body


def _is_client_author(type_code: str) -> bool:
    """
    Returns True if the message was sent by the client user.
    Outbound messages from the client = INEXTRANET or similar.
    """
    # INEXTRANET = client sending to SESAM (outgoing from client = blue right)
    # INTRANET = message from SESAM support (gray left)
    return type_code in ("INEXTRANET",)


templates.env.filters["is_client_author"] = _is_client_author


def _status_color(status: str) -> str:
    """Return a Tailwind color class for the status badge."""
    s = (status or "").lower()
    if "cours" in s:
        return "bg-blue-100 text-blue-800"
    if "attente" in s:
        return "bg-yellow-100 text-yellow-800"
    if "expertise" in s or "externe" in s:
        return "bg-purple-100 text-purple-800"
    if "clos" in s or "résolu" in s or "fermé" in s:
        return "bg-gray-100 text-gray-500"
    return "bg-gray-100 text-gray-700"


templates.env.filters["status_color"] = _status_color


def _priority_color(priority: str) -> str:
    """Return a Tailwind color class for the priority badge."""
    p = (priority or "").lower()
    if "urgent" in p or "critique" in p or "haut" in p:
        return "bg-red-100 text-red-800"
    if "normal" in p or "moyen" in p:
        return "bg-green-100 text-green-700"
    if "bas" in p or "faible" in p:
        return "bg-gray-100 text-gray-500"
    return "bg-gray-100 text-gray-700"


templates.env.filters["priority_color"] = _priority_color


def _is_hot(dt_str: str) -> bool:
    """Returns True if updated_at is within the last 24 hours."""
    if not dt_str:
        return False
    try:
        dt = datetime.fromisoformat(dt_str[:19]).replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt < timedelta(hours=24)
    except Exception:
        return False


templates.env.filters["is_hot"] = _is_hot


# ─── Suggestion service / qualification ──────────────────────────────────────

_SUGGEST_STOPWORDS = {
    "je", "un", "une", "des", "les", "est", "en", "de", "du", "la", "le",
    "et", "ou", "sur", "pour", "avec", "par", "au", "aux", "il", "elle",
    "ils", "elles", "nous", "vous", "mon", "ma", "mes", "son", "sa", "ses",
    "ce", "cet", "cette", "ces", "qui", "que", "quoi", "dont", "où", "à",
    "pas", "ne", "plus", "bien", "aussi", "très", "lors", "si", "car",
    "mais", "donc", "or", "ni", "tout", "tous", "toute", "non", "etc",
    "vs", "via", "chez", "cas", "dans", "sont", "bonjour", "cordialement",
    "merci", "avons", "notre", "leur", "nos",
}

# Termes techniques → fragment du label de qualification
# Basé sur l'analyse tf-idf de l'historique des tickets
_SUGGEST_SYNONYMS: dict[str, list[str]] = {
    "fsv": ["Package FSV"], "cica": ["Package FSV"], "adm": ["Package FSV"],
    "installeur": ["Package FSV"], "ssv": ["Package FSV", "J'ai une erreur SSV"],
    "0x": ["J'ai une erreur SSV"], "fse": ["J'ai une erreur SSV"],
    "signature": ["Support ARL", "J'ai une erreur SSV"],
    "arl": ["Support ARL"], "lot": ["Support ARL"], "lots": ["Support ARL"],
    "invérifiable": ["Support ARL"], "invérifiables": ["Support ARL"],
    "ccam": ["Support CCAM"], "c2s": ["Support CCAM"],
    "optam": ["Support CCAM", "Evolutions Règlementaires"],
    "tarification": ["Support CCAM"],
    "annexe": ["Tables de l'annexe"], "majoration": ["Tables de l'annexe"],
    "ameli": ["Tables de l'annexe"],
    "srt": ["Package Tables"], "sts": ["Package Tables"], "plafonds": ["Package Tables"],
    "nfc": ["Facturation avec l'Appli"], "iphone": ["Facturation avec l'Appli"],
    "ios": ["Facturation avec l'Appli"], "apple": ["Facturation avec l'Appli"],
    "android": ["Facturation avec l'Appli"],
    "apcv": ["Erreur apcv", "Facturation avec l'Appli"],
    "usb": ["Erreur apcv"], "hid": ["Erreur apcv"], "décodage": ["Erreur apcv"],
    "mgen": ["Flux SV en phase de production"],
    "triptyque": ["Flux SV en phase de production"],
    "migration": ["Flux SV en phase de production"],
    "rejet": ["Flux SV", "Demande d'accompagnement"],
    "rejets": ["Flux SV", "Demande d'accompagnement"],
    "télétransmission": ["Flux SV"], "télétransmissions": ["Flux SV"],
    "4005": ["Flux SV en phase de développement"],
    "404": ["Problème d'accès"], "finess": ["Problème d'accès"],
    "siret": ["Problème d'accès"], "identifiant": ["Problème d'accès"],
    "connexion": ["Problème d'accès"], "industriels": ["Problème d'accès"],
    "avenant": ["Evolutions Règlementaires", "j'ai une question concernant la documentation"],
    "réglementaire": ["Evolutions Règlementaires"],
    "reglementaire": ["Evolutions Règlementaires"],
    "frmt": ["Evolutions Règlementaires"], "valorisation": ["Evolutions Règlementaires"],
    "revalorisation": ["Evolutions Règlementaires"],
    "coefficients": ["Veille conventionnelle"], "coefficient": ["Veille conventionnelle"],
    "mcdc": ["j'ai une question concernant la documentation"],
    "cahier": ["j'ai une question concernant la documentation"],
    "scor": ["j'ai une question concernant la documentation"],
    "te2": ["j'ai une question concernant la documentation"],
    "livrable": ["J'ai une question sur la documentation"],
    "mutuelle": ["J'ai une question sur la documentation"],
    "harmonie": ["J'ai une question sur la documentation"],
    "catégorie": ["J'ai une question sur la documentation"],
    "nir": ["J'ai une demande technique"], "annuaire": ["J'ai une demande technique"],
    "lps": ["J'ai une demande technique"], "adri": ["J'ai une demande technique"],
    "clc": ["J'ai besoin d'aide en phase de développement"],
    "etudes": ["J'ai besoin d'aide en phase de développement"],
    "éditeur": ["J'ai besoin d'aide en phase de développement", "J'ai une demande technique"],
    "intégration": ["J'ai besoin d'aide en phase de développement"],
    "integration": ["J'ai besoin d'aide en phase de développement"],
    "développement": ["J'ai besoin d'aide en phase de développement", "Flux SV en phase de développement"],
    "developpement": ["J'ai besoin d'aide en phase de développement", "Flux SV en phase de développement"],
    "rsp": ["Demande d'accompagnement"], "meusrec": ["Demande d'accompagnement"],
    "entité": ["Demande d'accompagnement"],
    "composant": ["à l'installation des composants"],
    "composants": ["à l'installation des composants"],
    "télécharger": ["à l'installation des composants"],
    "diagam": ["à l'installation des composants"],
    "salarié": ["Autre sujet lié à la facturation"],
    "salarie": ["Autre sujet lié à la facturation"],
    "msp": ["Autre sujet lié à la facturation"],
    "selas": ["Autre sujet lié à la facturation"],
    "honoraires": ["Autre sujet lié à la facturation"],
    "dysfonctionnement": ["Je rencontre un dysfonctionnement"],
    "anomalie": ["Je rencontre un dysfonctionnement"],
    "bug": ["Je rencontre un dysfonctionnement"],
    "ordonnance": ["Je rencontre un dysfonctionnement"],
}

# Cache des fréquences de qualification calculé à la première suggestion
_qual_freq_cache: Counter | None = None


def _build_qual_freq() -> Counter:
    """Calcule les fréquences de qualification depuis le cache disque."""
    global _qual_freq_cache
    if _qual_freq_cache is not None:
        return _qual_freq_cache
    try:
        disk = _disk_load()
        tickets = disk.get("tickets:all", [])
        _qual_freq_cache = Counter(
            t.get("qualification", "") for t in tickets if t.get("qualification")
        )
    except Exception:
        _qual_freq_cache = Counter()
    return _qual_freq_cache


def _tokenize_suggest(text: str) -> list[str]:
    words = re.findall(r"[a-zàâäéèêëîïôùûüç0-9]+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in _SUGGEST_STOPWORDS]


def _compute_scores(
    titre: str,
    description: str,
    items: list[dict],
    label_fn,
    freq_map: Counter | None = None,
) -> dict[str, float]:
    """
    Retourne {item_id: score} pour chaque item afin de trier les dropdowns par pertinence.
    """
    tokens = _tokenize_suggest(titre + " " + description)
    if not tokens:
        return {}

    token_set = set(tokens)

    def _score(label: str, freq: int = 0) -> float:
        score = 0.0
        for tok in token_set:
            for partial in _SUGGEST_SYNONYMS.get(tok, []):
                if partial.lower() in label.lower():
                    score += 0.4
        label_tokens = set(_tokenize_suggest(label))
        inter = len(token_set & label_tokens)
        union = len(token_set | label_tokens)
        if union:
            j = inter / union
            score += j * (1 + 0.1 * math.log(1 + freq))
        return score

    result = {}
    for item in items:
        item_id = item.get("id")
        if not item_id:
            continue
        label = label_fn(item)
        freq = freq_map.get(label, 0) if freq_map else 0
        s = _score(label, freq)
        if s > 0:
            result[item_id] = round(s, 3)
    return result


# ─── Routes ──────────────────────────────────────────────────────────────────




@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, updated: int | None = None):
    """
    Page d'accueil : tableau de bord avec statistiques et tickets récents.

    Affiche le total des tickets, le nombre d'ouverts/clos, la répartition
    par statut et les 15 dernières activités (hot tickets + actifs récents).
    Le paramètre `updated` indique le nombre de tickets modifiés lors du dernier refresh.
    """
    if _initializing:
        return templates.TemplateResponse(request, "loading.html", {})

    # Lazy refresh si le cache est trop vieux
    try:
        if _DISK_CACHE_FILE.exists():
            raw = json.loads(_DISK_CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - raw.get("ts", 0) > _LAZY_REFRESH_INTERVAL:
                _delta_refresh(_get_client())
    except Exception as e:
        logger.warning(f"Lazy refresh failed: {e}")

    try:
        client = _get_client()
        tickets = _get_all_tickets(client)
    except (AuthError, APIError) as e:
        return templates.TemplateResponse(request, "error.html", {"error": str(e)}, status_code=503)

    # Compute stats
    total = len(tickets)
    open_tickets = [t for t in tickets if "clos" not in t.status.lower() and "résolu" not in t.status.lower() and "fermé" not in t.status.lower() and "suspendu" not in t.status.lower()]
    closed_tickets = [t for t in tickets if t not in open_tickets]

    # Count by status
    status_counts: dict[str, int] = {}
    for t in tickets:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1

    # Recent tickets: tous ceux mis à jour dans les 24h, + les actifs récents pour compléter
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()[:19]

    def _is_active(t):
        s = t.status.lower()
        return "clos" not in s and "résolu" not in s and "fermé" not in s and "suspendu" not in s

    hot = sorted([t for t in tickets if (t.updated_at or "") >= cutoff], key=lambda t: t.updated_at or "", reverse=True)
    active = sorted([t for t in tickets if _is_active(t) and t not in hot], key=lambda t: t.updated_at or "", reverse=True)
    recent = (hot + active)[:15]

    return templates.TemplateResponse(request, "dashboard.html", {
        "total": total,
        "open_count": len(open_tickets),
        "closed_count": len(closed_tickets),
        "status_counts": sorted(status_counts.items(), key=lambda x: -x[1]),
        "recent": recent,
        "cache_age": _cache_age(),
        "updated": updated,
        "last_refresh": _last_refresh,
    })


@app.get("/tickets", response_class=HTMLResponse)
async def tickets_list(
    request: Request,
    status: str | None = None,
    type: str | None = None,
    q: str | None = None,
):
    """
    Liste paginée des tickets avec filtres.

    Paramètres query string :
      - status : filtre exact sur le statut (ex: "En cours")
      - type   : filtre sur le type de ticket ("Incident" ou "Demande")
      - q      : recherche textuelle dans le titre, la référence, l'auteur et le service
    """
    if _initializing:
        return templates.TemplateResponse(request, "loading.html", {})

    try:
        client = _get_client()
        tickets = _get_all_tickets(client)
    except (AuthError, APIError) as e:
        return templates.TemplateResponse(request, "error.html", {"error": str(e)}, status_code=503)

    # Build available filter values
    all_types = sorted({t.type_ticket for t in tickets if t.type_ticket})
    status_counts: dict[str, int] = {}
    for t in tickets:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1
    status_counts_sorted = sorted(status_counts.items(), key=lambda x: -x[1])

    # Sort by updated_at desc
    tickets = sorted(tickets, key=lambda t: t.updated_at or "", reverse=True)

    filtered = _filter_tickets(tickets, status=status, type_=type, q=q)

    return templates.TemplateResponse(request, "tickets.html", {
        "tickets": filtered,
        "total_count": len(filtered),
        "status_counts": status_counts_sorted,
        "all_types": all_types,
        "filter_status": status or "",
        "filter_type": type or "",
        "filter_q": q or "",
    })



@app.get("/tickets/create", response_class=HTMLResponse)
async def create_ticket_form(request: Request):
    """Affiche le formulaire de création d'un nouveau ticket."""
    try:
        client = _get_client()
        services = client.get_services()
        qualifications = client.get_qualifications()
    except (AuthError, APIError) as e:
        return templates.TemplateResponse(request, "error.html", {"error": str(e)}, status_code=503)
    return templates.TemplateResponse(request, "create_ticket.html", {
        "services": services or [],
        "qualifications": qualifications or [],
    })


@app.post("/tickets/create", response_class=HTMLResponse)
async def create_ticket_submit(
    request: Request,
    titre: str = Form(...),
    description: str = Form(...),
    service_id: str = Form(""),
    qualification_id: str = Form(""),
    priority_code: str = Form("AVERAGE"),
    files: List[UploadFile] = File(default=[]),
    descriptions: List[str] = Form(default=[]),
):
    """
    Traite la soumission du formulaire de création de ticket.

    En cas de succès, invalide le cache et redirige vers la page de détail du nouveau ticket.
    En cas d'erreur, réaffiche le formulaire avec le message d'erreur et les valeurs saisies.
    """
    try:
        client = _get_client()
        attachments = []
        real_files = [f for f in files if f.filename]
        if real_files:
            upload_list = []
            for i, f in enumerate(real_files):
                desc = descriptions[i] if i < len(descriptions) else ""
                upload_list.append((f.filename, await f.read(), f.content_type, desc))
            attachments = client.upload_files(upload_list)

        ticket = client.create_ticket(
            source="DEMANDE",
            titre=titre,
            description=description,
            service_id=service_id or None,
            qualification_id=qualification_id or None,
            priority_code=priority_code,
            attachments=attachments or None,
        )
        _invalidate()
        return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=303)
    except (AuthError, APIError) as e:
        try:
            client2 = _get_client()
            services = client2.get_services()
            qualifications = client2.get_qualifications()
        except Exception:
            services, qualifications = [], []
        return templates.TemplateResponse(request, "create_ticket.html", {
            "services": services,
            "qualifications": qualifications,
            "error": str(e),
            "form": {
                "titre": titre,
                "description": description,
                "service_id": service_id,
                "qualification_id": qualification_id,
                "priority_code": priority_code,
            },
        }, status_code=422)


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def ticket_detail(request: Request, ticket_id: str):
    """
    Page de détail d'un ticket : métadonnées, messages chronologiques et pièces jointes.

    Les messages sont triés du plus ancien au plus récent (conversation naturelle).
    """
    try:
        client = _get_client()
        ticket = client.get_ticket(ticket_id)
        messages = _get_ticket_messages(client, ticket_id)
    except (AuthError, APIError) as e:
        return templates.TemplateResponse(request, "error.html", {"error": str(e)}, status_code=503)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Ticket not found: {e}")

    # Sort messages chronologically: oldest first, newest at bottom
    sorted_messages = sorted(messages, key=lambda m: m.created_at or "")

    return templates.TemplateResponse(request, "ticket_detail.html", {
        "ticket": ticket,
        "messages": sorted_messages,
    })


@app.get("/tickets/{ticket_id}/export")
async def export_ticket(ticket_id: str, fmt: str = "markdown"):
    """Export a ticket as structured Markdown or JSON for DUST agents."""
    try:
        client = _get_client()
        ticket = client.get_ticket(ticket_id)
        ticket.messages = _get_ticket_messages(client, ticket_id)
    except (AuthError, APIError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    content = format_ticket_export(ticket, fmt)
    media_type = "application/json" if fmt == "json" else "text/markdown"
    return Response(content=content, media_type=f"{media_type}; charset=utf-8")


@app.get("/tickets/{ticket_id}/messages/{message_id}/attachments/{attachment_id}")
async def download_attachment(
    ticket_id: str, message_id: str, attachment_id: str,
    filename: str = "", inline: bool = False,
):
    """
    Proxy attachment download from the portal.
    Endpoint (reverse-engineered from main.bundle.js):
      GET /api/messages/{message_id}/attachments/{attachment_id}/download
    Pass ?inline=true to get Content-Disposition: inline (for browser preview).
    """
    try:
        from portal import API_BASE
        client = _get_client()
        client._ensure_logged_in()

        url = f"{API_BASE}/messages/{message_id}/attachments/{attachment_id}/download"
        resp = client._session.get(url, stream=True, timeout=30)
        if resp.ok:
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            safe_name = filename or attachment_id
            disp_type = "inline" if inline else "attachment"
            disposition = f'{disp_type}; filename="{safe_name}"'

            def iter_content(r=resp):
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk

            return StreamingResponse(
                iter_content(),
                media_type=content_type,
                headers={"Content-Disposition": disposition},
            )

        raise HTTPException(status_code=404, detail="Pièce jointe introuvable sur le portail.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tickets/{ticket_id}/messages/raw")
async def api_messages_raw(ticket_id: str):
    """Debug: raw message data including attachment structure."""
    try:
        client = _get_client()
        messages = client.get_messages(ticket_id, limit=10)
        return [
            {
                "id": m.id,
                "title": m.title,
                "type_code": m.type_code,
                "created_at": m.created_at,
                "attachments": m.attachments,
            }
            for m in messages
        ]
    except Exception as e:
        return {"error": str(e)}


@app.post("/tickets/{ticket_id}/reply", response_class=HTMLResponse)
async def ticket_reply(
    request: Request,
    ticket_id: str,
    message: str = Form(...),
    action: str = Form(""),
):
    """
    Envoie un message de réponse sur un ticket.

    Si action="close", résout également le ticket après envoi du message.
    Invalide le cache des messages et (si clos) le cache des tickets.
    """
    try:
        client = _get_client()
        client.add_message(ticket_id, title="Réponse éditeur", body=message)
        _invalidate(f"messages:{ticket_id}")
        if action == "close":
            client.resolve_ticket(ticket_id)
            _invalidate("tickets:all")
            _disk_invalidate()
    except (AuthError, APIError) as e:
        return templates.TemplateResponse(request, "error.html", {"error": str(e)}, status_code=503)

    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


@app.post("/tickets/{ticket_id}/resolve", response_class=HTMLResponse)
async def ticket_resolve(request: Request, ticket_id: str):
    """
    Résout un ticket sans envoyer de message.

    Invalide le cache des messages et le cache global des tickets,
    puis redirige vers la page de détail du ticket.
    """
    try:
        client = _get_client()
        client.resolve_ticket(ticket_id)
        _invalidate(f"messages:{ticket_id}")
        _invalidate("tickets:all")
        _disk_invalidate()
    except (AuthError, APIError) as e:
        return templates.TemplateResponse(request, "error.html", {"error": str(e)}, status_code=503)

    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


def _cache_age() -> str:
    """Return human-readable age of the disk cache, or empty string if none."""
    try:
        if not _DISK_CACHE_FILE.exists():
            return ""
        raw = json.loads(_DISK_CACHE_FILE.read_text(encoding="utf-8"))
        age = time.time() - raw.get("ts", 0)
        if age < 60:
            return "il y a quelques secondes"
        if age < 3600:
            return f"il y a {int(age // 60)} min"
        return f"il y a {int(age // 3600)}h"
    except Exception:
        return ""


def _is_closed_status(status: str) -> bool:
    """Retourne True si le statut correspond à un ticket fermé/résolu/suspendu."""
    s = status.lower()
    return "clos" in s or "résolu" in s or "fermé" in s or "suspendu" in s


def _delta_refresh(client: PortalClient) -> int:
    """
    Smart refresh:
    1. Fetch full ticket list (statuts + metadata, no messages)
    2. Compare with cache — find status/updated_at changes
    3. Deepdive only changed tickets: fetch their messages
    4. Rebuild and persist cache
    Returns number of changed tickets.
    """
    global _last_refresh

    # Step 1 : fetch current metadata for all tickets
    current = client.list_tickets(include_closed=True, fetch_all=True)

    # Step 2 : build cached lookup {code → Ticket}
    cached_lookup: dict = {}
    disk_data = _disk_load()
    if "tickets:all" in disk_data:
        for t in _deserialize_tickets(disk_data["tickets:all"]):
            cached_lookup[t.code] = t
    elif "tickets:all" in _mem_cache:
        for t in _mem_cache["tickets:all"][1]:
            cached_lookup[t.code] = t

    # Step 3 : detect changes (new ticket, status changed, or updated_at changed)
    # Les tickets déjà fermés dans le cache sont ignorés (optimisation).
    # Risque accepté : une réouverture ne sera détectée qu'au prochain sync complet.
    changed = [
        t for t in current
        if not (t.code in cached_lookup and _is_closed_status(cached_lookup[t.code].status))
        and (
            t.code not in cached_lookup
            or cached_lookup[t.code].status != t.status
            or cached_lookup[t.code].updated_at != t.updated_at
        )
    ]

    # Step 4 : deepdive — fetch messages for each changed ticket
    final_by_code = {t.code: t for t in current}
    change_details = []
    for t in changed:
        old = cached_lookup.get(t.code)
        change_details.append({
            "id": t.id,
            "code": t.code,
            "title": t.titre or t.code,
            "old_status": old.status if old else None,  # None = nouveau ticket
            "new_status": t.status,
        })
        try:
            messages = client.get_enriched_messages(t.id)
            _cache_set(f"messages:{t.id}", (time.time(), messages))
        except Exception as e:
            logger.warning(f"Failed to enrich messages for ticket {t.id}: {e}")

    # Step 5 : persist updated ticket list
    ticket_list = list(final_by_code.values())
    _cache_set("tickets:all", (time.time(), ticket_list))
    disk_data["tickets:all"] = _serialize_tickets(ticket_list)
    _disk_save(disk_data)

    # Step 6 : store last refresh result for dashboard display
    _last_refresh = {
        "timestamp": time.time(),
        "changes": change_details,
    }

    return len(changed)


@app.post("/refresh")
async def refresh_cache():
    """Smart delta refresh: detect status changes, deepdive only what changed."""
    try:
        client = _get_client()
        updated = _delta_refresh(client)
        return RedirectResponse(url=f"/?updated={updated}", status_code=303)
    except Exception:
        _invalidate()
        return RedirectResponse(url="/", status_code=303)


@app.post("/refresh/full")
async def refresh_cache_full():
    """Force full re-scrape, bypassing cache entirely."""
    _invalidate()
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/suggest")
async def api_suggest(titre: str = "", description: str = "", service_id: str = ""):
    """
    Retourne les scores de pertinence pour trier les dropdowns.
    Sans service_id → {service_scores: {id: score}}
    Avec service_id  → {qual_scores: {id: score}} (filtrées par le service)
    """
    if len((titre + description).strip()) < 10:
        return {}
    try:
        client = _get_client()
        if not service_id:
            services = client.get_services() or []
            scores = _compute_scores(
                titre, description, services,
                lambda s: s.get("display") or s.get("nomLong") or s.get("nomCourt") or "",
            )
            return {"service_scores": scores}
        else:
            qualifications = client.get_qualifications() or []
            services = client.get_services() or []
            svc = next((s for s in services if s.get("id") == service_id), None)
            if svc and svc.get("qualifs"):
                qualifications = [q for q in qualifications if q.get("id") in svc["qualifs"]]
            scores = _compute_scores(
                titre, description, qualifications,
                lambda q: q.get("label") or q.get("code") or "",
                freq_map=_build_qual_freq(),
            )
            return {"qual_scores": scores}
    except Exception:
        return {}


@app.get("/api/tickets")
async def api_tickets(
    status: str | None = None,
    type: str | None = None,
    q: str | None = None,
):
    """JSON endpoint for dynamic filtering (Alpine.js)."""
    try:
        client = _get_client()
        tickets = _get_all_tickets(client)
    except (AuthError, APIError) as e:
        return {"error": str(e), "tickets": []}

    filtered = _filter_tickets(tickets, status=status, type_=type, q=q)
    return {"tickets": [t.to_dict() for t in filtered]}
