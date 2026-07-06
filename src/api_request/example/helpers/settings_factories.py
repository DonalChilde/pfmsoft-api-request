"""Factory functions for creating instances of settings-related classes."""

from esi_link.settings import EsiLinkSettings


def app_data_db_uri_factory(settings: EsiLinkSettings) -> str:
    """Factory function to create the URI for the app-data SQLite database."""
    return f"file:{settings.app_data_db_path}?mode=rwc"
