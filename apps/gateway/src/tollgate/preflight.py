"""Offline deployment checks. Never print configuration values or contact providers."""

import base64
from urllib.parse import urlsplit


def production_checks(settings):
    try:
        master_key_valid = len(base64.b64decode(settings.master_key, validate=True)) == 32
    except (ValueError, TypeError):
        master_key_valid = False
    origins = [urlsplit(origin.strip()) for origin in settings.allowed_origin.split(",")]
    return {
        "demo_disabled": not settings.demo,
        "mock_provider_disabled": not settings.enable_mock_provider,
        "postgresql_configured": settings.database_url.startswith("postgresql+asyncpg://"),
        "redis_configured": settings.redis_url.startswith(("redis://", "rediss://")),
        "secure_session_cookies": settings.cookie_secure,
        "https_origins": all(
            origin.scheme == "https" and bool(origin.hostname) and not origin.username and not origin.password
            for origin in origins
        ),
        "private_owner_password": len(settings.admin_password) >= 12
        and settings.admin_password != "tollgate-demo-2026",
        "valid_master_key": master_key_valid,
        "unsupported_integrations_disabled": not settings.kms_key_id and not settings.presidio_url,
    }
