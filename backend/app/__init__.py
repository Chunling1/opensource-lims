import os

from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from config_profiles import get_config_profile

from .extensions import db, migrate
from .functions.database_compat import install_database_compatibility

install_database_compatibility()


def _production_masterdata_is_protected(app):
    """Return true when automatic seed writes must never touch this database."""
    database_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
    normalized_uri = database_uri.replace("\\", "/").lower()
    return any((
        bool(app.config.get("PROD")),
        str(app.config.get("APP_ENV") or "").lower() == "production",
        os.environ.get("MASTER_DATA_PROTECTED") == "1",
        "/opt/lims/data/" in normalized_uri,
    ))


def create_app(config_object=None):
    app = Flask(__name__)
    from .edit_concurrency import install_conflict_handler
    install_conflict_handler(app)
    from .http_compression import install_compression
    install_compression(app)
    # Config 保留安全及兼容设置；环境 profile 只负责数据库、存储和启动策略。
    app.config.from_object(Config)
    app.config.from_object(config_object or get_config_profile())
    # esign-production-v1
    from .esign_production import configure as configure_esign_production
    configure_esign_production(app)
    app.config["JSON_AS_ASCII"] = False

    from .docparser_field_only import ENGINE as docparser_engine
    template_engine = app.config.get("DOCUMENT_TEMPLATE_ENGINE", "legacy")
    if template_engine not in {"legacy", docparser_engine}:
        raise RuntimeError("DOCUMENT_TEMPLATE_ENGINE is invalid")
    if (app.config.get("PROD") and template_engine == docparser_engine
            and not app.config.get("DOCPARSER_ROLLOUT_STARTED_AT")):
        raise RuntimeError(
            "生产启用原包委托/报告模板时必须设置 DOCPARSER_ROLLOUT_STARTED_AT，禁止改写历史文件"
        )

    from .external_side_effects import validate_deployment_isolation
    validate_deployment_isolation(app)

    # 生产硬化 fail-fast：默认/过短 JWT 密钥、宽松 CORS、缺 bcrypt 一律拒绝启动
    if app.config.get("PROD"):
        if app.config.get("JWT_SECRET_IS_DEFAULT") or len(app.config.get("JWT_SECRET") or "") < 32:
            raise RuntimeError(
                "生产模式(LIMS_PROD=1)拒绝启动：JWT_SECRET 缺失/为默认值/不足 32 字节。请注入随机长密钥。"
            )
        if (
            app.config.get("PUBLIC_JWT_SECRET_IS_DEFAULT")
            or len(app.config.get("PUBLIC_JWT_SECRET") or "") < 32
            or app.config.get("PUBLIC_JWT_SECRET") == app.config.get("JWT_SECRET")
        ):
            raise RuntimeError(
                "生产模式拒绝启动：PUBLIC_JWT_SECRET 必须是独立于内部 JWT 的随机长密钥。"
            )
        if app.config.get("ELN_ENABLED") and (
            app.config.get("ELN_SESSION_SECRET_IS_DEFAULT")
            or len(app.config.get("ELN_SESSION_SECRET") or "") < 32
            or app.config.get("ELN_SESSION_SECRET")
            in {app.config.get("JWT_SECRET"), app.config.get("PUBLIC_JWT_SECRET")}
        ):
            raise RuntimeError(
                "生产模式启用 ELN 时，ELN_SESSION_SECRET 必须是独立随机长密钥。"
            )
        if app.config.get("CORS_ORIGINS", "*") == "*":
            raise RuntimeError("生产模式拒绝启动：CORS_ORIGINS 不能为 *，请设置具体域名白名单。")
        from .security import _HAS_BCRYPT
        if not _HAS_BCRYPT:
            raise RuntimeError("生产模式拒绝启动：未安装 bcrypt，不允许 sha256 降级。请 pip install bcrypt。")

    db.init_app(app)
    migrate.init_app(app, db)
    from .report_preview_revision import install as install_preview_revisions
    install_preview_revisions()
    cfg_origins = app.config.get("CORS_ORIGINS", "*")
    origins = "*" if cfg_origins == "*" else [o.strip() for o in cfg_origins.split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins}})

    from .business_read_only import install_business_read_only_guard
    install_business_read_only_guard(app)

    from .external_side_effects import install_external_side_effect_guard
    install_external_side_effect_guard(app)

    from .blueprints.admin import bp as admin_bp
    from .blueprints.ai import bp as ai_bp
    from .blueprints.attachments import bp as attachments_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.bim_cad import bp as bim_cad_bp
    from .blueprints.customers import bp as customers_bp
    from .blueprints.eln import bp as eln_bp
    from .blueprints.eln_integration import bp as eln_integration_bp
    from .blueprints.esign import bp as esign_bp
    from .blueprints.entrust import bp as entrust_bp
    from .blueprints.exports import bp as exports_bp
    from .blueprints.finance import bp as finance_bp
    from .blueprints.permission_templates import bp as permission_templates_bp
    from .blueprints.public_portal import (
        admin_external_bp,
        public_bp,
    )
    from .blueprints.quality import bp as quality_bp
    from .blueprints.report_documents import bp as report_documents_bp
    from .blueprints.reports import bp as reports_bp
    from .blueprints.samples import bp as samples_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(bim_cad_bp)
    app.register_blueprint(ai_bp)
    from .blueprints.equipment_schemes import bp as equipment_schemes_bp
    app.register_blueprint(equipment_schemes_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(report_documents_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(attachments_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(permission_templates_bp)
    app.register_blueprint(samples_bp)
    app.register_blueprint(entrust_bp)
    app.register_blueprint(eln_integration_bp)
    app.register_blueprint(esign_bp)
    from .blueprints.business_supplement import bp as business_supplement_bp
    app.register_blueprint(business_supplement_bp)
    from .blueprints.report_assurance import bp as report_assurance_bp
    from .blueprints.report_publication import bp as report_publication_bp, short_bp as report_shortlink_bp
    from .blueprints.technical_subprojects import bp as technical_subprojects_bp
    app.register_blueprint(report_assurance_bp)
    app.register_blueprint(report_publication_bp)
    app.register_blueprint(report_shortlink_bp)
    app.register_blueprint(technical_subprojects_bp)
    app.register_blueprint(eln_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_external_bp)
    from .blueprints.system_config import apply_esign_config_to_app, bp as system_config_bp
    app.register_blueprint(system_config_bp)

    from .readiness import install_readiness
    install_readiness(app)

    @app.get("/api/health")
    def health():
        return jsonify({
            "code": 0,
            "message": "ok",
            "data": {
                "status": "up",
                "deploymentRole": app.config.get(
                    "DEPLOYMENT_ROLE", "standard"
                ),
                "environmentLabel": app.config.get("ENVIRONMENT_LABEL", "开源标准版"),
                "releaseId": app.config.get("RELEASE_ID", "local"),
                "businessReadOnly": bool(app.config.get("APP_BUSINESS_READ_ONLY")),
                "externalSideEffectsEnabled": bool(
                    app.config.get("EXTERNAL_SIDE_EFFECTS_ENABLED", True)
                ),
            },
        })

    # 安全响应头统一由前置 nginx 注入（见 deploy-server.sh），单一来源避免与代理层重复导致头值失效。

    from .commands import register_commands
    register_commands(app)

    # 开发/自动化测试保留即开即用；生产只允许显式执行迁移和初始化命令。
    if app.config.get("AUTO_BOOTSTRAP") and _production_masterdata_is_protected(app):
        raise RuntimeError(
            "生产主数据库禁止 AUTO_BOOTSTRAP：部门、人员权限、标准和仪器主数据只能通过显式迁移变更"
        )
    if app.config.get("AUTO_BOOTSTRAP"):
        with app.app_context():
            from .seed import seed_all

            seed_all()
            apply_esign_config_to_app(app)
    from .admin_corrections import init_app as init_admin_corrections
    init_admin_corrections(app)
    if app.config.get("AUTO_BOOTSTRAP"):
        with app.app_context():
            db.create_all()
    return app
