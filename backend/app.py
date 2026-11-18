import os
import secrets
from datetime import date
from pathlib import Path
from uuid import UUID

from flask import Flask, jsonify, request, send_from_directory, session
from flask.json.provider import DefaultJSONProvider
from sqlalchemy import create_engine, event, select
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from .commands import perform
from .policy import Problem, visible_samples
from .schema import files, notices, reports, samples, users
from .views import detail, sample_list, report_list
from .worklist import worklist


class ProductJSON(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, date):
            return value.isoformat()
        return DefaultJSONProvider.default(value)


FIELDS = {
    "claim": (),
    "return": ("reason",),
    "transfer": ("reason", "targetId"),
    "create": ("ruleId",),
    "cancel": ("reportId", "reason"),
    "upload": ("reportId", "kind", "replaces?"),
    "submit": ("reportId", "start", "end", "reviewerId?", "siteDate?"),
}


def command_input(action):
    if action not in FIELDS:
        raise Problem("动作不存在。", 404)
    body = request.form.to_dict() if action == "upload" else request.get_json()
    if not isinstance(body, dict):
        raise Problem("请求格式错误。", 400)
    fields = ("requestId", "version", *FIELDS[action])
    allowed = {f.rstrip("?") for f in fields}
    if set(body) - allowed or any(f not in body for f in fields if not f.endswith("?")):
        raise Problem("动作字段缺少或无法识别。", 400)
    try:
        body["requestId"] = str(UUID(body["requestId"]))
        for field in body.keys() & {
            "version",
            "targetId",
            "reviewerId",
            "ruleId",
            "reportId",
            "replaces",
        }:
            value = body[field]
            if type(value) is not int and not (
                action == "upload" and isinstance(value, str) and value.isdecimal()
            ):
                raise ValueError()
            body[field] = int(value)
            if not 0 < body[field] <= 2147483647:
                raise ValueError()
        for field in body.keys() & {"start", "end", "siteDate"}:
            body[field] = date.fromisoformat(body[field])
        for field in body.keys() & {"reason", "kind"}:
            if not isinstance(body[field], str) or not body[field].strip():
                raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise Problem("请核对办理原因、编号和日期。", 400) from None
    return body


def make_app(instance, url=None):
    root = Path(instance).resolve()
    root.mkdir(exist_ok=True, parents=True)
    storage = root / "files"
    storage.mkdir(exist_ok=True)
    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    app = Flask(__name__, static_folder=str(dist / "assets"), static_url_path="/assets")
    app.json = ProductJSON(app)
    key = root / "session.key"
    if not key.exists():
        key.write_bytes(secrets.token_bytes(32))
    limit = int(os.environ.get("LIMS_PDF_MB", "50")) * 1024 * 1024
    app.config.update(
        SECRET_KEY=key.read_bytes(),
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=limit + 1024 * 1024,
    )
    engine = create_engine(url or f"sqlite:///{root / 'demo.db'}")
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def sqlite_settings(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")

    app.extensions["engine"] = engine

    def actor(db):
        row = db.execute(select(users).where(users.c.id == session.get("uid"))).first()
        if not row:
            raise Problem("请先登录。", 401)
        return row

    @app.before_request
    def verify_browser_action():
        if request.method == "POST" and request.headers.get("X-LIMS-Action") != "1":
            raise Problem("请求未携带操作标识。", 403)

    @app.after_request
    def private_response(response):
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(Problem)
    def problem(error):
        return jsonify(error=str(error)), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(
            error="文件超过大小上限。" if error.code == 413 else error.description
        ), error.code

    @app.post("/api/login")
    def login():
        body = request.get_json()
        if not isinstance(body, dict) or not all(
            isinstance(body.get(k), str) for k in ("account", "password")
        ):
            raise Problem("请填写账号和密码。", 400)
        with engine.connect() as db:
            u = db.execute(select(users).where(users.c.account == body["account"])).first()
            if not u or not check_password_hash(u.password_hash, body["password"]):
                raise Problem("账号或密码错误。", 401)
            session.clear()
            session["uid"] = u.id
            return jsonify(name=u.name, department=u.department, permissions=u.permissions)

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        with engine.connect() as db:
            u = actor(db)
            return jsonify(name=u.name, department=u.department, permissions=u.permissions)

    def pagination():
        try:
            page=int(request.args.get("page","1"))
            size=int(request.args.get("pageSize","10"))
        except ValueError:
            raise Problem("分页参数无效。",400) from None
        if not 1<=page<=1000000 or size not in (10,20,50):
            raise Problem("分页参数无效。",400)
        return page,size

    @app.get("/api/tasks")
    def my_tasks():
        page,size=pagination()
        with engine.connect() as db:
            return jsonify(worklist(db,actor(db),request.args,page,size))

    @app.get("/api/samples")
    def listing():
        view = request.args.get("view", "pool")
        page,size = pagination()
        if (
            view not in {"pool", "mine"}

            or request.args.get("state", "") not in {"", "pool", "mine", "frozen"}
        ):
            raise Problem("筛选参数无效。", 400)
        with engine.connect() as db:
            return jsonify(sample_list(db, actor(db), view, request.args, page,size))

    @app.get("/api/reports")
    def report_listing():
        page,size = pagination()
        if request.args.get("state", "") not in {"", "draft", "review", "cancelled"}:
            raise Problem("筛选参数无效。", 400)
        with engine.connect() as db:
            return jsonify(report_list(db, actor(db), request.args, page,size))

    @app.get("/api/samples/<int:sid>")
    def get_sample(sid):
        with engine.begin() as db:
            return jsonify(detail(db, actor(db), sid))

    @app.post("/api/samples/<int:sid>/<action>")
    def execute(sid, action):
        data = command_input(action)
        created = []
        try:
            with engine.begin() as db:
                if engine.dialect.name == "sqlite":
                    db.exec_driver_sql("BEGIN IMMEDIATE")
                u = actor(db)
                # Consistent lock order serializes reuse of a user's request key across samples.
                db.execute(select(users.c.id).where(users.c.id == u.id).with_for_update()).first()
                result = perform(
                    db, u, sid, action, data, request.files.get("file"), storage, created, limit
                )
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        if "error" in result:
            raise Problem(result["error"])
        return jsonify(result)

    @app.get("/api/files/<int:fid>")
    def download(fid):
        with engine.connect() as db:
            u = actor(db)
            doc = db.execute(
                select(files.c.key, files.c.name)
                .select_from(files)
                .join(reports, reports.c.id == files.c.report_id)
                .join(samples, samples.c.id == reports.c.sample_id)
                .where(files.c.id == fid, visible_samples(u))
            ).first()
            if doc is None:
                raise Problem("文件不存在或超出数据范围。", 404)
            return send_from_directory(
                storage, doc.key, download_name=doc.name, mimetype="application/pdf", as_attachment=True
            )

    @app.get("/api/notices")
    def catalog_notices():
        with engine.connect() as db:
            u = actor(db)
            if "catalog" not in u.permissions:
                raise Problem("需要资料管理权限。", 403)
            query = (
                select(notices.c.message, reports.c.number)
                .select_from(notices)
                .join(reports, reports.c.id == notices.c.report_id)
                .join(samples, samples.c.id == reports.c.sample_id)
                .where(samples.c.department == u.department)
                .order_by(notices.c.id.desc())
            )
            return jsonify([dict(row._mapping) for row in db.execute(query)])

    @app.get("/")
    def index():
        return send_from_directory(dist, "index.html")

    return app
