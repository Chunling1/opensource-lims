from .base import BaseConfig, ConfigurationError, _non_blank


class ProductionConfig(BaseConfig):
    APP_ENV = "production"
    PROD = True
    SEED_PROFILE = "production"

    def __init__(self, environ=None):
        super().__init__(environ)
        if self.AUTO_BOOTSTRAP:
            raise ConfigurationError("production profile forbids AUTO_BOOTSTRAP")

    def resolve_database_url(self) -> str:
        value = _non_blank(self._environ.get("DATABASE_URL"))
        if not value:
            raise ConfigurationError("production profile requires DATABASE_URL")
        return value

    def resolve_storage_root(self) -> str:
        value = _non_blank(self._environ.get("STORAGE_ROOT"))
        if not value:
            raise ConfigurationError("production profile requires STORAGE_ROOT")
        return value
