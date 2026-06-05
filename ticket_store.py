"""ticket_store.py — Couche domaine partagée CLI + WebUI.

Point d'accès unique aux tickets et messages, au-dessus de CacheStore.
Fichier cache partagé : .sesam_cache.json

Stratégie :
  - Tickets clos   → permanent (jamais expiré, source statique pour les agents)
  - Tickets ouverts → TTL_TICKET (15 min)
  - Messages clos  → permanent
  - Messages ouverts → TTL_MESSAGES (5 min)
  - Liste globale  → TTL_LIST (5 min)
"""

import heapq
import logging
import time
from pathlib import Path
from typing import Optional

from cache import CacheStore
from portal import Message, PortalClient, Ticket

logger = logging.getLogger(__name__)

# ── Instance singleton ────────────────────────────────────────────────────────

_store = CacheStore(Path(".sesam_cache.json"), mem_max=500)

# ── TTL ──────────────────────────────────────────────────────────────────────

TTL_LIST     = 300   # 5 min
TTL_TICKET   = 900   # 15 min
TTL_MESSAGES = 300   # 5 min

# ── Clés de cache ─────────────────────────────────────────────────────────────

_KEY_ALL      = "tickets:all"


def _key_ticket(tid: str) -> str:
    return f"ticket:{tid}"


def _key_messages(tid: str, limit: int) -> str:
    return f"messages:{tid}:{limit}"


def _key_messages_enriched(tid: str) -> str:
    return f"messages:{tid}:enriched"


def _key_code(code: str) -> str:
    return f"code:{code}"


# ── État du dernier refresh ───────────────────────────────────────────────────

last_refresh: dict = {}  # {"timestamp": float, "changes": list}

# ── Helpers domaine ───────────────────────────────────────────────────────────

def is_closed(status: str) -> bool:
    """Retourne True si le statut correspond à un ticket fermé/résolu/suspendu."""
    s = status.lower()
    return "clos" in s or "résolu" in s or "fermé" in s or "suspendu" in s


def is_client_author(type_code: str) -> bool:
    """Retourne True si le message est d'origine client (extranet entrant/sortant)."""
    return type_code in ("INEXTRANET", "EXEXTRANET")


def _is_gie_relance(msgs: list[Message]) -> bool:
    """Retourne True si les 2 derniers messages (par date) sont du GIE."""
    if len(msgs) < 2:
        return False
    last_two = heapq.nlargest(2, msgs, key=lambda m: m.created_at or "")
    return all(not is_client_author(m.type_code) for m in last_two)


# ── Sérialisation ─────────────────────────────────────────────────────────────

def _ser_tickets(tickets: list[Ticket]) -> list[dict]:
    return [t.to_dict() for t in tickets]


def _deser_tickets(data: list[dict]) -> list[Ticket]:
    result = []
    for d in data:
        try:
            result.append(Ticket.from_dict(d))
        except Exception as e:
            logger.warning(f"Skipping malformed ticket from cache: {e}")
    return result


def _ser_messages(msgs: list[Message]) -> list[dict]:
    return [m.to_dict() for m in msgs]


def _deser_messages(data: list[dict]) -> list[Message]:
    result = []
    for d in data:
        try:
            result.append(Message.from_dict(d))
        except Exception as e:
            logger.warning(f"Skipping malformed message from cache: {e}")
    return result


# ── Lecture ───────────────────────────────────────────────────────────────────

def get_all_tickets(client: PortalClient, refresh: bool = False) -> list[Ticket]:
    """Liste complète (ouverts + clos). Appel réseau si cache expiré ou refresh=True."""
    if not refresh:
        cached = _store.get(_KEY_ALL, TTL_LIST)
        if cached is not None:
            return _deser_tickets(cached)

    tickets = client.list_tickets(include_closed=True, fetch_all=True)
    _store.put(_KEY_ALL, _ser_tickets(tickets))
    prepopulate_closed(tickets)
    return tickets


def get_ticket(client: PortalClient, ticket_id: str, refresh: bool = False) -> Ticket:
    """Détail d'un ticket par ID. Permanent si clos."""
    if not refresh:
        cached = _store.get(_key_ticket(ticket_id), TTL_TICKET)
        if cached is not None:
            return Ticket.from_dict(cached)

    ticket = client.get_ticket(ticket_id)
    put_ticket(ticket)
    return ticket


def resolve_code(client: PortalClient, code: str, refresh: bool = False) -> str:
    """Résout une référence XX-YYY-NNNNNN en ID hexadécimal. Permanent si ticket clos."""
    if not refresh:
        cached_id = _store.get(_key_code(code), TTL_TICKET)
        if cached_id:
            return cached_id

    ticket = client.get_ticket_by_code(code)
    if ticket is None:
        raise KeyError(f"Ticket {code} introuvable")

    put_ticket(ticket)
    if not ticket.closed_at:
        _store.put(_key_code(code), ticket.id)
    return ticket.id


def get_messages(
    client: PortalClient, ticket_id: str, limit: int = 50, refresh: bool = False
) -> list[Message]:
    """Messages d'un ticket (simples). Permanent si ticket clos."""
    key = _key_messages(ticket_id, limit)
    if not refresh:
        cached = _store.get(key, TTL_MESSAGES)
        if cached is not None:
            return _deser_messages(cached)

    msgs = client.get_messages(ticket_id, limit=limit)
    ticket_raw = _store.get_raw(_key_ticket(ticket_id))
    closed = bool(ticket_raw and ticket_raw.get("closed_at"))
    _store.put(key, _ser_messages(msgs), permanent=closed)
    return msgs


def get_enriched_messages(
    client: PortalClient, ticket_id: str, refresh: bool = False
) -> list[Message]:
    """Messages enrichis avec pièces jointes. Permanent si ticket clos."""
    key = _key_messages_enriched(ticket_id)
    if not refresh:
        cached = _store.get(key, TTL_MESSAGES)
        if cached is not None:
            return _deser_messages(cached)

    msgs = client.get_enriched_messages(ticket_id)
    ticket_raw = _store.get_raw(_key_ticket(ticket_id))
    closed = bool(ticket_raw and ticket_raw.get("closed_at"))
    _store.put(key, _ser_messages(msgs), permanent=closed)
    return msgs


def has_data() -> bool:
    """Vrai si le cache contient des données (pour la détection d'initialisation)."""
    return _store.has_data()


def get_list_age_seconds() -> Optional[float]:
    """Retourne l'âge en secondes de la liste globale en cache, None si absente."""
    return _store.age_seconds(_KEY_ALL)


def get_cached_all_raw() -> list[dict]:
    """Retourne les dicts bruts de tous les tickets depuis le cache, sans appel réseau."""
    raw = _store.get_raw(_KEY_ALL)
    return raw if raw is not None else []


def stats() -> dict:
    return _store.stats()


# ── Écriture ──────────────────────────────────────────────────────────────────

def put_ticket(ticket: Ticket) -> None:
    """Cache un ticket — permanent si clos, TTL sinon."""
    permanent = bool(ticket.closed_at)
    _store.put(_key_ticket(ticket.id), ticket.to_dict(), permanent=permanent)
    if permanent and ticket.code:
        _store.put(_key_code(ticket.code), ticket.id, permanent=True)


def put_messages(ticket_id: str, limit: int, msgs: list[Message], closed: bool) -> None:
    """Cache des messages simples — permanent si ticket clos, TTL sinon."""
    _store.put(_key_messages(ticket_id, limit), _ser_messages(msgs), permanent=closed)


def prepopulate_closed(tickets: list[Ticket]) -> None:
    """Pré-peuple le cache permanent pour tous les tickets clos en un seul write disque."""
    items: dict[str, tuple] = {}
    for t in tickets:
        if t.closed_at:
            items[_key_ticket(t.id)] = (t.to_dict(), True)
            if t.code:
                items[_key_code(t.code)] = (t.id, True)
    if items:
        _store.put_batch(items)


def enrich_gie_relance(tickets: list[Ticket]) -> None:
    """Enrichit in-place gie_relance depuis le cache, sans appel réseau."""
    for t in tickets:
        if is_closed(t.status):
            continue
        raw = _store.get_raw(_key_messages_enriched(t.id))
        if raw is None:
            raw = _store.get_raw(_key_messages(t.id, 50))
        if raw:
            t.gie_relance = _is_gie_relance(_deser_messages(raw))


# ── Invalidation ──────────────────────────────────────────────────────────────

def invalidate_ticket(ticket_id: str) -> None:
    """Invalide ticket + messages (non permanents uniquement)."""
    _store.invalidate(f"ticket:{ticket_id}")
    _store.invalidate(f"messages:{ticket_id}:")


def invalidate_list() -> None:
    """Invalide la liste globale (non permanente)."""
    _store.invalidate(_KEY_ALL)


def invalidate_all() -> None:
    """Purge complète du cache y compris les entrées permanentes."""
    _store.invalidate()


# ── Delta refresh ─────────────────────────────────────────────────────────────

def delta_refresh(client: PortalClient) -> int:
    """Refresh intelligent :
    1. Fetch la liste complète (métadonnées, sans messages)
    2. Compare avec le cache précédent sans TTL
    3. Deepdive uniquement les tickets changés → messages enrichis + gie_relance
    4. Recalcule gie_relance pour les tickets "En attente" inchangés
    5. Persiste la liste mise à jour
    Retourne le nombre de tickets modifiés.
    """
    global last_refresh

    # 1. Liste fraîche depuis l'API
    current = client.list_tickets(include_closed=True, fetch_all=True)

    # 2. Référence précédente sans TTL (pour comparaison quelle que soit l'ancienneté)
    cached_lookup: dict[str, Ticket] = {}
    raw_all = _store.get_raw(_KEY_ALL)
    if raw_all:
        for t in _deser_tickets(raw_all):
            cached_lookup[t.code] = t

    # 3. Détection des changements
    # Tickets déjà clos dans le cache → ignorés (source statique, ne changent plus)
    changed = [
        t for t in current
        if not (t.code in cached_lookup and is_closed(cached_lookup[t.code].status))
        and (
            t.code not in cached_lookup
            or cached_lookup[t.code].status != t.status
            or cached_lookup[t.code].updated_at != t.updated_at
        )
    ]

    # 4. Deepdive pour les tickets changés
    final_by_code = {t.code: t for t in current}
    changed_codes = {t.code for t in changed}
    change_details = []

    for t in changed:
        old = cached_lookup.get(t.code)
        change_details.append({
            "id": t.id,
            "code": t.code,
            "title": t.titre or t.code,
            "old_status": old.status if old else None,
            "new_status": t.status,
        })
        try:
            msgs = client.get_enriched_messages(t.id)
            ticket_obj = final_by_code[t.code]
            closed = is_closed(ticket_obj.status)
            _store.put(_key_messages_enriched(t.id), _ser_messages(msgs), permanent=closed)
            if not closed:
                ticket_obj.gie_relance = _is_gie_relance(msgs)
        except Exception as e:
            logger.warning(f"Failed to enrich messages for ticket {t.id}: {e}")

    # 5. gie_relance pour les tickets "En attente" inchangés
    waiting_tickets = [
        t for t in current
        if "attente" in t.status.lower() and t.code not in changed_codes
    ]
    for t in waiting_tickets:
        try:
            msgs = client.get_messages(t.id)
            final_by_code[t.code].gie_relance = _is_gie_relance(msgs)
        except Exception:
            pass

    # 6. Préserve gie_relance pour les tickets inchangés hors "En attente"
    waiting_codes = {t.code for t in waiting_tickets}
    enriched_codes = changed_codes | waiting_codes
    for code, t in final_by_code.items():
        if code not in enriched_codes and code in cached_lookup:
            t.gie_relance = cached_lookup[code].gie_relance

    # 7. Persiste la liste mise à jour
    ticket_list = list(final_by_code.values())
    _store.put(_KEY_ALL, _ser_tickets(ticket_list))
    prepopulate_closed(ticket_list)

    last_refresh = {
        "timestamp": time.time(),
        "changes": change_details,
    }

    return len(changed)
