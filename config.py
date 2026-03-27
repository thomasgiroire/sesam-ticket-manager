"""
config.py - Centralized configuration for SESAM Ticket Manager
===============================================================
Loads all configuration from environment variables (.env file).
Provides validation and defaults for all settings.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from exceptions import ConfigError

load_dotenv()


@dataclass
class PortalConfig:
    """Configuration for SESAM-Vitale portal connection."""

    base_url: str = "https://portail-support.sesam-vitale.fr/gsvextranet"
    username: str = ""
    password: str = ""
    state_file: str = ".sesam_state.json"

    @property
    def api_base(self) -> str:
        return f"{self.base_url}/api"

    @property
    def login_url(self) -> str:
        return f"{self.api_base}/authenticate"

    def validate(self):
        """Validate that required portal configuration is present."""
        if not self.username or not self.password:
            raise ConfigError(
                "SESAM_USERNAME et SESAM_PASSWORD doivent etre definis dans .env"
            )


@dataclass
class AppConfig:
    """Root configuration object combining all sub-configs."""

    portal: PortalConfig = field(default_factory=PortalConfig)
    log_level: str = "WARNING"

    def validate_all(self):
        """Validate all configuration sections."""
        self.portal.validate()


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.

    Returns:
        AppConfig instance with all settings loaded

    Raises:
        ConfigError: If required configuration is missing
    """
    return AppConfig(
        portal=PortalConfig(
            base_url=os.getenv(
                "PORTAL_BASE_URL",
                "https://portail-support.sesam-vitale.fr/gsvextranet",
            ),
            username=os.getenv("SESAM_USERNAME", ""),
            password=os.getenv("SESAM_PASSWORD", ""),
            state_file=os.getenv("STATE_FILE", ".sesam_state.json"),
        ),
        log_level=os.getenv("LOG_LEVEL", "WARNING"),
    )
