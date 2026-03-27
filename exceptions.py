"""Custom exceptions for SESAM Ticket Manager."""


class SesamError(Exception):
    """Base exception for all SESAM-related errors."""

    pass


class AuthError(SesamError):
    """Raised when authentication or session validation fails."""

    pass


class LoginError(AuthError):
    """Raised when login attempt fails after retries."""

    pass


class SessionExpiredError(AuthError):
    """Raised when session has expired and reconnection failed."""

    pass


class APIError(SesamError):
    """Raised when API request fails (4xx/5xx response or network error)."""

    pass


class StateError(SesamError):
    """Raised when state file operations fail."""

    pass


class ConfigError(SesamError):
    """Raised when configuration is invalid or missing."""

    pass


class ValidationError(SesamError):
    """Raised when input validation fails."""

    pass
