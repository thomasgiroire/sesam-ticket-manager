"""
portal.py – Client pour le Portail IRIS (SESAM-Vitale)
=======================================================
API découverte par reverse-engineering du portail réel.

Application : JHipster Angular 11
Base URL    : https://portail-support.sesam-vitale.fr/gsvextranet/api

Endpoints confirmés :
  POST /api/authenticate               → login (cookie session)
  GET  /api/account                    → infos utilisateur connecté
  GET  /api/requests/company           → liste tous les tickets de la société
  GET  /api/requests/{id}              → détail d'un ticket (id hexadécimal)
  GET  /api/requests/{id}/messages     → messages d'un ticket (nbOfResult sans 's')
  GET  /api/requests/{id}/messages/attachments → pièces jointes
  POST /api/requests/{id}/messages     → ajouter un message (title + description)
  GET  /api/refvalues?tableCode=Tt_    → types de tickets
  GET  /api/refvalues?tableCode=Rst    → statuts
  GET  /api/requests/services          → services disponibles
  GET  /api/requests/qualifications    → qualifications

Champs ticket : id (hex), code (ex: 26-083-026025), titre, description,
                status.{code,label}, priority.{code,label}, typeTicket.{code,label},
                service, qualification, person.{firstName,lastName},
                createdAt, updatedAt, closedAt

Champs message : id, title, description, type.{code,label},
                 attachments, createdAt, updatedAt
"""

import json
import logging
import re
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from dataclasses import dataclass, field, asdict

import requests

from config import load_config, PortalConfig
from exceptions import AuthError, APIError, LoginError, SessionExpiredError, StateError
from utils import get_logger, validate_ticket_code

# Import file locking (platform-specific)
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

logger = get_logger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────

# URL de base publique — constante non sensible, gardée au niveau module
# pour permettre les imports directs (ex: portal.API_BASE)
PORTAL_BASE = "https://portail-support.sesam-vitale.fr/gsvextranet"
API_BASE    = f"{PORTAL_BASE}/api"
LOGIN_URL   = f"{API_BASE}/authenticate"

# Valeurs par défaut pour STATE_FILE (utilisé par PortalState sans config injectée)
_DEFAULT_STATE_FILE = Path(".sesam_state.json")

# ─── Utilitaires HTML ────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """
    Convertit du HTML en texte brut lisible.

    Handles block-level tags by inserting newlines, strips all HTML tags,
    and decodes HTML entities. Handles malformed HTML gracefully.
    """
    _BLOCK_TAGS = frozenset({
        "p", "br", "div", "li", "tr", "td", "th",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "hr", "ul", "ol", "table",
    })

    def __init__(self):
        """Initialise le parser avec une liste vide de fragments texte."""
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data):
        """Accumule le texte brut rencontré entre les balises."""
        self._parts.append(data)

    def handle_starttag(self, tag, attrs):
        """Insère un saut de ligne avant les balises de bloc."""
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        """Insère un saut de ligne après les balises de bloc."""
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_comment(self, data):
        """Ignore HTML comments."""
        pass

    def get_text(self) -> str:
        """Retourne le texte accumulé, nettoyé des espaces excessifs."""
        text = "".join(self._parts)
        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def error(self, message):
        """Override to prevent raising on malformed HTML."""
        logger.debug(f"HTML parser encountered issue: {message}")


def strip_html(html: str) -> str:
    """
    Retire les balises HTML et décode les entités HTML.

    Handles malformed HTML, CDATA sections, and comments gracefully.
    Falls back to regex stripping if the parser fails.

    Args:
        html: HTML string to strip

    Returns:
        Plain text with HTML removed
    """
    if not html or not html.strip():
        return ""
    # Si pas de HTML, retourner tel quel
    if "<" not in html:
        return html
    stripper = _HTMLStripper()
    try:
        stripper.feed(html)
        result = stripper.get_text()
        stripper.close()
        return result
    except Exception as e:
        logger.debug(f"HTML parser failed ({e}), falling back to regex")
        # Improved regex fallback: handle comments, CDATA, and tags
        text = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)  # comments
        text = re.sub(r"<!\[CDATA\[.*?\]\]>", "", text, flags=re.DOTALL)  # CDATA
        text = re.sub(r"<[^>]+>", "", text)  # tags
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def sanitize_html(html: str) -> str:
    """
    Nettoie le HTML en supprimant les balises dangereuses (script, style)
    et les attributs d'événement (on*), mais préserve les images et le formatage.
    """
    if not html or "<" not in html:
        return html
    # Supprimer <script> et <style> avec leur contenu
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Supprimer les attributs d'événement (onclick, onload, onerror, etc.)
    html = re.sub(r'\s+on\w+\s*=\s*"[^"]*"', "", html, flags=re.IGNORECASE)
    html = re.sub(r"\s+on\w+\s*=\s*'[^']*'", "", html, flags=re.IGNORECASE)
    # Supprimer javascript: dans les attributs href/src
    html = re.sub(r'(href|src)\s*=\s*"javascript:[^"]*"', '', html, flags=re.IGNORECASE)
    return html.strip()


# ─── Data models ────────────────────────────────────────────────────────────

@dataclass
class Ticket:
    id: str           # ID hexadécimal interne ex: "00294000001e8cbd"
    code: str         # Référence affichée ex: "26-083-026025"
    titre: str        # Titre du ticket
    status: str       # Label du statut ex: "En cours"
    status_code: str  # Code du statut ex: "ENCOURS"
    priority: str     # Label de la priorité ex: "Normal"
    type_ticket: str  # "Incident" ou "Demande"
    service: str      # Service concerné
    qualification: str
    author: str       # Prénom Nom du demandeur
    created_at: str
    updated_at: str
    closed_at: str       = ""
    service_id: str      = ""
    qualification_id: str = ""
    description: str  = ""
    messages: list    = field(default_factory=list)
    raw: dict         = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Sérialise le ticket en dict JSON-compatible (sans le champ raw)."""
        d = asdict(self)
        d.pop("raw", None)
        return d

    def short_repr(self) -> str:
        """Représentation courte sur une ligne : [code] statut | titre (60 car.)."""
        return f"[{self.code}] {self.status:18s} | {self.titre[:60]}"


@dataclass
class Message:
    id: str
    title: str
    body: str
    type_code: str    # ex: "INEXTRANET"
    type_label: str   # ex: "Extranet entrant"
    created_at: str
    attachments: list = field(default_factory=list)
    body_html: str    = ""   # HTML nettoyé (scripts supprimés, img préservées)


# ─── State persistant ────────────────────────────────────────────────────────

class PortalState:
    """
    Sauvegarde les cookies et l'état de synchro entre les sessions.

    Uses atomic writes and file locking to prevent corruption when multiple
    CLI instances access the state file simultaneously.
    """

    def __init__(self, path: Path = _DEFAULT_STATE_FILE):
        """
        Initialise l'état persistant depuis le fichier JSON indiqué.

        Args:
            path: Chemin du fichier d'état (défaut : STATE_FILE env var)
        """
        self.path = path
        self._data: dict = {}
        self._lock_file = path.parent / f".{path.name}.lock"
        self._lock_handle = None
        self._load()

    def _acquire_lock(self, timeout: float = 10.0):
        """
        Acquire exclusive lock on state file.

        Args:
            timeout: Maximum time to wait for lock

        Raises:
            StateError: If lock cannot be acquired within timeout
        """
        start = time.time()
        while True:
            try:
                if sys.platform == "win32":
                    # Windows: use file opening in exclusive mode
                    self._lock_handle = open(self._lock_file, "w")
                    msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    # Unix: use fcntl
                    self._lock_handle = open(self._lock_file, "w")
                    fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("Acquired state file lock")
                return
            except (IOError, OSError):
                if time.time() - start > timeout:
                    raise StateError(f"Could not acquire state file lock within {timeout}s")
                time.sleep(0.1)

    def _release_lock(self):
        """Release lock on state file."""
        if self._lock_handle:
            try:
                if sys.platform == "win32":
                    msvcrt.locking(self._lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
                self._lock_handle.close()
                self._lock_handle = None
                logger.debug("Released state file lock")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")

    def _atomic_write(self, data: dict):
        """
        Atomically write state to file.

        Writes to a temporary file first, then renames it to the target file.
        This ensures the state file is never left in a corrupted state.

        Args:
            data: Data to write

        Raises:
            StateError: If write fails
        """
        try:
            self._acquire_lock()
            try:
                # Write to temporary file
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=self.path.parent,
                    delete=False,
                    suffix=".tmp"
                ) as tmp:
                    json.dump(data, tmp, indent=2)
                    tmp_path = tmp.name

                # Atomically rename temp file to target
                Path(tmp_path).replace(self.path)
                logger.debug(f"Atomically wrote state file: {self.path}")
            finally:
                self._release_lock()
        except StateError:
            raise
        except Exception as e:
            raise StateError(f"Failed to write state file: {e}")

    def _load(self):
        """Load state from file."""
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
                logger.debug(f"Loaded state from {self.path}")
            except json.JSONDecodeError as e:
                logger.warning(f"State file corrupted ({e}), starting fresh")
                self._data = {}
            except Exception as e:
                logger.warning(f"Error loading state file ({e}), starting fresh")
                self._data = {}

    def save(self):
        """Save state to file using atomic write."""
        self._atomic_write(self._data)

    @property
    def cookies(self) -> dict:
        """Get stored session cookies."""
        return self._data.get("cookies", {})

    @cookies.setter
    def cookies(self, value: dict):
        """Sauvegarde les cookies de session et persiste l'état sur disque."""
        self._data["cookies"] = value
        self.save()

    @property
    def known_tickets(self) -> dict:
        """
        Get dict of known tickets: {code → updated_at} for detecting changes.
        """
        return self._data.get("known_tickets", {})

    @known_tickets.setter
    def known_tickets(self, value: dict):
        """Sauvegarde le dictionnaire de tickets connus et persiste l'état sur disque."""
        self._data["known_tickets"] = value
        self.save()

    def update_known_tickets(self, tickets: list):
        """
        Update known tickets with current ticket states.

        Args:
            tickets: List of Ticket objects to track
        """
        current = self.known_tickets
        for t in tickets:
            current[t.code] = t.updated_at
        self.known_tickets = current
        logger.info(f"Updated {len(tickets)} known tickets in state")

    def get_new_or_updated(self, tickets: list) -> list:
        """
        Identify new or updated tickets by comparing with known state.

        Args:
            tickets: List of Ticket objects to check

        Returns:
            List of tickets that are new or have been updated
        """
        known = self.known_tickets
        new_or_updated = [
            t for t in tickets
            if t.code not in known or known[t.code] != t.updated_at
        ]
        logger.info(f"Found {len(new_or_updated)} new/updated tickets from {len(tickets)} total")
        return new_or_updated


# ─── Client HTTP ─────────────────────────────────────────────────────────────

class PortalClient:
    """
    Client HTTP direct pour l'API REST du Portail IRIS.
    Authentification par session cookie (JHipster).
    """

    def __init__(self, config: PortalConfig | None = None):
        """
        Initialise le client HTTP avec les cookies de session sauvegardés.

        Args:
            config: Configuration du portail. Si None, chargée depuis load_config().

        Charge l'état persistant (PortalState) et restaure les cookies
        de session dans la requête HTTP pour éviter un re-login.
        """
        self._config = config or load_config().portal
        self.state = PortalState(Path(self._config.state_file))
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        })
        # Charger les cookies sauvegardés
        if self.state.cookies:
            for name, value in self.state.cookies.items():
                self._session.cookies.set(name, value)
        # Cache des services (id → label) pour résoudre les labels
        self._services_cache: dict[str, str] = {}

    # ── Auth ──────────────────────────────────────────────────────────────

    def login(self, max_retries: int = 3) -> bool:
        """
        Authentification via POST /api/authenticate.
        Stocke les cookies de session pour les appels suivants.

        Args:
            max_retries: Maximum number of login attempts

        Returns:
            True if login successful

        Raises:
            LoginError: If login fails after max retries
            AuthError: If credentials are missing or invalid
        """
        if not self._config.username or not self._config.password:
            raise AuthError(
                "SESAM_USERNAME et SESAM_PASSWORD doivent être définis dans le fichier .env"
            )

        payload = {
            "username": self._config.username,
            "password": self._config.password,
            "rememberMe": True,
        }

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Login attempt {attempt + 1}/{max_retries} for user {self._config.username}"
                )
                resp = self._session.post(self._config.login_url, json=payload, timeout=15)

                if resp.status_code == 401:
                    raise AuthError("Identifiants incorrects (401). Vérifiez SESAM_USERNAME et SESAM_PASSWORD.")
                if resp.status_code == 403:
                    raise AuthError("Accès refusé (403).")
                if not resp.ok:
                    logger.warning(
                        f"Login failed with status {resp.status_code}: {resp.text[:200]}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # exponential backoff
                        continue
                    raise AuthError(f"Erreur de connexion ({resp.status_code}) : {resp.text[:200]}")

                # Success: save session cookies
                self.state.cookies = dict(self._session.cookies)
                logger.info(f"✓ Successfully logged in as {self._config.username}")
                return True

            except AuthError:
                raise
            except requests.RequestException as e:
                logger.warning(f"Network error during login: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise LoginError(f"Unable to contact portal after {max_retries} attempts: {e}")

        raise LoginError(f"Login failed after {max_retries} attempts")

    def _ensure_logged_in(self):
        """
        Vérifie la session ; se reconnecte si nécessaire.

        Raises:
            LoginError: If session validation or login fails
        """
        if not self.state.cookies:
            logger.debug("No session cookies found, logging in...")
            self.login()
            return

        # Verify that the session is still valid
        try:
            logger.debug("Validating session...")
            resp = self._session.get(f"{API_BASE}/account", timeout=10)
            if resp.status_code == 401:
                logger.warning("Session expired, attempting reconnect...")
                self.state.cookies = {}
                self._session.cookies.clear()
                self.login()
            elif not resp.ok:
                logger.warning(f"Session validation failed with status {resp.status_code}")
                self.login()
            else:
                logger.debug("Session is valid")
        except requests.RequestException as e:
            logger.warning(f"Error validating session: {e}, attempting reconnect...")
            self.login()

    def _get(self, path: str, params: dict = None) -> dict:
        """
        Execute GET request with error handling and logging.

        Args:
            path: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            SessionExpiredError: If session has expired (401)
            APIError: If request fails
        """
        url = f"{API_BASE}{path}"
        logger.debug(f"GET {path} with params={params}")
        try:
            resp = self._session.get(url, params=params, timeout=20)
            if resp.status_code == 401:
                logger.warning(f"Session expired on GET {path}")
                raise SessionExpiredError("Session expirée")
            if not resp.ok:
                logger.error(
                    f"GET {path} failed with {resp.status_code}: {resp.text[:300]}"
                )
                raise APIError(f"GET {path} → {resp.status_code}: {resp.text[:300]}")
            logger.debug(f"GET {path} successful")
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Network error on GET {path}: {e}")
            raise APIError(f"Network error on GET {path}: {e}")

    def _post(self, path: str, data: dict) -> dict:
        """
        Execute POST request with error handling and logging.

        Args:
            path: API endpoint path
            data: Request payload

        Returns:
            Parsed JSON response or empty dict if no response

        Raises:
            SessionExpiredError: If session has expired (401)
            APIError: If request fails
        """
        url = f"{API_BASE}{path}"
        logger.debug(f"POST {path} with data keys={list(data.keys())}")
        try:
            resp = self._session.post(url, json=data, timeout=20)
            if resp.status_code == 401:
                logger.warning(f"Session expired on POST {path}")
                raise SessionExpiredError("Session expirée")
            if not resp.ok:
                logger.error(
                    f"POST {path} failed with {resp.status_code}: {resp.text[:300]}"
                )
                raise APIError(f"POST {path} → {resp.status_code}: {resp.text[:300]}")
            logger.debug(f"POST {path} successful")
            return resp.json() if resp.text else {}
        except requests.RequestException as e:
            logger.error(f"Network error on POST {path}: {e}")
            raise APIError(f"Network error on POST {path}: {e}")

    def _put(self, path: str, data: dict | None = None) -> dict:
        """Execute PUT request — même pattern que _post. data=None envoie un body null."""
        url = f"{API_BASE}{path}"
        logger.debug(f"PUT {path} with data={data}")
        try:
            resp = self._session.put(url, json=data, timeout=20)
            if resp.status_code == 401:
                raise SessionExpiredError("Session expirée")
            if not resp.ok:
                raise APIError(f"PUT {path} → {resp.status_code}: {resp.text[:300]}")
            logger.debug(f"PUT {path} successful")
            return resp.json() if resp.text else {}
        except requests.RequestException as e:
            raise APIError(f"Network error on PUT {path}: {e}")

    # ── Tickets ───────────────────────────────────────────────────────────

    def list_tickets(
        self,
        include_closed: bool = False,
        page: int = 1,
        limit: int = 50,
        order_by: str = "DmdCrDt",
        order_dir: str = " DESC",
        status_code: str = None,
        type_code: str = None,
        requester: str = None,
        title: str = None,
        date_from: str = None,
        date_to: str = None,
        fetch_all: bool = False,
    ) -> list[Ticket]:
        """
        Liste les tickets de la société.

        Paramètres de l'API :
          notClosed     : true/false (masquer les clos)
          fromPageNumber: page (débute à 1)
          nbOfResults   : nombre de résultats par page
          orderBy       : champ de tri (DmdCrDt, DmdUpDt…)
          orderWay      : " DESC" ou " ASC"

        Args:
            fetch_all: If True, auto-paginate to fetch ALL tickets
                       (loops while hasNextPage=True, max 20 pages)
        """
        self._ensure_logged_in()

        params = {
            "fromPageNumber": page,
            "nbOfResults": limit,
            "orderWay": order_dir,
            "orderBy": order_by,
        }
        if not include_closed:
            params["notClosed"] = "true"
        if status_code:
            params["status"] = status_code
        if type_code:
            params["type"] = type_code
        if requester:
            params["requester"] = requester
        if title:
            params["title"] = title
        if date_from:
            params["createdAtStart"] = date_from
        if date_to:
            params["createdAtEnd"] = date_to

        all_tickets = []
        max_pages = 20  # Safety cap to prevent infinite loops
        current_page = page

        while True:
            params["fromPageNumber"] = current_page

            try:
                data = self._get("/requests/company", params=params)
            except SessionExpiredError:
                logger.info("Session expired, attempting to re-login...")
                self.state.cookies = {}
                self._session.cookies.clear()
                self.login()
                data = self._get("/requests/company", params=params)

            page_tickets = [self._parse_ticket(t) for t in data.get("objectsList", [])]
            all_tickets.extend(page_tickets)

            has_next = data.get("hasNextPage", False)
            logger.info(
                f"Page {current_page}: {len(page_tickets)} tickets "
                f"(total so far: {len(all_tickets)}, hasNextPage={has_next})"
            )

            if not fetch_all or not has_next or current_page >= max_pages:
                break

            current_page += 1

        logger.info(f"Retrieved {len(all_tickets)} tickets total ({current_page - page + 1} page(s))")
        return all_tickets

    def get_ticket(self, ticket_id: str) -> Ticket:
        """
        Récupère le détail d'un ticket par son ID hexadécimal.
        Pour trouver l'ID depuis une référence (ex: 26-083-026025),
        utilisez d'abord list_tickets() et filtrez sur .code.
        """
        self._ensure_logged_in()
        data = self._get(f"/requests/{ticket_id}")
        ticket = self._parse_ticket(data)

        # Charger aussi les messages
        try:
            msgs = self.get_messages(ticket_id)
            ticket.messages = msgs
        except Exception as e:
            logger.warning(f"Failed to load messages for ticket {ticket_id}: {e}")

        return ticket

    def get_ticket_by_code(self, code: str) -> "Ticket | None":
        """
        Trouve un ticket par sa référence affichée (ex: 26-083-026025),
        tous statuts confondus (ouvert ou clos).

        Args:
            code: Ticket code in format XX-XXX-XXXXXX

        Returns:
            Ticket si trouvé, None sinon

        Raises:
            ValidationError: If code format is invalid
        """
        validate_ticket_code(code)
        logger.debug(f"Searching for ticket by code: {code}")
        tickets = self.list_tickets(include_closed=True, fetch_all=True)
        for t in tickets:
            if t.code == code:
                logger.debug(f"Found ticket {code}, fetching details")
                return self.get_ticket(t.id)
        logger.warning(f"Ticket not found: {code}")
        return None

    def get_messages(self, ticket_id: str, page: int = 1, limit: int = 50) -> list[Message]:
        """
        Récupère les messages d'un ticket.
        IMPORTANT : le paramètre s'appelle 'nbOfResult' (sans 's') !
        """
        self._ensure_logged_in()
        params = {
            "fromPageNumber": page,
            "nbOfResult": limit,   # ← sans 's' ! (confirmé par reverse-engineering)
        }
        data = self._get(f"/requests/{ticket_id}/messages", params=params)
        return [self._parse_message(m) for m in data.get("objectsList", [])]

    def get_enriched_messages(self, ticket_id: str, limit: int = 100) -> list[Message]:
        """
        Récupère les messages d'un ticket et enrichit les pièces jointes avec
        leurs métadonnées complètes (nom, type MIME) via l'endpoint dédié.

        Endpoint pièces jointes :
          GET /api/requests/{id}/messages/attachments
          Retourne : {message_id: [{id, name, contentType, ...}]}
        """
        messages = self.get_messages(ticket_id, limit=limit)

        try:
            resp = self._session.get(
                f"{API_BASE}/requests/{ticket_id}/messages/attachments", timeout=15
            )
            att_map: dict = resp.json() if resp.ok else {}
        except Exception as e:
            logger.warning(f"Failed to fetch attachment metadata for ticket {ticket_id}: {e}")
            att_map = {}

        for msg in messages:
            if msg.attachments and att_map.get(msg.id):
                enriched = {a["id"]: a for a in att_map[msg.id] if a.get("id")}
                msg.attachments = [
                    enriched.get(a.get("id") if isinstance(a, dict) else a, a)
                    for a in msg.attachments
                ]

        return messages

    def add_message(self, ticket_id: str, title: str, body: str) -> Message:
        """
        Ajoute un message (commentaire) à un ticket.
        Endpoint : POST /messages avec linkedRequest.id
        (/requests/{id}/messages n'accepte que GET — Allow: GET,HEAD,OPTIONS)
        """
        self._ensure_logged_in()
        payload = {
            "title": title,
            "description": body,
            "linkedRequest": {"id": ticket_id},
        }
        data = self._post("/messages", payload)
        return self._parse_message(data) if data else Message(
            id="", title=title, body=body, type_code="", type_label="",
            created_at="", attachments=[]
        )

    def resolve_ticket(self, ticket_id: str) -> bool:
        """
        Résout un ticket sur le portail GIE.
        Endpoint (reverse-engineered depuis main.bundle.js) :
          PUT /requests/{id}/solve   body: null
        """
        self._ensure_logged_in()
        self._put(f"/requests/{ticket_id}/solve", None)
        return True

    # ID de type ticket pour DEMANDE (observé dans le HAR)
    _TYPE_TICKET_DEMANDE = {"id": "0002300000033a2f", "code": "DEMANDE", "label": "Demande"}

    def upload_files(self, files: list) -> list:
        """
        Upload multiple fichiers vers POST /api/upload/multiple.
        files = [(nom, contenu_bytes, content_type, description), ...]
        Retourne la liste des objets attachment : [{id, name, description, contentType, ...}]
        """
        self._ensure_logged_in()
        url = f"{API_BASE}/upload/multiple"
        parts = []
        for nom, contenu, ctype, description in files:
            parts.append(("data", (nom, contenu, ctype or "application/octet-stream")))
            parts.append(("description", (None, description or "")))
        resp = self._session.post(url, files=parts, timeout=60)
        if resp.status_code == 401:
            raise SessionExpiredError("Session expirée")
        if not resp.ok:
            raise APIError(f"Upload échoué ({resp.status_code}): {resp.text[:200]}")
        return resp.json()

    def create_ticket(
        self,
        source: str,          # "DEMANDE" ou "INCIDENT"
        titre: str,
        description: str,
        service_id: str = None,
        qualification_id: str = None,
        priority_code: str = "AVERAGE",
        attachments: list = None,
    ) -> "Ticket":
        """
        Crée un nouveau ticket.
        source = "DEMANDE" (Nouvelle demande) ou "INCIDENT" (Nouvel incident)
        attachments = liste d'objets retournés par upload_files()
        """
        self._ensure_logged_in()
        payload = {
            "titre": titre,
            "description": description,
            "typeTicket": self._TYPE_TICKET_DEMANDE,
            "priority": {"code": priority_code},
        }
        if service_id:
            payload["service"] = {"id": service_id}
        if qualification_id:
            payload["qualification"] = {"id": qualification_id}
        if attachments:
            payload["attachments"] = attachments

        data = self._post("/requests", payload)
        if data:
            return self._parse_ticket(data)

        raise APIError("Impossible de créer le ticket. Vérifiez les paramètres.")

    def get_services(self) -> list[dict]:
        """Liste les services disponibles."""
        self._ensure_logged_in()
        return self._get("/requests/services")

    def _load_services_cache(self):
        """
        Charge le cache id→label des services (appelé une seule fois).

        Services are cached in memory for the lifetime of the PortalClient instance.
        """
        if self._services_cache:
            logger.debug(f"Services cache already loaded ({len(self._services_cache)} entries)")
            return
        try:
            logger.debug("Loading services cache...")
            services = self._get("/requests/services")
            if isinstance(services, list):
                for s in services:
                    if isinstance(s, dict) and s.get("id"):
                        label = s.get("label") or s.get("name") or s.get("code") or ""
                        self._services_cache[s["id"]] = label
                logger.info(f"Loaded {len(self._services_cache)} services into cache")
        except Exception as e:
            logger.warning(f"Failed to load services cache: {e}. Service labels may be missing.")

    def _resolve_service_label(self, service_raw) -> str:
        """Résout le label d'un service depuis l'objet API."""
        if not service_raw:
            return ""
        if isinstance(service_raw, str):
            return service_raw
        if isinstance(service_raw, dict):
            # Certaines réponses ont directement le label
            label = service_raw.get("label") or service_raw.get("name")
            if label:
                return str(label)
            # Sinon résoudre par ID via le cache
            sid = service_raw.get("id")
            if sid:
                if not self._services_cache:
                    self._load_services_cache()
                return self._services_cache.get(sid, service_raw.get("code", ""))
        return ""

    def get_qualifications(self) -> list[dict]:
        """Liste les qualifications disponibles."""
        self._ensure_logged_in()
        return self._get("/requests/qualifications", params={"all": "true"})

    def get_statuses(self) -> list[dict]:
        """Liste les statuts (table Rst)."""
        self._ensure_logged_in()
        return self._get("/refvalues", params={"tableCode": "Rst"})

    def get_account(self) -> dict:
        """Informations sur l'utilisateur connecté."""
        self._ensure_logged_in()
        return self._get("/account")

    # ── Suivi des nouveautés ──────────────────────────────────────────────

    def get_new_or_updated(self, tickets: list[Ticket] = None) -> list[Ticket]:
        """
        Retourne les tickets nouveaux ou modifiés depuis la dernière synchro.

        Si `tickets` n'est pas fourni, récupère d'abord la liste courante.
        Délègue la comparaison à PortalState.get_new_or_updated().
        """
        if tickets is None:
            tickets = self.list_tickets()
        return self.state.get_new_or_updated(tickets)

    def mark_synced(self, tickets: list[Ticket]):
        """Marque les tickets comme synchronisés en mettant à jour l'état persistant."""
        self.state.update_known_tickets(tickets)

    # ── Parsing ───────────────────────────────────────────────────────────

    def _parse_ticket(self, data: dict) -> Ticket:
        """Convertit un objet API en Ticket normalisé."""
        status_raw  = data.get("status") or {}
        priority_raw = data.get("priority") or {}
        type_raw    = data.get("typeTicket") or {}
        service_raw = data.get("service") or {}
        qualif_raw  = data.get("qualification") or {}
        person_raw  = data.get("person") or {}

        # Titre : le champ s'appelle 'titre' (pas 'title' !)
        titre = str(data.get("titre") or data.get("title") or "")

        # Auteur
        first = person_raw.get("firstName", "")
        last  = person_raw.get("lastName", "")
        author = f"{first} {last}".strip() if (first or last) else ""

        # Service : résolution via cache si pas de label direct
        service = self._resolve_service_label(service_raw)

        # Qualification
        if isinstance(qualif_raw, dict):
            qualification = qualif_raw.get("label") or qualif_raw.get("code") or ""
        else:
            qualification = str(qualif_raw) if qualif_raw else ""

        return Ticket(
            id            = str(data.get("id", "")),
            code          = str(data.get("code", "")),
            titre         = titre,
            status        = status_raw.get("label", "") if isinstance(status_raw, dict) else str(status_raw),
            status_code   = status_raw.get("code", "") if isinstance(status_raw, dict) else "",
            priority      = priority_raw.get("label", "") if isinstance(priority_raw, dict) else str(priority_raw),
            type_ticket   = type_raw.get("label", "") if isinstance(type_raw, dict) else str(type_raw),
            service       = service,
            service_id    = service_raw.get("id", "") if isinstance(service_raw, dict) else "",
            qualification = qualification,
            qualification_id = qualif_raw.get("id", "") if isinstance(qualif_raw, dict) else "",
            author        = author,
            created_at    = str(data.get("createdAt", "")),
            updated_at    = str(data.get("updatedAt", "")),
            closed_at     = str(data.get("closedAt") or ""),
            description   = str(data.get("description") or ""),
            raw           = data,
        )

    def _parse_message(self, data: dict) -> Message:
        """Convertit un objet API en Message normalisé. Nettoie le HTML du corps."""
        type_raw = data.get("type") or {}
        raw_body = str(data.get("description") or "")
        return Message(
            id         = str(data.get("id", "")),
            title      = str(data.get("title") or ""),
            body       = strip_html(raw_body),
            body_html  = sanitize_html(raw_body),
            type_code  = type_raw.get("code", "") if isinstance(type_raw, dict) else "",
            type_label = type_raw.get("label", "") if isinstance(type_raw, dict) else str(type_raw),
            created_at = str(data.get("createdAt", "")),
            attachments= data.get("attachments") or [],
        )


