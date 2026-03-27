"""Tests for portal.py - HTML stripping, state management, and data parsing."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal import (
    strip_html,
    _HTMLStripper,
    PortalState,
    PortalClient,
    Ticket,
    Message,
)
from exceptions import AuthError, LoginError, SessionExpiredError, StateError


# ─── HTML Stripping Tests ───────────────────────────────────────────────────


class TestStripHTML:
    def test_empty_string(self):
        assert strip_html("") == ""

    def test_none_value(self):
        assert strip_html(None) == ""

    def test_whitespace_only(self):
        assert strip_html("   ") == ""

    def test_plain_text(self):
        assert strip_html("Hello world") == "Hello world"

    def test_no_html_tags(self):
        assert strip_html("Simple text without tags") == "Simple text without tags"

    def test_basic_html(self):
        result = strip_html("<p>Hello <b>world</b></p>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_paragraph_tags(self):
        result = strip_html("<p>Paragraph 1</p><p>Paragraph 2</p>")
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result

    def test_br_tags(self):
        result = strip_html("Line 1<br>Line 2<br/>Line 3")
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_nested_html(self):
        html = "<div><ul><li>Item 1</li><li>Item 2</li></ul></div>"
        result = strip_html(html)
        assert "Item 1" in result
        assert "Item 2" in result
        assert "<" not in result

    def test_html_entities_in_fallback(self):
        """Test that fallback regex handles common HTML entities."""
        # Force fallback by using malformed HTML that might trigger parser error
        result = strip_html("Hello &amp; world")
        assert "Hello" in result
        assert "world" in result

    def test_excessive_newlines_cleaned(self):
        result = strip_html("<p>A</p><p></p><p></p><p></p><p>B</p>")
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in result

    def test_heading_tags(self):
        result = strip_html("<h1>Title</h1><h2>Subtitle</h2><p>Content</p>")
        assert "Title" in result
        assert "Subtitle" in result
        assert "Content" in result

    def test_table_content(self):
        html = "<table><tr><td>Cell 1</td><td>Cell 2</td></tr></table>"
        result = strip_html(html)
        assert "Cell 1" in result
        assert "Cell 2" in result

    def test_html_comments_handled(self):
        result = strip_html("Before<!-- comment -->After")
        assert "Before" in result
        assert "After" in result
        assert "comment" not in result


# ─── PortalState Tests ──────────────────────────────────────────────────────


class TestPortalState:
    def test_init_creates_empty_state(self, tmp_state_file):
        state = PortalState(path=tmp_state_file)
        assert state._data == {}
        assert state.cookies == {}
        assert state.known_tickets == {}

    def test_load_existing_state(self, tmp_state_file, state_data):
        tmp_state_file.write_text(json.dumps(state_data))
        state = PortalState(path=tmp_state_file)
        assert state.cookies == {"JSESSIONID": "abc123"}
        assert "26-083-026025" in state.known_tickets

    def test_load_corrupted_file(self, tmp_state_file):
        tmp_state_file.write_text("not valid json{{{")
        state = PortalState(path=tmp_state_file)
        assert state._data == {}

    def test_save_and_reload(self, tmp_state_file):
        state = PortalState(path=tmp_state_file)
        state.cookies = {"session": "test123"}

        # Reload
        state2 = PortalState(path=tmp_state_file)
        assert state2.cookies == {"session": "test123"}

    def test_update_known_tickets(self, tmp_state_file):
        state = PortalState(path=tmp_state_file)
        ticket1 = MagicMock(code="26-083-000001", updated_at="2026-03-20T10:00:00Z")
        ticket2 = MagicMock(code="26-083-000002", updated_at="2026-03-21T11:00:00Z")

        state.update_known_tickets([ticket1, ticket2])
        assert state.known_tickets["26-083-000001"] == "2026-03-20T10:00:00Z"
        assert state.known_tickets["26-083-000002"] == "2026-03-21T11:00:00Z"

    def test_get_new_or_updated_detects_new(self, tmp_state_file, state_data):
        tmp_state_file.write_text(json.dumps(state_data))
        state = PortalState(path=tmp_state_file)

        # Known ticket (same updated_at) + new ticket
        known = MagicMock(code="26-083-026025", updated_at="2026-03-20T10:30:00Z")
        new = MagicMock(code="26-083-999999", updated_at="2026-03-25T10:00:00Z")

        result = state.get_new_or_updated([known, new])
        assert len(result) == 1
        assert result[0].code == "26-083-999999"

    def test_get_new_or_updated_detects_modified(self, tmp_state_file, state_data):
        tmp_state_file.write_text(json.dumps(state_data))
        state = PortalState(path=tmp_state_file)

        # Same code but different updated_at
        modified = MagicMock(code="26-083-026025", updated_at="2026-03-25T16:00:00Z")

        result = state.get_new_or_updated([modified])
        assert len(result) == 1

    def test_atomic_write_creates_file(self, tmp_state_file):
        state = PortalState(path=tmp_state_file)
        state.cookies = {"test": "value"}

        assert tmp_state_file.exists()
        data = json.loads(tmp_state_file.read_text())
        assert data["cookies"]["test"] == "value"


# ─── Ticket/Message Parsing Tests ──────────────────────────────────────────


class TestTicketParsing:
    def test_parse_ticket(self, sample_ticket_data):
        client = PortalClient.__new__(PortalClient)
        client._services_cache = {}

        ticket = client._parse_ticket(sample_ticket_data)

        assert ticket.id == "00294000001e8cbd"
        assert ticket.code == "26-083-026025"
        assert ticket.titre == "Problème de lecture CPS"
        assert ticket.status == "En cours"
        assert ticket.status_code == "ENCOURS"
        assert ticket.priority == "Normal"
        assert ticket.type_ticket == "Incident"
        assert ticket.author == "Jean Dupont"
        assert ticket.service == "Support technique"

    def test_parse_ticket_missing_fields(self):
        """Test parsing with minimal/missing fields."""
        client = PortalClient.__new__(PortalClient)
        client._services_cache = {}

        data = {"id": "abc", "code": "00-000-000000"}
        ticket = client._parse_ticket(data)

        assert ticket.id == "abc"
        assert ticket.code == "00-000-000000"
        assert ticket.titre == ""
        assert ticket.author == ""

    def test_parse_message(self, sample_message_data):
        client = PortalClient.__new__(PortalClient)

        msg = client._parse_message(sample_message_data)

        assert msg.id == "msg001"
        assert msg.title == "Mise à jour"
        assert "identifié" in msg.body
        assert "<" not in msg.body  # HTML stripped
        assert msg.type_code == "INEXTRANET"

    def test_ticket_to_dict(self):
        ticket = Ticket(
            id="abc", code="26-083-000001", titre="Test",
            status="En cours", status_code="ENCOURS",
            priority="Normal", type_ticket="Incident",
            service="Support", qualification="Tech",
            author="Test User", created_at="2026-01-01",
            updated_at="2026-01-02", raw={"secret": "data"},
        )
        d = ticket.to_dict()
        assert "raw" not in d
        assert d["code"] == "26-083-000001"

    def test_ticket_short_repr(self):
        ticket = Ticket(
            id="abc", code="26-083-000001", titre="Test ticket title",
            status="En cours", status_code="ENCOURS",
            priority="Normal", type_ticket="Incident",
            service="Support", qualification="Tech",
            author="Test", created_at="2026-01-01",
            updated_at="2026-01-02",
        )
        repr_str = ticket.short_repr()
        assert "26-083-000001" in repr_str
        assert "En cours" in repr_str


# ─── Auth Tests ─────────────────────────────────────────────────────────────


def _make_client(tmp_state_file, username: str = "user", password: str = "pass"):
    """Helper : crée un PortalClient avec une config injectée (sans appel réseau)."""
    from config import PortalConfig
    cfg = PortalConfig(username=username, password=password, state_file=str(tmp_state_file))
    client = PortalClient.__new__(PortalClient)
    client._config = cfg
    client.state = PortalState(path=tmp_state_file)
    client._session = MagicMock()
    client._services_cache = {}
    return client


class TestAuth:
    def test_login_missing_credentials(self, tmp_state_file):
        client = _make_client(tmp_state_file, username="", password="")

        with pytest.raises(AuthError, match="SESAM_USERNAME"):
            client.login()

    def test_login_success(self, tmp_state_file):
        client = _make_client(tmp_state_file)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        client._session.post.return_value = mock_resp
        client._session.cookies = {"JSESSIONID": "test"}

        result = client.login()
        assert result is True

    def test_login_401_raises_auth_error(self, tmp_state_file):
        client = _make_client(tmp_state_file)

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        client._session.post.return_value = mock_resp

        with pytest.raises(AuthError, match="401"):
            client.login()

    def test_login_retries_on_network_error(self, tmp_state_file):
        import requests

        client = _make_client(tmp_state_file)

        # Fail twice, succeed on third
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        client._session.cookies = {"JSESSIONID": "test"}

        client._session.post.side_effect = [
            requests.ConnectionError("Network down"),
            requests.ConnectionError("Network down"),
            mock_resp,
        ]

        result = client.login(max_retries=3)
        assert result is True
        assert client._session.post.call_count == 3
