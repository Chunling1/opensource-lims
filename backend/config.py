import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 默认开发密钥；生产必须经环境变量覆盖（见 __init__ 的 fail-fast）
_DEFAULT_JWT = "lims-inspection-dev-secret-key-2026-please-override-in-prod"
_DEFAULT_PUBLIC_JWT = "lims-external-portal-dev-secret-key-2026-override-in-prod"
_DEFAULT_ELN_JWT = "lims-eln-dev-secret-key-2026-override-separately"


def _environment_boolean(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean")


_DEPLOYMENT_ROLE = os.environ.get(
    "DEPLOYMENT_ROLE", "standard"
).strip().lower()
_DEFAULT_ENVIRONMENT_LABEL = {
    "standard": "开源标准版",
    "validation": "验证环境",
    "production": "正式生产",
}.get(_DEPLOYMENT_ROLE, "开源标准版")

_INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(_INSTANCE_DIR, exist_ok=True)


class Config:
    LIST_PAGE_IDS = _environment_boolean("LIST_PAGE_IDS", False)
    LIST_QUERY_A2 = _environment_boolean("LIST_QUERY_A2", False)
    LIST_QUERY_PROTOTYPE = _environment_boolean("LIST_QUERY_PROTOTYPE", False)
    REPORT_QUERY_ORIGIN = os.environ.get('REPORT_QUERY_ORIGIN', 'https://lims.example.com')
    # Explicit per-report public display redaction; never changes signed snapshots.
    REPORT_QUERY_REDACT_PROJECT_NAMES = frozenset(
        value.strip() for value in os.environ.get('REPORT_QUERY_REDACT_PROJECT_NAMES', '').split(',')
        if value.strip()
    )
    # 开发用 SQLite；生产可通过 DATABASE_URL 切换到 MariaDB/MySQL/PostgreSQL/达梦/人大金仓/GaussDB
    # SQLAlchemy 抽象层保证国产信创数据库可平滑替换
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(_INSTANCE_DIR, "inspection.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    # OAuth2 资源所有者密码模式签发的 JWT 密钥（生产经环境变量注入 ≥32 字节随机值）
    JWT_SECRET = os.environ.get("JWT_SECRET") or _DEFAULT_JWT
    JWT_SECRET_IS_DEFAULT = JWT_SECRET == _DEFAULT_JWT
    JWT_EXPIRES_SECONDS = int(os.environ.get("JWT_EXPIRES_SECONDS", "28800"))  # 8h
    # 外部客户身份域使用独立密钥、签发方和受众，严禁与内部员工 JWT 混用。
    PUBLIC_JWT_SECRET = os.environ.get("PUBLIC_JWT_SECRET") or _DEFAULT_PUBLIC_JWT
    PUBLIC_JWT_SECRET_IS_DEFAULT = PUBLIC_JWT_SECRET == _DEFAULT_PUBLIC_JWT
    PUBLIC_JWT_EXPIRES_SECONDS = int(
        os.environ.get("PUBLIC_JWT_EXPIRES_SECONDS", "28800")
    )
    PUBLIC_JWT_ISSUER = os.environ.get(
        "PUBLIC_JWT_ISSUER", "lims-external-portal"
    )
    PUBLIC_JWT_AUDIENCE = os.environ.get(
        "PUBLIC_JWT_AUDIENCE", "lims-external-customer"
    )
    # 生产硬化开关：LIMS_PROD=1 时强制改密播种 + 拒绝默认 JWT 密钥启动 + HSTS
    PROD = os.environ.get("LIMS_PROD") == "1"
    # 生产播种 admin 初始口令（仅 PROD 生效，必填，禁止 123456 进库）
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    # 请求体上限（默认 32MB，与 nginx client_max_body_size 对齐）
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(32 * 1024 * 1024)))
    BIM_CAD_EXPERIMENT_ENABLED = os.environ.get("BIM_CAD_EXPERIMENT_ENABLED", "0") == "1"
    BIM_CAD_MODEL_PATH = os.environ.get("BIM_CAD_MODEL_PATH", "")
    BIM_CAD_MAX_BYTES = int(os.environ.get("BIM_CAD_MAX_BYTES", str(20 * 1024 * 1024)))
    BIM_CAD_MAX_SIDE = int(os.environ.get("BIM_CAD_MAX_SIDE", "2048"))
    BIM_CAD_MAX_PIXELS = int(os.environ.get("BIM_CAD_MAX_PIXELS", "6000000"))
    MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", str(30 * 1024 * 1024)))
    # Early standalone service-to-service protocol. It stays fail-closed unless
    # a compatibility rehearsal explicitly enables it; the integrated PWA uses
    # the separate ELN session secret below.
    ELN_SHARED_SECRET = os.environ.get("ELN_SHARED_SECRET", "")
    ELN_LEGACY_INTEGRATION_ENABLED = os.environ.get("ELN_LEGACY_INTEGRATION_ENABLED", "0") == "1"
    ELN_ENABLED = _environment_boolean("ELN_ENABLED", False)
    ELN_BASE_URL = os.environ.get("ELN_BASE_URL", "/eln/").rstrip("/") + "/"
    ELN_SESSION_COOKIE_PATH = os.environ.get(
        "ELN_SESSION_COOKIE_PATH", "/api/eln"
    ).rstrip("/") or "/api/eln"
    ELN_SESSION_SECRET = os.environ.get("ELN_SESSION_SECRET") or _DEFAULT_ELN_JWT
    ELN_SESSION_SECRET_IS_DEFAULT = ELN_SESSION_SECRET == _DEFAULT_ELN_JWT
    ELN_SESSION_EXPIRES_SECONDS = int(os.environ.get("ELN_SESSION_EXPIRES_SECONDS", "28800"))
    ELN_LAUNCH_EXPIRES_SECONDS = int(os.environ.get("ELN_LAUNCH_EXPIRES_SECONDS", "60"))
    ELN_SESSION_COOKIE_NAME = "lims_eln_session"
    # CORS 白名单：逗号分隔域名；默认 * 便于本地/演示，生产经 CORS_ORIGINS 收敛
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    RELEASE_ID = os.environ.get("RELEASE_ID", "local")
    # 双服务器并行期间通过角色区分开源标准版与信创验证线。验证线默认且强制
    # 关闭真实外部推送/回调，仍允许业务数据在自己的隔离库中正常写入测试。
    DEPLOYMENT_ROLE = _DEPLOYMENT_ROLE
    ENVIRONMENT_LABEL = (
        os.environ.get("ENVIRONMENT_LABEL", "").strip()
        or _DEFAULT_ENVIRONMENT_LABEL
    )
    EXTERNAL_SIDE_EFFECTS_ENABLED = _environment_boolean(
        "EXTERNAL_SIDE_EFFECTS_ENABLED",
        DEPLOYMENT_ROLE == "standard",
    )
    # 测试可设为同步生成，生产默认使用持久化任务 + 后台线程，前端轮询进度。
    REPORT_RENDER_SYNC = os.environ.get("REPORT_RENDER_SYNC") == "1"
    # The DocParser source package remains byte-identical under app/docparser_original.
    # Selection/mapping is implemented only by the surrounding adapter and is
    # activated for records created at/after the immutable rollout timestamp.
    DOCUMENT_TEMPLATE_ENGINE = os.environ.get("DOCUMENT_TEMPLATE_ENGINE", "legacy")
    DOCPARSER_ROLLOUT_STARTED_AT = os.environ.get("DOCPARSER_ROLLOUT_STARTED_AT", "")
    DOCPARSER_DEPARTMENT_RULES = os.environ.get("DOCPARSER_DEPARTMENT_RULES", "")
    DOCPARSER_INSTITUTION_PROFILES = os.environ.get("DOCPARSER_INSTITUTION_PROFILES", "{}")
    PUBLIC_REPORT_VERIFICATION_BASE_URL = os.environ.get(
        "PUBLIC_REPORT_VERIFICATION_BASE_URL",
        "https://8.219.128.132/service/reports",
    )
    # 旧测试配置继续继承本类；正常启动由 config_profiles 决定环境。
    APP_ENV = os.environ.get("APP_ENV", "development")
    STORAGE_ROOT = os.environ.get(
        "STORAGE_ROOT", os.path.join(BASE_DIR, "instance", "storage", "development")
    )
    # 默认不写入主数据；开发 profile 会显式启用，生产必须始终保持关闭。
    AUTO_BOOTSTRAP = os.environ.get("AUTO_BOOTSTRAP", "0") == "1"
    # Acceptance environments can exercise reads, previews, search and voice
    # without creating a second writable business system before cut-over.
    APP_BUSINESS_READ_ONLY = os.environ.get("APP_BUSINESS_READ_ONLY", "0") == "1"
    # AI is fail-closed. Credentials and the approved Beijing workspace endpoint
    # are injected by the platform secret manager and are never stored in source.
    AI_ENABLED = os.environ.get("AI_ENABLED", "0") == "1"
    AI_VOICE_ENABLED = os.environ.get("AI_VOICE_ENABLED", "0") == "1"
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "bailian")
    AI_BASE_URL = os.environ.get("AI_BASE_URL", "")
    AI_ALLOWED_HOSTS = os.environ.get(
        "AI_ALLOWED_HOSTS",
        "dashscope.aliyuncs.com,.cn-beijing.maas.aliyuncs.com",
    )
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_CHAT_MODEL = os.environ.get("AI_CHAT_MODEL", "qwen-plus")
    AI_ASR_MODEL = os.environ.get("AI_ASR_MODEL", "qwen3-asr-flash")
    AI_HTTP_TIMEOUT_SECONDS = int(os.environ.get("AI_HTTP_TIMEOUT_SECONDS", "45"))
    AI_AUDIO_MAX_BYTES = int(os.environ.get("AI_AUDIO_MAX_BYTES", str(8 * 1024 * 1024)))
    AI_AUDIO_MAX_SECONDS = int(os.environ.get("AI_AUDIO_MAX_SECONDS", "90"))
    AI_INDEX_BATCH_SIZE = int(os.environ.get("AI_INDEX_BATCH_SIZE", "500"))
    AI_INDEX_INTERVAL_SECONDS = int(os.environ.get("AI_INDEX_INTERVAL_SECONDS", "30"))
    AI_INDEX_ON_REQUEST = os.environ.get("AI_INDEX_ON_REQUEST", "1") == "1"
    AI_SEARCH_V2_ENABLED = os.environ.get("AI_SEARCH_V2_ENABLED", "0") == "1"
    AI_ANALYSIS_ENABLED = os.environ.get("AI_ANALYSIS_ENABLED", "0") == "1"
    AI_RERANK_ENABLED = os.environ.get("AI_RERANK_ENABLED", "0") == "1"
    AI_RERANK_CANDIDATES = int(os.environ.get("AI_RERANK_CANDIDATES", "30"))
    AI_ANALYSIS_MAX_SOURCES = int(os.environ.get("AI_ANALYSIS_MAX_SOURCES", "20"))
    AI_CHAT_MAX_TURNS = int(os.environ.get("AI_CHAT_MAX_TURNS", "6"))
    # e签宝报告签发。所有凭据仅由服务器环境注入；源码和前端不保存 AppSecret。
    # 初次上线可仅打开 WORKFLOW 建立本地任务，待回调、印章授权和人员绑定
    # 验收后再打开 ESIGN_ENABLED 与 REQUIRED_FOR_ISSUANCE。
    ESIGN_STAGE_WORKFLOW_ENABLED = _environment_boolean("ESIGN_STAGE_WORKFLOW_ENABLED", False)
    ESIGN_WORKFLOW_ENABLED = _environment_boolean("ESIGN_WORKFLOW_ENABLED", False)
    ESIGN_ENABLED = _environment_boolean("ESIGN_ENABLED", False)
    ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED = _environment_boolean("ESIGN_EXTERNAL_SIDE_EFFECTS_ENABLED", False)
    ESIGN_PROVIDER_FLOW_MIN_ID = int(os.environ.get("ESIGN_PROVIDER_FLOW_MIN_ID", "0"))
    ESIGN_REQUIRED_FOR_ISSUANCE = _environment_boolean("ESIGN_REQUIRED_FOR_ISSUANCE", False)
    ESIGN_ENVIRONMENT = os.environ.get("ESIGN_ENVIRONMENT", "sandbox").strip().lower()
    ESIGN_BASE_URL = os.environ.get(
        "ESIGN_BASE_URL",
        "https://smlopenapi.esign.cn" if ESIGN_ENVIRONMENT == "sandbox" else "https://openapi.esign.cn",
    ).rstrip("/")
    ESIGN_APP_ID = os.environ.get("ESIGN_APP_ID", "")
    ESIGN_APP_SECRET = os.environ.get("ESIGN_APP_SECRET", "")
    ESIGN_CALLBACK_PUBLIC_URL = os.environ.get("ESIGN_CALLBACK_PUBLIC_URL", "")
    ESIGN_BATCH_REDIRECT_URL = os.environ.get("ESIGN_BATCH_REDIRECT_URL", "")
    ESIGN_HTTP_TIMEOUT_SECONDS = int(os.environ.get("ESIGN_HTTP_TIMEOUT_SECONDS", "30"))
    ESIGN_CALLBACK_MAX_SKEW_SECONDS = int(os.environ.get("ESIGN_CALLBACK_MAX_SKEW_SECONDS", "300"))
    ESIGN_POSITION_KEYWORDS = os.environ.get("ESIGN_POSITION_KEYWORDS", "")
    ESIGN_POSITION_OFFSETS = os.environ.get("ESIGN_POSITION_OFFSETS", "")
    ESIGN_POSITIONING_REDIRECT_URL = os.environ.get("ESIGN_POSITIONING_REDIRECT_URL", "")
    ESIGN_ORG_AUTOSIGN_ENABLED = _environment_boolean("ESIGN_ORG_AUTOSIGN_ENABLED", False)
    ESIGN_ORG_ID = os.environ.get("ESIGN_ORG_ID", "")
    ESIGN_ORG_NAME = os.environ.get("ESIGN_ORG_NAME", "")
    ESIGN_ORG_SEAL_ID = os.environ.get("ESIGN_ORG_SEAL_ID", "")
    ESIGN_ACROSS_SEAL_POSITION_Y = float(os.environ.get("ESIGN_ACROSS_SEAL_POSITION_Y", "420"))
    ESIGN_INITIAL_SMS_ENABLED = _environment_boolean("ESIGN_INITIAL_SMS_ENABLED", False)
    ESIGN_DAILY_SMS_HOUR = int(os.environ.get("ESIGN_DAILY_SMS_HOUR", "9"))
