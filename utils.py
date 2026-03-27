"""Utility functions for SESAM Ticket Manager."""

import logging
import logging.config
import os
import re
from datetime import datetime

from exceptions import ValidationError


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   Can be overridden by LOG_LEVEL env var

    Returns:
        Configured root logger instance
    """
    # Allow env var override
    log_level = os.getenv("LOG_LEVEL", log_level).upper()

    # Validate log level
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in valid_levels:
        log_level = "INFO"

    # Configure logging format
    log_format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        datefmt=date_format,
    )

    # Get root logger
    logger = logging.getLogger()
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance for the module
    """
    return logging.getLogger(name)


def validate_ticket_code(code: str) -> str:
    """
    Validate SESAM ticket code format.

    Expected format: "XX-XXX-XXXXXX" (2-3-6 digits separated by hyphens)

    Args:
        code: Ticket code to validate

    Returns:
        The validated code

    Raises:
        ValidationError: If code format is invalid
    """
    if not code or not isinstance(code, str):
        raise ValidationError("Ticket code must be a non-empty string")

    # Check if it's a hex ID (alternative format)
    if len(code) <= 20 and re.match(r"^[a-f0-9]+$", code):
        return code

    # Check standard format: XX-XXX-XXXXXX
    if not re.match(r"^\d{2}-\d{3}-\d{6}$", code):
        raise ValidationError(
            f"Invalid ticket code format: {code}. Expected format: XX-XXX-XXXXXX"
        )

    return code


def validate_email(email: str) -> str:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        The validated email

    Raises:
        ValidationError: If email format is invalid
    """
    if not email or not isinstance(email, str):
        raise ValidationError("Email must be a non-empty string")

    # Simple email validation (not exhaustive, but practical)
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        raise ValidationError(f"Invalid email format: {email}")

    return email


def validate_url(url: str) -> str:
    """
    Validate URL format.

    Args:
        url: URL to validate

    Returns:
        The validated URL

    Raises:
        ValidationError: If URL format is invalid
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL must be a non-empty string")

    if not url.startswith(("http://", "https://")):
        raise ValidationError(f"Invalid URL: {url}. Must start with http:// or https://")

    return url



def truncate_string(value: str, max_length: int = 300, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.

    Args:
        value: String to truncate
        max_length: Maximum length (excludes suffix)
        suffix: Text to append if truncated

    Returns:
        Truncated string
    """
    if not isinstance(value, str):
        return value

    if len(value) <= max_length:
        return value

    return value[: max_length - len(suffix)] + suffix


def safe_get_dict(data: dict, *keys, default=None):
    """
    Safely get nested dictionary values.

    Args:
        data: Dictionary to search
        *keys: Keys to traverse (supports nested access)
        default: Default value if key not found

    Returns:
        Value at key path or default
    """
    if not isinstance(data, dict):
        return default

    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default

        if result is None:
            return default

    return result


def format_iso_date(dt_str: str, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """
    Convertit une date ISO 8601 en chaîne formatée.

    Args:
        dt_str: Date ISO (ex: "2026-03-24T10:30:00Z" ou "2026-03-24T10:30:00.000+0000")
        fmt: Format strftime souhaité (défaut: "%d/%m/%Y %H:%M")

    Returns:
        Date formatée, ou dt_str tronqué en cas d'erreur
    """
    if not dt_str:
        return ""
    try:
        return datetime.fromisoformat(dt_str[:19]).strftime(fmt)
    except Exception:
        return dt_str[:16] if len(dt_str) >= 16 else dt_str


def format_ticket_export(ticket, fmt: str = "markdown") -> str:
    """
    Format a ticket for export, ready to be passed to a DUST agent.

    Args:
        ticket: Ticket object (with .messages loaded)
        fmt: "markdown" (default) or "json"

    Returns:
        Formatted string
    """
    if fmt == "json":
        return _ticket_to_json(ticket)
    return _ticket_to_markdown(ticket)


def _fmt_date_export(dt_str: str) -> str:
    """Convert ISO date to DD/MM/YYYY."""
    result = format_iso_date(dt_str, fmt="%d/%m/%Y")
    return result or "—"


def _msg_direction(type_code: str, type_label: str) -> str:
    """Traduit le code type d'un message en libellé de direction lisible."""
    if type_code == "INEXTRANET":
        return "Client → Support"
    if type_code == "INTRANET":
        return "Support → Client"
    return type_label or type_code or "?"


def _ticket_to_markdown(ticket) -> str:
    """Sérialise un ticket et ses messages au format Markdown structuré."""
    lines = [
        f"# Ticket SESAM-Vitale : {ticket.code}",
        "",
        f"**Titre** : {ticket.titre}",
        f"**Statut** : {ticket.status}",
        f"**Priorité** : {ticket.priority or '—'}",
        f"**Type** : {ticket.type_ticket or '—'}",
    ]
    if ticket.service:
        lines.append(f"**Service** : {ticket.service}")
    if ticket.qualification:
        lines.append(f"**Qualification** : {ticket.qualification}")
    lines.append(f"**Demandeur** : {ticket.author or '—'}")
    lines.append(f"**Créé le** : {_fmt_date_export(ticket.created_at)}")
    if ticket.updated_at:
        lines.append(f"**Mis à jour le** : {_fmt_date_export(ticket.updated_at)}")
    if ticket.closed_at:
        lines.append(f"**Clos le** : {_fmt_date_export(ticket.closed_at)}")

    msgs = sorted(ticket.messages or [], key=lambda m: m.created_at or "")
    lines += ["", "---", "", f"## Messages ({len(msgs)})", ""]

    for i, msg in enumerate(msgs, 1):
        direction = _msg_direction(msg.type_code, msg.type_label)
        date_str = _fmt_date_export(msg.created_at)
        time_str = (msg.created_at[11:16] if msg.created_at and len(msg.created_at) > 10 else "")
        timestamp = f"{date_str} {time_str}".strip()
        lines.append(f"### Message {i} — [{direction}] {timestamp}")
        if msg.title:
            lines.append(f"**Objet** : {msg.title}")
        lines.append("")
        if msg.body:
            lines.append(msg.body.strip())
        else:
            lines.append("*(pas de contenu)*")
        if msg.attachments:
            lines.append("")
            for att in msg.attachments:
                if isinstance(att, dict):
                    name = att.get("name") or att.get("fileName") or att.get("originalFileName") or "pièce jointe"
                    ctype = att.get("contentType", "")
                    lines.append(f"📎 Pièce jointe : {name}" + (f" ({ctype})" if ctype else ""))
        lines += ["", "---", ""]

    return "\n".join(lines)


def _ticket_to_json(ticket) -> str:
    """Sérialise un ticket et ses messages au format JSON normalisé."""
    import json as _json

    def _att_info(att):
        if not isinstance(att, dict):
            return {"nom": str(att)}
        return {
            "nom": att.get("name") or att.get("fileName") or att.get("originalFileName") or "",
            "type": att.get("contentType") or "",
        }

    msgs = sorted(ticket.messages or [], key=lambda m: m.created_at or "")
    data = {
        "ticket": {
            "reference": ticket.code,
            "titre": ticket.titre,
            "statut": ticket.status,
            "priorite": ticket.priority,
            "type": ticket.type_ticket,
            "service": ticket.service,
            "qualification": ticket.qualification,
            "demandeur": ticket.author,
            "cree_le": ticket.created_at,
            "mis_a_jour_le": ticket.updated_at,
            "clos_le": ticket.closed_at,
        },
        "messages": [
            {
                "numero": i + 1,
                "direction": _msg_direction(m.type_code, m.type_label),
                "objet": m.title,
                "contenu": m.body,
                "date": m.created_at,
                "pieces_jointes": [_att_info(a) for a in (m.attachments or [])],
            }
            for i, m in enumerate(msgs)
        ],
    }
    return _json.dumps(data, indent=2, ensure_ascii=False)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration (e.g., "1m 23s", "45s")
    """
    if seconds < 1:
        return f"{seconds:.2f}s"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)

    if minutes == 0:
        return f"{secs}s"
    elif minutes < 60:
        return f"{minutes}m {secs}s"
    else:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
