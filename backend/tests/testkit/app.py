"""Isolated Flask/SQLite application builder for module tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app import create_app
from app.extensions import db
from config import Config

_TEST_SECRET = "module-test-secret-is-not-used-outside-tests-2026"

# These values are the isolation boundary, not ordinary test customization.
# Refusing even a seemingly-safe override keeps a future environment/config
# change from silently turning a unit test into a production/demo client.
_PROTECTED_ISOLATION_KEYS = frozenset(
    {
        "APP_ENV",
        "AUTO_BOOTSTRAP",
        "BIM_CAD_EXPERIMENT_ENABLED",
        "DEPLOYMENT_ROLE",
        "ELN_ENABLED",
        "ELN_LEGACY_INTEGRATION_ENABLED",
        "EXTERNAL_SIDE_EFFECTS_ENABLED",
        "PROD",
        "SQLALCHEMY_DATABASE_URI",
        "STORAGE_ROOT",
        "TESTING",
        "AI_ENABLED",
        "AI_VOICE_ENABLED",
        "AI_SEARCH_V2_ENABLED",
        "AI_ANALYSIS_ENABLED",
        "AI_RERANK_ENABLED",
    }
)


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def assert_isolated_app(app, tmp_path: Path) -> None:
    """Prove the live app still uses a private SQLite DB and file root."""

    root = Path(tmp_path).resolve()
    storage = Path(str(app.config.get("STORAGE_ROOT") or "")).resolve()
    if (
        not app.config.get("TESTING")
        or app.config.get("PROD")
        or app.config.get("AUTO_BOOTSTRAP")
        or app.config.get("APP_ENV") != "testing"
        or app.config.get("DEPLOYMENT_ROLE") != "validation"
    ):
        raise RuntimeError("testkit application profile escaped isolated testing mode")
    if not _is_within(storage, root):
        raise RuntimeError("testkit STORAGE_ROOT escaped pytest tmp_path")
    if app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED"):
        raise RuntimeError("testkit external side effects must remain disabled")
    if any(
        app.config.get(key)
        for key in (
            "ELN_ENABLED",
            "ELN_LEGACY_INTEGRATION_ENABLED",
            "AI_ENABLED",
            "AI_VOICE_ENABLED",
            "AI_SEARCH_V2_ENABLED",
            "AI_ANALYSIS_ENABLED",
            "AI_RERANK_ENABLED",
            "BIM_CAD_EXPERIMENT_ENABLED",
        )
    ):
        raise RuntimeError("testkit optional/external modules must remain disabled")
    with app.app_context():
        engine_url = db.engine.url
        if engine_url.get_backend_name() != "sqlite" or not engine_url.database:
            raise RuntimeError("testkit database must be a file-backed SQLite database")
        database = Path(str(engine_url.database)).resolve()
        if not _is_within(database, root):
            raise RuntimeError("testkit SQLite database escaped pytest tmp_path")


def isolated_config(tmp_path: Path, overrides: Mapping[str, Any] | None = None):
    """Build a side-effect-free configuration class for a single test."""

    overrides = dict(overrides or {})
    forbidden = sorted(_PROTECTED_ISOLATION_KEYS.intersection(overrides))
    if forbidden:
        raise ValueError(
            "testkit isolation settings cannot be overridden: "
            + ", ".join(forbidden)
        )
    database_path = (Path(tmp_path) / "module-test.sqlite3").resolve()
    storage_path = (Path(tmp_path) / "stored-files").resolve()
    values: dict[str, Any] = {
        "APP_ENV": "testing",
        "TESTING": True,
        "PROD": False,
        "AUTO_BOOTSTRAP": False,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "STORAGE_ROOT": str(storage_path),
        "JWT_SECRET": _TEST_SECRET,
        "JWT_SECRET_IS_DEFAULT": False,
        "PUBLIC_JWT_SECRET": f"public-{_TEST_SECRET}",
        "PUBLIC_JWT_SECRET_IS_DEFAULT": False,
        "ELN_SESSION_SECRET": f"eln-{_TEST_SECRET}",
        "ELN_SESSION_SECRET_IS_DEFAULT": False,
        "DEPLOYMENT_ROLE": "validation",
        "ENVIRONMENT_LABEL": "自动化测试隔离环境",
        "RELEASE_ID": "testkit-local",
        "EXTERNAL_SIDE_EFFECTS_ENABLED": False,
        "APP_BUSINESS_READ_ONLY": False,
        "ELN_ENABLED": False,
        "ELN_LEGACY_INTEGRATION_ENABLED": False,
        "AI_ENABLED": False,
        "AI_VOICE_ENABLED": False,
        "AI_SEARCH_V2_ENABLED": False,
        "AI_ANALYSIS_ENABLED": False,
        "AI_RERANK_ENABLED": False,
        "BIM_CAD_EXPERIMENT_ENABLED": False,
        "REPORT_RENDER_SYNC": True,
    }
    values.update(overrides)
    return type("IsolatedModuleTestConfig", (Config,), values)


def create_isolated_app(tmp_path: Path, overrides: Mapping[str, Any] | None = None):
    """Create a new app, empty schema and private attachment directory.

    The helper never calls seed functions and never connects to a configured
    production or demo database.  Tests opt into only the virtual records they
    need through :class:`testkit.factories.ScenarioFactory`.
    """

    config = isolated_config(Path(tmp_path), overrides)
    app = create_app(config)
    assert_isolated_app(app, Path(tmp_path))
    with app.app_context():
        db.create_all()
    return app


__all__ = ["assert_isolated_app", "create_isolated_app", "isolated_config"]
