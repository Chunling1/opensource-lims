from .base import BACKEND_DIR, BaseConfig, _non_blank


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    TESTING = True
    REPORT_RENDER_SYNC = True
    SEED_PROFILE = "testing"
    AUTO_BOOTSTRAP = True
    DEFAULT_DATABASE_URL = "sqlite:///:memory:"
    DEFAULT_STORAGE_ROOT = BACKEND_DIR / "instance" / "storage" / "testing"

    def resolve_database_url(self) -> str:
        return (
            _non_blank(self._environ.get("TEST_DATABASE_URL"))
            or self.DEFAULT_DATABASE_URL
        )

    def resolve_storage_root(self) -> str:
        value = (
            _non_blank(self._environ.get("TEST_STORAGE_ROOT"))
        )
        return value or str(self.DEFAULT_STORAGE_ROOT)
