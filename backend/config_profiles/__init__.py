from __future__ import annotations

import os
from collections.abc import Mapping

from .base import BaseConfig, ConfigurationError
from .development import DevelopmentConfig
from .production import ProductionConfig
from .testing import TestingConfig

_PROFILES = {
    "dev": DevelopmentConfig,
    "development": DevelopmentConfig,
    "local": DevelopmentConfig,
    "test": TestingConfig,
    "testing": TestingConfig,
    "prod": ProductionConfig,
    "production": ProductionConfig,
}


def get_config_profile(environ: Mapping[str, str] | None = None) -> BaseConfig:
    source = os.environ if environ is None else environ
    configured_name = source.get("APP_ENV")
    # 兼容既有部署开关；显式 APP_ENV 始终优先。
    default_name = "production" if source.get("LIMS_PROD") == "1" else "development"
    name = str(configured_name or default_name).strip().lower()
    profile_type = _PROFILES.get(name)
    if profile_type is None:
        raise ConfigurationError(
            "APP_ENV must be one of: development, testing, production"
        )
    return profile_type(source)


__all__ = [
    "BaseConfig",
    "ConfigurationError",
    "DevelopmentConfig",
    "ProductionConfig",
    "TestingConfig",
    "get_config_profile",
]
