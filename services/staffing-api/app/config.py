from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_RV_SOURCES = frozenset({"azure", "azure_raw", "demo"})
_STAFFING_STORES = frozenset({"azure", "memory"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_sql_connection_string: str | None = Field(
        default=None,
        validation_alias="AZURE_SQL_CONNECTION_STRING",
    )
    azure_sql_server: str | None = Field(default=None, validation_alias="AZURE_SQL_SERVER")
    azure_sql_database: str | None = Field(default=None, validation_alias="AZURE_SQL_DATABASE")
    azure_sql_username: str | None = Field(default=None, validation_alias="AZURE_SQL_USERNAME")
    azure_sql_password: str | None = Field(default=None, validation_alias="AZURE_SQL_PASSWORD")
    azure_sql_driver: str = Field(
        default="ODBC Driver 18 for SQL Server",
        validation_alias="AZURE_SQL_DRIVER",
    )
    azure_sql_trust_server_certificate: str = Field(
        default="no",
        validation_alias="AZURE_SQL_TRUST_SERVER_CERTIFICATE",
    )
    azure_sql_max_rows: int = Field(default=0, validation_alias="AZURE_SQL_MAX_ROWS")

    api_host: str = Field(default="127.0.0.1", validation_alias="API_HOST")
    api_port: int = Field(default=8010, validation_alias="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:5174,http://localhost:5175,http://127.0.0.1:5174,http://127.0.0.1:5175",
        validation_alias="CORS_ORIGINS",
    )
    dev_launch_token: str = Field(default="dev-simulator-token", validation_alias="DEV_LAUNCH_TOKEN")
    """Primary switch: `azure` (Azure SQL) or `demo` (synthetic). Overrides RV_DATA_SOURCE when set."""
    rv_data_mode: str | None = Field(default=None, validation_alias="RV_DATA_MODE")
    rv_data_source: str = Field(default="azure", validation_alias="RV_DATA_SOURCE")
    staffing_persistence: str = Field(
        default="azure",
        validation_alias="STAFFING_PERSISTENCE",
        description="azure | memory (memory for unit tests only)",
    )

    @field_validator("rv_data_mode", "rv_data_source", mode="before")
    @classmethod
    def _strip_mode(cls, v: object) -> object:
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()

    @field_validator("staffing_persistence", mode="before")
    @classmethod
    def _strip_persist(cls, v: object) -> object:
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()

    def resolved_rv_data_source(self) -> str:
        raw = (self.rv_data_mode or self.rv_data_source or "azure").strip().lower()
        if raw not in _RV_SOURCES:
            raise ValueError(f"RV_DATA_MODE / RV_DATA_SOURCE must be one of: {', '.join(sorted(_RV_SOURCES))}")
        return raw

    def resolved_staffing_persistence(self) -> str:
        mode = self.staffing_persistence.strip().lower()
        if mode not in _STAFFING_STORES:
            raise ValueError("STAFFING_PERSISTENCE must be azure or memory")
        if self.resolved_rv_data_source() == "demo" and mode == "azure":
            return "memory"
        return mode
    employee_block_max: int = Field(default=3, validation_alias="EMPLOYEE_BLOCK_MAX")
    interview_expiry_days: int = Field(default=7, validation_alias="INTERVIEW_EXPIRY_DAYS")
    training_ratio: float = Field(default=0.85, validation_alias="TRAINING_RATIO")
    refresh_debounce_seconds: int = Field(default=30, validation_alias="REFRESH_DEBOUNCE_SECONDS")
    confirmed_project_statuses: str = Field(default="confirmed", validation_alias="CONFIRMED_PROJECT_STATUSES")
    allow_window_extend: bool = Field(default=False, validation_alias="ALLOW_WINDOW_EXTEND")
    outbox_poll_seconds: int = Field(default=10, validation_alias="OUTBOX_POLL_SECONDS")
    skill_level_order: str = Field(
        default="Foundational,Applied,Advanced,Expert",
        validation_alias="SKILL_LEVEL_ORDER",
    )
    mnh_hr_to: str = Field(
        default="hr-staffing@mynexthire.example",
        validation_alias="MNH_HR_TO",
        description="HR mailbox for MyNextHire staffing request emails (To).",
    )
    mnh_bu_lead_cc_default: str = Field(
        default="bu-lead@example.com",
        validation_alias="MNH_BU_LEAD_CC",
        description="Default BU lead address on MNH staffing emails (Cc).",
    )

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def confirmed_statuses(self) -> frozenset[str]:
        return frozenset(s.strip().lower() for s in self.confirmed_project_statuses.split(",") if s.strip())

    def skill_levels(self) -> tuple[str, ...]:
        return tuple(s.strip() for s in self.skill_level_order.split(",") if s.strip())

    def uses_connection_string(self) -> bool:
        return bool(self.azure_sql_connection_string and self.azure_sql_connection_string.strip())

    def build_connection_string(self) -> str:
        """Prefer AZURE_SQL_CONNECTION_STRING; four-part AZURE_SQL_* is optional fallback."""
        if self.uses_connection_string():
            return self.azure_sql_connection_string.strip()  # type: ignore[union-attr]

        missing = [
            name
            for name, value in [
                ("AZURE_SQL_SERVER", self.azure_sql_server),
                ("AZURE_SQL_DATABASE", self.azure_sql_database),
                ("AZURE_SQL_USERNAME", self.azure_sql_username),
                ("AZURE_SQL_PASSWORD", self.azure_sql_password),
            ]
            if value is None or str(value).strip() == ""
        ]
        if missing:
            raise ValueError(
                "Azure SQL is not configured. Set AZURE_SQL_CONNECTION_STRING "
                f"or provide: {', '.join(missing)}.",
            )

        server = self.azure_sql_server.strip()
        if not server.startswith("tcp:"):
            server = f"tcp:{server},1433"

        trust = self.azure_sql_trust_server_certificate.strip().lower()
        trust_flag = "yes" if trust in {"1", "true", "yes"} else "no"

        return (
            f"DRIVER={{{self.azure_sql_driver}}};"
            f"SERVER={server};"
            f"DATABASE={self.azure_sql_database.strip()};"
            f"UID={self.azure_sql_username.strip()};"
            f"PWD={self.azure_sql_password};"
            f"Encrypt=yes;"
            f"TrustServerCertificate={trust_flag};"
            f"Connection Timeout=30;"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()