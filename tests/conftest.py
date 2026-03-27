"""Shared test fixtures for SESAM Ticket Manager tests."""

import json
import sys
import os
from pathlib import Path

import pytest

# Add project root to sys.path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def sample_ticket_data():
    """Raw API response for a single ticket."""
    return {
        "id": "00294000001e8cbd",
        "code": "26-083-026025",
        "titre": "Problème de lecture CPS",
        "status": {"code": "ENCOURS", "label": "En cours"},
        "priority": {"code": "AVERAGE", "label": "Normal"},
        "typeTicket": {"code": "INC", "label": "Incident"},
        "service": {"id": "svc001", "label": "Support technique"},
        "qualification": {"code": "TECH", "label": "Technique"},
        "person": {"firstName": "Jean", "lastName": "Dupont"},
        "createdAt": "2026-03-20T10:30:00Z",
        "updatedAt": "2026-03-21T14:15:00Z",
        "closedAt": None,
        "description": "<p>Description du problème avec <b>balises HTML</b></p>",
    }


@pytest.fixture
def sample_message_data():
    """Raw API response for a message."""
    return {
        "id": "msg001",
        "title": "Mise à jour",
        "description": "<p>Le problème a été <i>identifié</i>.</p>",
        "type": {"code": "INEXTRANET", "label": "Extranet entrant"},
        "createdAt": "2026-03-21T15:00:00Z",
        "attachments": [],
    }


@pytest.fixture
def sample_ticket_list_response(sample_ticket_data):
    """API response for list_tickets."""
    return {
        "objectsList": [sample_ticket_data],
        "totalCount": 1,
    }


@pytest.fixture
def tmp_state_file(tmp_path):
    """Temporary state file for tests."""
    return tmp_path / ".sesam_state.json"


@pytest.fixture
def state_data():
    """Sample state file content."""
    return {
        "cookies": {"JSESSIONID": "abc123"},
        "known_tickets": {
            "26-083-026025": "2026-03-20T10:30:00Z",
        },
    }
