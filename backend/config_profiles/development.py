from .base import BACKEND_DIR, BaseConfig


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    SEED_PROFILE = "development"
    AUTO_BOOTSTRAP = True
    # 保留历史开发库位置，切换配置体系不会让本地数据“消失”。
    DEFAULT_DATABASE_URL = "sqlite:///" + (BACKEND_DIR / "instance" / "inspection.db").as_posix()
    DEFAULT_STORAGE_ROOT = BACKEND_DIR / "instance" / "storage" / "development"
