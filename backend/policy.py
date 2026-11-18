from datetime import date
from sqlalchemy import and_, or_, exists, select
from .schema import events, files, grants, items, reports, samples, templates, users


class Problem(Exception):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def covers(user_id, sample_id, duty):
    """All requested project/method pairs must have a current grant."""
    active = (
        select(grants.c.id)
        .where(
            grants.c.user_id == user_id,
            grants.c.scope == items.c.scope,
            grants.c.duty == duty,
            grants.c.start <= date.today(),
            grants.c.end >= date.today(),
        )
        .correlate_except(grants)
    )
    missing = (
        select(items.c.scope)
        .where(items.c.sample_id == sample_id, ~active.exists())
        .correlate_except(items)
    )
    return ~missing.exists()


def visible_samples(actor):
    if actor.data_scope == "all":
        return True
    assigned = (
        exists()
        .where(reports.c.sample_id == samples.c.id, reports.c.reviewer == actor.id)
        .correlate_except(reports)
    )
    own = (
        (samples.c.owner == actor.id)
        | assigned
        | exists()
        .where(events.c.sample_id == samples.c.id, events.c.actor == actor.id)
        .correlate_except(events)
    )
    if actor.data_scope == "self":
        return own
    return (samples.c.department == actor.department) | own


def pool_scope(actor):
    return and_(
        (True if actor.data_scope == "all" else samples.c.department == actor.department),
        samples.c.owner.is_(None),
        samples.c.reviewed,
        ~samples.c.frozen,
        (~templates.c.receive_required | samples.c.received),
        covers(actor.id, samples.c.id, "test"),
        "claim" in actor.permissions,
    )


def current_documents(db, report_id):
    replacement = files.alias("replacement")
    return (
        db.execute(
            select(files, users.c.name.label("uploader"))
            .join(users)
            .where(
                files.c.report_id == report_id,
                ~exists(select(replacement.c.id).where(replacement.c.replaces == files.c.id)),
            )
            .order_by(files.c.id)
        )
        .mappings()
        .all()
    )


def notify_catalog(db, report_id):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from .schema import notices

    insert = sqlite_insert if db.dialect.name == "sqlite" else pg_insert
    db.execute(
        insert(notices)
        .values(report_id=report_id, audience="catalog", message="本报告无合格审核人，请核对技术授权。")
        .on_conflict_do_nothing(index_elements=["report_id", "audience"])
    )


class SamplePolicy:
    def __init__(self, db, actor, sample_id):
        self.db, self.actor = db, actor
        self.row = db.execute(
            select(
                samples,
                templates.c.label,
                templates.c.physical,
                templates.c.receive_required,
                templates.c.review_mode,
            )
            .join(templates)
            .where(samples.c.id == sample_id, or_(visible_samples(actor), pool_scope(actor)))
        ).first()
        if self.row is None:
            raise Problem("样品不存在或超出数据范围。", 404)
        self.allowed = db.scalar(select(covers(actor.id, sample_id, "test")))
        self.has_upload = db.scalar(
            select(exists().where(files.c.report_id == reports.c.id, reports.c.sample_id == sample_id))
        )

    def candidates(self, duty, report_id=None):
        query = select(users).where(covers(users.c.id, self.row.id, duty)).order_by(users.c.id)
        if duty == "review":
            authors = select(events.c.actor).where(
                events.c.report_id == report_id, events.c.action.in_(("create", "upload", "submit"))
            )
            query = query.where(users.c.id != self.row.owner, ~users.c.id.in_(authors))
        return [
            dict(id=u.id, name=u.name)
            for u in self.db.execute(query)
            if duty in u.permissions and (duty != "test" or u.id != self.row.owner)
        ]

    def actions(self):
        s, a = self.row, self.actor
        result = {}
        blocked = "样品已冻结。" if s.frozen else ""
        if (
            "claim" in a.permissions
            and s.owner is None
            and (a.data_scope == "all" or a.department == s.department)
        ):
            result["claim"] = (
                blocked
                or ("" if s.reviewed else "请先完成委托评审。")
                or ("请先完成收样确认。" if s.receive_required and not s.received else "")
                or ("" if self.allowed else "当前检测授权未覆盖样品全部项目和方法。")
            )
        if s.owner == a.id:
            result["return"] = blocked or ("已上传资料，请走转交。" if self.has_upload else "")
            if "test" in a.permissions:
                result["create"] = blocked or ("" if self.allowed else "检测授权已失效，请转交。")
        if s.owner is not None and "transfer" in a.permissions:
            result["transfer"] = blocked or (
                "" if self.candidates("test") else "没有符合授权的接收人。"
            )
        return result

    def report_actions(self, report, docs, reviewers):
        if self.row.owner != self.actor.id or "test" not in self.actor.permissions:
            return {}
        common = self.actions()["create"] or ("" if report.state == "draft" else "本版本已退出编制。")
        kinds = {f["kind"] for f in docs}
        return {
            "upload": common,
            "cancel": common,
            "submit": common
            or ("请上传原始记录 PDF。" if "source" not in kinds else "")
            or ("请上传待签报告 PDF。" if "draft" not in kinds else "")
            or (
                "未找到合格审核人，请资料管理员核对授权。"
                if self.row.review_mode == "designated" and not reviewers
                else ""
            ),
        }

    def report(self, report_id):
        row = self.db.execute(
            select(reports).where(reports.c.id == report_id, reports.c.sample_id == self.row.id)
        ).first()
        if row is None:
            raise Problem("未找到这份报告。", 404)
        return row
