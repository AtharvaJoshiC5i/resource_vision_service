from __future__ import annotations

from app.config import get_settings


def resolved_rv_data_source() -> str:
    settings = get_settings()
    return settings.resolved_rv_data_source()


def staffing_persistence() -> str:
    return get_settings().staffing_persistence.strip().lower()


def azure_sql_configured() -> bool:
    settings = get_settings()
    if settings.uses_connection_string():
        return True
    parts = (
        settings.azure_sql_server,
        settings.azure_sql_database,
        settings.azure_sql_username,
        settings.azure_sql_password,
    )
    return all(p is not None and str(p).strip() for p in parts)


def runtime_info() -> dict:
    mode = resolved_rv_data_source()
    persistence = staffing_persistence()
    settings = get_settings()
    return {
        "data_mode": "demo" if mode == "demo" else "azure",
        "rv_data_source": mode,
        "staffing_persistence": persistence,
        "azure_sql_configured": azure_sql_configured(),
        "azure_sql_via_connection_string": settings.uses_connection_string(),
        "synthetic": mode == "demo",
    }