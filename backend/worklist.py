from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import and_, case, exists, func, literal, or_, select, union_all
from .policy import Problem, covers, pool_scope, visible_samples
from .schema import events, reports, samples, tasks, templates

KINDS = ("claim", "author", "returned", "review1")


def worklist(db, actor, params, page, size):
    sample_id = samples.c.id
    authorized = and_(
        "test" in actor.permissions,
        samples.c.owner == actor.id,
        ~samples.c.frozen,
        covers(actor.id, sample_id, "test"),
    )
    participated = (
        exists()
        .where(
            events.c.actor == actor.id,
            events.c.report_id == reports.c.id,
            events.c.action.in_(("create", "upload", "submit")),
        )
        .correlate_except(events)
    )
    eligible_review = and_(
        "review" in actor.permissions,
        visible_samples(actor),
        or_(tasks.c.assigned == actor.id, tasks.c.assigned.is_(None)),
        ~samples.c.frozen,
        samples.c.owner != actor.id,
        covers(actor.id, sample_id, "review"),
        ~participated,
    )
    source = case(
        (tasks.c.kind == "claim", "检测领取池"),
        (tasks.c.kind == "review1", "报告提交"),
        else_="报告编制",
    )
    records = (
        select(
            tasks.c.kind,
            sample_id.label("sampleId"),
            tasks.c.report_id.label("reportId"),
            func.coalesce(reports.c.number, samples.c.number).label("number"),
            samples.c.name,
            source.label("source"),
            tasks.c.arrived,
        )
        .select_from(
            tasks.join(samples).join(templates).outerjoin(reports, reports.c.id == tasks.c.report_id)
        )
        .where(
            ~tasks.c.closed,
            or_(
                and_(tasks.c.kind == "claim", pool_scope(actor)),
                and_(
                    tasks.c.kind.in_(("author", "returned")),
                    authorized,
                    tasks.c.assigned == actor.id,
                    reports.c.state == "draft",
                ),
                and_(tasks.c.kind == "review1", eligible_review, reports.c.state == "review"),
            ),
        )
    )
    received = (
        select(func.max(events.c.at))
        .where(events.c.sample_id == sample_id, events.c.action.in_(("claim", "transfer", "cancel")))
        .correlate(samples)
        .scalar_subquery()
    )
    # A claimed sample needs a first report. Its report task takes over once created.
    initial = select(
        literal("author"),
        sample_id,
        literal(None, type_=reports.c.id.type),
        samples.c.number,
        samples.c.name,
        literal("检测领取"),
        received,
    ).where(
        authorized, ~exists().where(reports.c.sample_id == sample_id, reports.c.state != "cancelled")
    )
    rows = union_all(records, initial).subquery()
    counts = dict.fromkeys(
        [
            *(["claim"] if "claim" in actor.permissions else []),
            *(["author", "returned"] if "test" in actor.permissions else []),
            *(["review1"] if "review" in actor.permissions else []),
        ],
        0,
    )
    counts.update(dict(db.execute(select(rows.c.kind, func.count()).group_by(rows.c.kind)).all()))
    kind = params.get("kind")
    query = select(rows)
    if kind:
        if kind not in KINDS:
            raise Problem("待办类型无效。", 400)
        query = query.where(rows.c.kind == kind)
    for key in ("start", "end"):
        if params.get(key):
            try:
                day = date.fromisoformat(params[key])
            except ValueError:
                raise Problem("日期格式无效。", 400) from None
            # Filter by the installation's local calendar date. Stored instants use UTC.
            bound = datetime.combine(day + timedelta(days=(key == "end")), time.min).astimezone(
                timezone.utc
            )
            query = query.where(rows.c.arrived >= bound if key == "start" else rows.c.arrived < bound)
    if params.get("start") and params.get("end") and params["start"] > params["end"]:
        raise Problem("起始日期不能晚于结束日期。", 400)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    data = db.execute(
        query.order_by(
            rows.c.arrived.desc().nulls_last(), rows.c.sampleId, rows.c.reportId, rows.c.kind
        )
        .offset((page - 1) * size)
        .limit(size)
    ).mappings()
    return {
        "counts": counts,
        "total": total,
        "page": page,
        "pageSize": size,
        "rows": [
            {
                **r,
                "arrived": (
                    r["arrived"].replace(tzinfo=timezone.utc)
                    if r["arrived"] and r["arrived"].tzinfo is None
                    else r["arrived"]
                ),
            }
            for r in data
        ],
    }
