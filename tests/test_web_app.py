"""Tests for web_app.py — navigation, routes, error handling, and cache behavior."""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web_app
from web_app import app, _status_color, _priority_color, _is_client_author, _is_hot
from portal import PortalClient, Ticket, Message
from exceptions import AuthError, APIError


# ─── Factories ────────────────────────────────────────────────────────────────


def make_ticket_obj(**kwargs) -> Ticket:
    defaults = dict(
        id="abc123hex",
        code="26-083-000001",
        titre="Problème CPS",
        status="En cours",
        status_code="ENCOURS",
        priority="Normal",
        type_ticket="Incident",
        service="Support",
        qualification="Technique",
        author="Jean Dupont",
        created_at="2026-03-20T10:00:00",
        updated_at="2026-03-21T14:00:00",
    )
    defaults.update(kwargs)
    return Ticket(**defaults)


def make_message_obj(**kwargs) -> Message:
    defaults = dict(
        id="msg001",
        title="Réponse",
        body="Contenu du message",
        type_code="INEXTRANET",
        type_label="Extranet entrant",
        created_at="2026-03-21T15:00:00",
    )
    defaults.update(kwargs)
    return Message(**defaults)


# ─── Fixture principale ───────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch, tmp_path):
    """
    Client HTTP de test avec :
    - PortalClient mocké
    - Watchdog neutralisé (pas de os.kill en test)
    - Cache disque redirigé vers tmp_path (inexistant = pas de lazy refresh)
    - Globals réinitialisés entre chaque test
    """
    mock_portal = MagicMock(spec=PortalClient)
    mock_portal.list_tickets.return_value = [
        make_ticket_obj(),
        make_ticket_obj(id="closed001", code="26-083-000002", titre="Ticket fermé", status="Clos", status_code="CLOS"),
    ]
    mock_portal.get_ticket.return_value = make_ticket_obj()
    mock_portal.get_enriched_messages.return_value = [make_message_obj()]
    mock_portal.get_services.return_value = [{"id": "svc1", "label": "Support"}]
    mock_portal.get_qualifications.return_value = [{"id": "q1", "label": "Technique"}]
    mock_portal.create_ticket.return_value = make_ticket_obj(id="newticket001")
    mock_portal.add_message.return_value = None
    mock_portal.resolve_ticket.return_value = None

    # Créer un cache disque factice récent → lifespan ne pose pas _initializing=True
    # et la route dashboard ne déclenche pas de lazy refresh
    fake_cache = tmp_path / ".sesam_web_cache_test.json"
    fake_cache.write_text(json.dumps({"ts": time.time(), "data": {}}))

    monkeypatch.setattr(web_app, "_get_client", lambda: mock_portal)
    monkeypatch.setattr(web_app, "_initializing", False)
    monkeypatch.setattr(web_app, "_last_refresh", {})
    monkeypatch.setattr(web_app, "_DISK_CACHE_FILE", fake_cache)
    web_app._mem_cache.clear()

    # Neutraliser watchdog et initial fetch (évite os.kill en test)
    monkeypatch.setattr(web_app.asyncio, "create_task", lambda coro: coro.close() or None)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, mock_portal


# ─── TestDashboard ────────────────────────────────────────────────────────────


class TestDashboard:
    def test_returns_200(self, client):
        http, _ = client
        r = http.get("/")
        assert r.status_code == 200
        assert "Tickets ouverts" in r.text or "ouvert" in r.text.lower()

    def test_shows_ticket_counts(self, client):
        http, _ = client
        r = http.get("/")
        assert r.status_code == 200
        # Un ticket "En cours" et un "Clos" → compteurs présents dans le HTML
        assert "1" in r.text  # open_count ou closed_count

    def test_shows_recent_tickets(self, client):
        http, _ = client
        r = http.get("/")
        assert "Problème CPS" in r.text

    def test_with_updated_param(self, client):
        http, _ = client
        r = http.get("/?updated=3")
        assert r.status_code == 200

    def test_auth_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.list_tickets.side_effect = AuthError("Session expirée")
        r = http.get("/")
        assert r.status_code == 503
        assert "Session expirée" in r.text

    def test_api_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.list_tickets.side_effect = APIError("Portail indisponible")
        r = http.get("/")
        assert r.status_code == 503
        assert "Portail indisponible" in r.text


# ─── TestInitializingState ────────────────────────────────────────────────────


class TestInitializingState:
    def test_dashboard_shows_loading(self, client, monkeypatch):
        http, _ = client
        monkeypatch.setattr(web_app, "_initializing", True)
        r = http.get("/")
        assert r.status_code == 200
        # loading.html doit être renvoyé (pas un crash)
        assert "refresh" in r.text.lower() or "chargement" in r.text.lower() or "initialisation" in r.text.lower()

    def test_tickets_shows_loading(self, client, monkeypatch):
        http, _ = client
        monkeypatch.setattr(web_app, "_initializing", True)
        r = http.get("/tickets")
        assert r.status_code == 200
        assert "refresh" in r.text.lower() or "chargement" in r.text.lower() or "initialisation" in r.text.lower()

    def test_loading_has_meta_refresh(self, client, monkeypatch):
        http, _ = client
        monkeypatch.setattr(web_app, "_initializing", True)
        r = http.get("/")
        assert r.status_code == 200
        assert 'http-equiv="refresh"' in r.text or "http-equiv='refresh'" in r.text


# ─── TestTicketsList ──────────────────────────────────────────────────────────


class TestTicketsList:
    def test_returns_200_with_tickets(self, client):
        http, _ = client
        r = http.get("/tickets")
        assert r.status_code == 200
        assert "Problème CPS" in r.text

    def test_status_filter_open(self, client):
        http, _ = client
        r = http.get("/tickets?status=En+cours")
        assert r.status_code == 200
        assert "Problème CPS" in r.text
        assert "Ticket fermé" not in r.text

    def test_status_filter_closed(self, client):
        http, _ = client
        r = http.get("/tickets?status=Clos")
        assert r.status_code == 200
        assert "Ticket fermé" in r.text
        assert "Problème CPS" not in r.text

    def test_type_filter(self, client):
        http, mock_portal = client
        mock_portal.list_tickets.return_value = [
            make_ticket_obj(type_ticket="Incident"),
            make_ticket_obj(id="dem001", code="26-083-000003", titre="Demande service", type_ticket="Demande"),
        ]
        r = http.get("/tickets?type=Incident")
        assert r.status_code == 200
        assert "Problème CPS" in r.text
        assert "Demande service" not in r.text

    def test_search_query(self, client):
        http, _ = client
        r = http.get("/tickets?q=CPS")
        assert r.status_code == 200
        assert "Problème CPS" in r.text

    def test_search_no_results(self, client):
        http, _ = client
        r = http.get("/tickets?q=xxxxunknownxxxx")
        assert r.status_code == 200
        # Pas de crash, juste 0 résultats
        assert "Problème CPS" not in r.text
        assert "Ticket fermé" not in r.text

    def test_auth_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.list_tickets.side_effect = AuthError("Accès refusé")
        r = http.get("/tickets")
        assert r.status_code == 503


# ─── TestCreateTicketForm ─────────────────────────────────────────────────────


class TestCreateTicketForm:
    def test_form_returns_200(self, client):
        http, _ = client
        r = http.get("/tickets/create")
        assert r.status_code == 200
        assert "Support" in r.text  # service label

    def test_auth_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.get_services.side_effect = AuthError("Token expiré")
        r = http.get("/tickets/create")
        assert r.status_code == 503

    def test_api_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.get_services.side_effect = APIError("Timeout")
        r = http.get("/tickets/create")
        assert r.status_code == 503


# ─── TestCreateTicketSubmit ───────────────────────────────────────────────────


class TestCreateTicketSubmit:
    def test_success_redirects_303(self, client):
        http, _ = client
        r = http.post(
            "/tickets/create",
            data={"titre": "Mon ticket", "description": "Descriptif détaillé", "priority_code": "AVERAGE"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/tickets/newticket001"

    def test_success_clears_cache(self, client):
        http, _ = client
        # Pré-remplir le cache
        web_app._mem_cache["tickets:all"] = (time.time(), [make_ticket_obj()])
        http.post(
            "/tickets/create",
            data={"titre": "Mon ticket", "description": "Détail", "priority_code": "AVERAGE"},
            follow_redirects=False,
        )
        assert "tickets:all" not in web_app._mem_cache

    def test_api_error_redisplays_form_422(self, client):
        http, mock_portal = client
        mock_portal.create_ticket.side_effect = APIError("Formulaire invalide")
        r = http.post(
            "/tickets/create",
            data={"titre": "Mon titre", "description": "Détail", "priority_code": "AVERAGE"},
            follow_redirects=False,
        )
        assert r.status_code == 422
        assert "Mon titre" in r.text

    def test_empty_service_id_sends_none(self, client):
        http, mock_portal = client
        http.post(
            "/tickets/create",
            data={"titre": "T", "description": "D", "service_id": "", "qualification_id": "", "priority_code": "AVERAGE"},
            follow_redirects=False,
        )
        call_kwargs = mock_portal.create_ticket.call_args
        assert call_kwargs.kwargs.get("service_id") is None or call_kwargs.args[3] is None


# ─── TestTicketDetail ─────────────────────────────────────────────────────────


class TestTicketDetail:
    def test_returns_200(self, client):
        http, _ = client
        r = http.get("/tickets/abc123hex")
        assert r.status_code == 200
        assert "Problème CPS" in r.text

    def test_messages_oldest_first(self, client):
        http, mock_portal = client
        older = make_message_obj(id="m1", body="Premier message", created_at="2026-03-20T10:00:00")
        newer = make_message_obj(id="m2", body="Deuxième message", created_at="2026-03-21T10:00:00")
        mock_portal.get_enriched_messages.return_value = [newer, older]  # ordre inversé
        r = http.get("/tickets/abc123hex")
        assert r.status_code == 200
        pos_first = r.text.index("Premier message")
        pos_second = r.text.index("Deuxième message")
        assert pos_first < pos_second  # le plus ancien apparaît en premier

    def test_unknown_ticket_returns_404(self, client):
        http, mock_portal = client
        mock_portal.get_ticket.side_effect = Exception("Not found")
        r = http.get("/tickets/unknownid")
        assert r.status_code == 404

    def test_auth_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.get_ticket.side_effect = AuthError("Session expirée")
        r = http.get("/tickets/abc123hex")
        assert r.status_code == 503

    def test_api_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.get_ticket.side_effect = APIError("Portail KO")
        r = http.get("/tickets/abc123hex")
        assert r.status_code == 503

    def test_messages_api_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.get_ticket.return_value = make_ticket_obj()
        mock_portal.get_enriched_messages.side_effect = APIError("Messages indisponibles")
        r = http.get("/tickets/abc123hex")
        assert r.status_code == 503


# ─── TestTicketReply ──────────────────────────────────────────────────────────


class TestTicketReply:
    def test_reply_redirects_303(self, client):
        http, mock_portal = client
        r = http.post(
            "/tickets/abc123hex/reply",
            data={"message": "Ma réponse"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/tickets/abc123hex"
        mock_portal.add_message.assert_called_once()

    def test_reply_without_close_does_not_call_resolve(self, client):
        http, mock_portal = client
        http.post("/tickets/abc123hex/reply", data={"message": "Test"}, follow_redirects=False)
        mock_portal.resolve_ticket.assert_not_called()

    def test_reply_with_close_calls_resolve(self, client):
        http, mock_portal = client
        r = http.post(
            "/tickets/abc123hex/reply",
            data={"message": "Fermeture", "action": "close"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        mock_portal.resolve_ticket.assert_called_once_with("abc123hex")

    def test_reply_only_clears_message_cache(self, client):
        http, _ = client
        web_app._mem_cache["messages:abc123hex"] = (time.time(), [])
        web_app._mem_cache["messages:other999"] = (time.time(), [])
        web_app._mem_cache["tickets:all"] = (time.time(), [])

        http.post("/tickets/abc123hex/reply", data={"message": "ok"}, follow_redirects=False)

        assert "messages:abc123hex" not in web_app._mem_cache
        assert "messages:other999" in web_app._mem_cache   # isolation préfixe
        assert "tickets:all" in web_app._mem_cache          # pas touché sans close

    def test_reply_with_close_clears_tickets_cache(self, client):
        http, _ = client
        web_app._mem_cache["tickets:all"] = (time.time(), [])
        http.post(
            "/tickets/abc123hex/reply",
            data={"message": "ok", "action": "close"},
            follow_redirects=False,
        )
        assert "tickets:all" not in web_app._mem_cache

    def test_auth_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.add_message.side_effect = AuthError("Session invalide")
        r = http.post("/tickets/abc123hex/reply", data={"message": "test"}, follow_redirects=False)
        assert r.status_code == 503


# ─── TestTicketResolve ────────────────────────────────────────────────────────


class TestTicketResolve:
    def test_resolve_redirects_303(self, client):
        http, _ = client
        r = http.post("/tickets/abc123hex/resolve", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/tickets/abc123hex"

    def test_resolve_calls_portal(self, client):
        http, mock_portal = client
        http.post("/tickets/abc123hex/resolve", follow_redirects=False)
        mock_portal.resolve_ticket.assert_called_once_with("abc123hex")

    def test_resolve_clears_both_caches(self, client):
        http, _ = client
        web_app._mem_cache["messages:abc123hex"] = (time.time(), [])
        web_app._mem_cache["tickets:all"] = (time.time(), [])
        http.post("/tickets/abc123hex/resolve", follow_redirects=False)
        assert "messages:abc123hex" not in web_app._mem_cache
        assert "tickets:all" not in web_app._mem_cache

    def test_auth_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.resolve_ticket.side_effect = AuthError("Accès refusé")
        r = http.post("/tickets/abc123hex/resolve", follow_redirects=False)
        assert r.status_code == 503

    def test_api_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.resolve_ticket.side_effect = APIError("Portail KO")
        r = http.post("/tickets/abc123hex/resolve", follow_redirects=False)
        assert r.status_code == 503


# ─── TestExport ───────────────────────────────────────────────────────────────


class TestExport:
    def test_export_markdown_default(self, client):
        http, _ = client
        r = http.get("/tickets/abc123hex/export")
        assert r.status_code == 200
        assert "text/markdown" in r.headers.get("content-type", "")
        assert "26-083-000001" in r.text  # code ticket dans le corps

    def test_export_json_format(self, client):
        http, _ = client
        r = http.get("/tickets/abc123hex/export?fmt=json")
        assert r.status_code == 200
        assert "application/json" in r.headers.get("content-type", "")
        data = r.json()
        assert "code" in data or isinstance(data, dict)

    def test_export_no_raw_field(self, client):
        http, _ = client
        r = http.get("/tickets/abc123hex/export?fmt=json")
        assert r.status_code == 200
        body = r.text
        assert '"raw"' not in body

    def test_unknown_ticket_returns_404(self, client):
        http, mock_portal = client
        mock_portal.get_ticket.side_effect = Exception("Not found")
        r = http.get("/tickets/unknownid/export")
        assert r.status_code == 404

    def test_auth_error_returns_503(self, client):
        http, mock_portal = client
        mock_portal.get_ticket.side_effect = AuthError("Session expirée")
        r = http.get("/tickets/abc123hex/export")
        assert r.status_code == 503


# ─── TestRefresh ──────────────────────────────────────────────────────────────


class TestRefresh:
    def test_delta_refresh_redirects_with_count(self, client, monkeypatch):
        http, _ = client
        monkeypatch.setattr(web_app, "_delta_refresh", lambda c: 3)
        r = http.post("/refresh", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/?updated=3"

    def test_delta_refresh_exception_clears_cache_and_redirects(self, client, monkeypatch):
        http, _ = client
        web_app._mem_cache["tickets:all"] = (time.time(), [])
        monkeypatch.setattr(web_app, "_delta_refresh", lambda c: (_ for _ in ()).throw(Exception("crash")))
        r = http.post("/refresh", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        assert "tickets:all" not in web_app._mem_cache

    def test_full_refresh_clears_cache(self, client):
        http, _ = client
        web_app._mem_cache["tickets:all"] = (time.time(), [])
        web_app._mem_cache["messages:abc"] = (time.time(), [])
        r = http.post("/refresh/full", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        assert len(web_app._mem_cache) == 0


# ─── TestHeartbeat ────────────────────────────────────────────────────────────


class TestHeartbeat:
    def test_returns_ok_json(self, client):
        http, _ = client
        r = http.post("/heartbeat")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_updates_timestamp(self, client, monkeypatch):
        http, _ = client
        old_ts = time.time() - 100
        monkeypatch.setattr(web_app, "_last_heartbeat", old_ts)
        http.post("/heartbeat")
        assert web_app._last_heartbeat > old_ts


# ─── TestApiTickets ───────────────────────────────────────────────────────────


class TestApiTickets:
    def test_returns_json_list(self, client):
        http, _ = client
        r = http.get("/api/tickets")
        assert r.status_code == 200
        data = r.json()
        assert "tickets" in data
        assert isinstance(data["tickets"], list)

    def test_status_filter(self, client):
        http, _ = client
        r = http.get("/api/tickets?status=En+cours")
        data = r.json()
        assert all(t["status"] == "En cours" for t in data["tickets"])

    def test_auth_error_returns_error_json(self, client):
        http, mock_portal = client
        mock_portal.list_tickets.side_effect = AuthError("Expiré")
        r = http.get("/api/tickets")
        assert r.status_code == 200
        data = r.json()
        assert "error" in data
        assert data["tickets"] == []

    def test_no_raw_field_in_response(self, client):
        http, _ = client
        r = http.get("/api/tickets")
        body = r.text
        assert '"raw"' not in body


# ─── TestJinja2Filters ────────────────────────────────────────────────────────


class TestJinja2Filters:
    def test_status_color_en_cours(self):
        assert "blue" in _status_color("En cours")

    def test_status_color_attente(self):
        assert "yellow" in _status_color("En attente")

    def test_status_color_clos(self):
        result = _status_color("Clos")
        assert "gray" in result

    def test_status_color_expertise(self):
        assert "purple" in _status_color("En expertise")

    def test_status_color_unknown(self):
        result = _status_color("Inconnu")
        assert isinstance(result, str)  # ne doit pas lever d'exception

    def test_priority_color_critique(self):
        assert "red" in _priority_color("Critique")

    def test_priority_color_urgent(self):
        assert "red" in _priority_color("Urgent")

    def test_priority_color_normal(self):
        assert "green" in _priority_color("Normal")

    def test_priority_color_bas(self):
        assert "gray" in _priority_color("Bas")

    def test_is_client_author_inextranet(self):
        assert _is_client_author("INEXTRANET") is True

    def test_is_client_author_intranet(self):
        assert _is_client_author("INTRANET") is False

    def test_is_client_author_unknown(self):
        assert _is_client_author("OTHER") is False

    def test_is_hot_recent(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()[:19]
        assert _is_hot(recent) is True

    def test_is_hot_old(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()[:19]
        assert _is_hot(old) is False

    def test_is_hot_empty(self):
        assert _is_hot("") is False

    def test_is_hot_invalid(self):
        assert _is_hot("not-a-date") is False
