from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALLOWED_DEPLOYMENT_ROLES = frozenset({
    "standard",
    "validation",
    "production",
})
DEPLOYMENT_ROLE_ERROR = (
    "DEPLOYMENT_ROLE must be one of: standard, "
    "validation, production"
)


def default_environment_label(role: str) -> str:
    return {
        "standard": "开源标准版",
        "validation": "验证环境",
        "production": "正式生产",
    }[role]


class ConfigurationError(RuntimeError):
    """Raised when an environment profile is incomplete or invalid."""


def _non_blank(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = _non_blank(environ.get(name))
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be a positive integer")
    return value


def _boolean(environ: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _non_blank(environ.get(name))
    if raw is None:
        return default
    normalized = raw.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


def database_dialect(database_url: str) -> str:
    scheme = database_url.partition(":")[0].lower()
    return scheme.partition("+")[0]


def engine_options(database_url: str, environ: Mapping[str, str]) -> dict[str, object]:
    if database_dialect(database_url) == "sqlite":
        return {}
    return {
        "pool_pre_ping": True,
        "pool_recycle": _positive_int(environ, "DB_POOL_RECYCLE_SECONDS", 1800),
        "pool_timeout": _positive_int(environ, "DB_POOL_TIMEOUT_SECONDS", 30),
    }


class BaseConfig:
    APP_ENV = "base"
    TESTING = False
    PROD = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    SEED_PROFILE = "none"
    AUTO_BOOTSTRAP = False

    DEFAULT_DATABASE_URL: str | None = None
    DEFAULT_STORAGE_ROOT: Path | None = None

    def __init__(self, environ: Mapping[str, str] | None = None):
        self._environ = os.environ if environ is None else environ
        self.AUTO_BOOTSTRAP = _boolean(self._environ, "AUTO_BOOTSTRAP", self.AUTO_BOOTSTRAP)
        self.APP_BUSINESS_READ_ONLY = _boolean(
            self._environ, "APP_BUSINESS_READ_ONLY", False
        )
        self.DEPLOYMENT_ROLE = (
            _non_blank(self._environ.get("DEPLOYMENT_ROLE"))
            or "standard"
        ).lower()
        if self.DEPLOYMENT_ROLE not in ALLOWED_DEPLOYMENT_ROLES:
            raise ConfigurationError(DEPLOYMENT_ROLE_ERROR)
        self.ENVIRONMENT_LABEL = _non_blank(
            self._environ.get("ENVIRONMENT_LABEL")
        ) or default_environment_label(self.DEPLOYMENT_ROLE)
        if len(self.ENVIRONMENT_LABEL) > 80:
            raise ConfigurationError("ENVIRONMENT_LABEL must not exceed 80 characters")
        self.EXTERNAL_SIDE_EFFECTS_ENABLED = _boolean(
            self._environ,
            "EXTERNAL_SIDE_EFFECTS_ENABLED",
            self.DEPLOYMENT_ROLE == "standard",
        )
        if (
            self.DEPLOYMENT_ROLE == "validation"
            and self.EXTERNAL_SIDE_EFFECTS_ENABLED
        ):
            raise ConfigurationError(
                "validation deployment forbids EXTERNAL_SIDE_EFFECTS_ENABLED"
            )
        self.SQLALCHEMY_DATABASE_URI = self.resolve_database_url()
        self.STORAGE_ROOT = self.resolve_storage_root()
        self.DATABASE_DIALECT = database_dialect(self.SQLALCHEMY_DATABASE_URI)
        self.SQLALCHEMY_ENGINE_OPTIONS = engine_options(
            self.SQLALCHEMY_DATABASE_URI,
            self._environ,
        )
        self.validate()

    def resolve_database_url(self) -> str:
        value = _non_blank(self._environ.get("DATABASE_URL")) or self.DEFAULT_DATABASE_URL
        if not value:
            raise ConfigurationError(f"{self.APP_ENV} profile requires DATABASE_URL")
        return value

    def resolve_storage_root(self) -> str:
        value = _non_blank(self._environ.get("STORAGE_ROOT"))
        if value:
            return value
        if self.DEFAULT_STORAGE_ROOT is None:
            raise ConfigurationError(f"{self.APP_ENV} profile requires STORAGE_ROOT")
        return str(self.DEFAULT_STORAGE_ROOT)

    def validate(self) -> None:
        if not _non_blank(self.SQLALCHEMY_DATABASE_URI):
            raise ConfigurationError(f"{self.APP_ENV} profile requires DATABASE_URL")
        if not _non_blank(self.STORAGE_ROOT):
            raise ConfigurationError(f"{self.APP_ENV} profile requires STORAGE_ROOT")
