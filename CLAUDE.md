# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest                                          # All tests
pytest -v --tb=short                           # Verbose with short tracebacks
pytest tests/test_portal.py -v                 # Single test file
pytest tests/test_portal.py::TestStripHTML -v  # Single test class
pytest --cov=portal,web_app                    # With coverage

# Run web app
uvicorn web_app:app --reload --port 8473       # Dev server at localhost:8473

# Run CLI
python main.py list
python main.py show <TICKET_CODE>
python main.py messages <TICKET_CODE>
python main.py reply <TICKET_CODE>
python main.py status
```

## Architecture

The app is a ticket management client for the proprietary **Efficy 11 CRM** backend (SESAM-Vitale Portail IRIS). It has two interfaces over a shared HTTP client:

- **[portal.py](portal.py)** — Core HTTP client (`PortalClient`). Handles JHipster session auth, all API calls, data models (`Ticket`, `Message`), HTML sanitization, and persistent state (cookies + known tickets in `.sesam_state.json`). The API has quirks: `/requests/company` uses `nbOfResults` (with 's') but `/requests/{id}/messages` uses `nbOfResult` (without 's').
- **[web_app.py](web_app.py)** — FastAPI app with Jinja2 templates. Implements its own two-tier cache (memory LRU 500 entries + disk JSON 1hr TTL). Background refresh every 15 minutes.
- **[main.py](main.py)** — Click CLI with Rich formatting.
- **[config.py](config.py)** — Loads credentials from `.env` via python-dotenv. Required vars: `SESAM_USERNAME`, `SESAM_PASSWORD`.
- **[test_suggest.py](test_suggest.py)** — Fuzzy matching engine for qualification suggestions (not a test file despite the name).

## Key Technical Details

**Authentication**: POST to `/api/authenticate` → JHipster session cookies (`JSESSIONID` + `XSRF-TOKEN`) managed automatically by `requests.Session`. `SessionExpiredError` triggers re-auth.

**State persistence**: `.sesam_state.json` is written atomically (temp file + rename) with file locking (`fcntl` on Unix) to prevent concurrent corruption.

**HTML content**: Ticket descriptions and messages contain raw HTML from the portal. `portal.py` sanitizes these by stripping tags and dangerous attributes before use.

**Caching** (web app): Memory cache evicts on LRU, disk cache at `.sesam_web_cache.json` invalidated by key prefix.

## Workflow

- Never commit or push automatically — the user always handles git operations.
- Tests are run automatically via pre-commit hook on file edits (configured in `.claude/settings.local.json`).
- The `features/` directory contains Gherkin BDD specs (documentation, not executable tests).
