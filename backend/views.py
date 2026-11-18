from datetime import date
from sqlalchemy import exists, func, select

from .policy import SamplePolicy, current_documents, notify_catalog, pool_scope, visible_samples
from .schema import items, reports, samples, sequences, templates, users


def sample_list(db, actor, view, filters, page, size):
    condition = pool_scope(actor) if view == "pool" else samples.c.owner == actor.id
    query = (
        select(samples.c.id, samples.c.number, samples.c.name, samples.c.commission, samples.c.frozen)
        .join(templates)
        .where(condition)
    )
    if filters.get("commission"):
        query = query.where(samples.c.commission.contains(filters["commission"], autoescape=True))
    if filters.get("project"):
        query = query.where(
            exists().where(
                items.c.sample_id == samples.c.id,
                items.c.scope.contains(filters["project"], autoescape=True),
            )
        )
    state = filters.get("state")
    if state:
        query = query.where(
            samples.c.frozen if state == "frozen" else ~samples.c.frozen,
            samples.c.owner.is_(None) if state == "pool" else samples.c.owner.is_not(None),
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    return {
        "total": total,
        "page": page,
        "pageSize": size,
        "rows": [
            dict(row._mapping)
            for row in db.execute(query.order_by(samples.c.id).offset((page - 1) * size).limit(size))
        ],
    }


def report_list(db, actor, filters, page, size):
    query = select(
        reports.c.id, reports.c.number, reports.c.state, samples.c.id.label("sampleId"),
        samples.c.name.label("sampleName"), samples.c.number.label("sampleNumber"),
        samples.c.commission, users.c.name.label("owner"),
    ).select_from(reports.join(samples).outerjoin(users, users.c.id == samples.c.owner)).where(visible_samples(actor))
    if filters.get("number"):
        query = query.where(reports.c.number.contains(filters["number"], autoescape=True))
    if filters.get("sample"):
        word = filters["sample"]
        query = query.where(samples.c.name.contains(word, autoescape=True) | samples.c.number.contains(word, autoescape=True))
    if filters.get("state"):
        query = query.where(reports.c.state == filters["state"])
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(reports.c.id.desc()).offset((page-1)*size).limit(size)).mappings()
    return {"total": total, "page": page, "pageSize": size, "rows": [dict(row) for row in rows]}


def detail(db, actor, sid):
    p = SamplePolicy(db, actor, sid)
    s = p.row
    actions = p.actions()
    rows = []
    for report in db.execute(select(reports).where(reports.c.sample_id == sid).order_by(reports.c.id)):
        docs = current_documents(db, report.id)
        reviewers = p.candidates("review", report.id)
        if (
            s.owner == actor.id
            and report.state == "draft"
            and s.review_mode == "designated"
            and not reviewers
        ):
            notify_catalog(db, report.id)
        rows.append(
            {
                "id": report.id,
                "number": report.number,
                "version": report.version,
                "state": report.state,
                "start": report.start,
                "end": report.end,
                "reviewerId": report.reviewer,
                "reviewers": reviewers,
                "actions": p.report_actions(report, docs, reviewers),
                "files": [
                    {
                        key: f[key]
                        for key in ("id", "name", "kind", "size", "created", "uploader", "sha256")
                    }
                    for f in docs
                ],
            }
        )
    return {
        "id": sid,
        "today": date.today(),
        "number": s.number,
        "name": s.name,
        "commission": s.commission,
        "template": s.label,
        "owner": db.scalar(select(users.c.name).where(users.c.id == s.owner)),
        "version": s.version,
        "frozen": s.frozen,
        "designated": s.review_mode == "designated",
        "physical": s.physical,
        "receivedDate": s.received_date,
        "siteDate": s.site_date,
        "commissionDate": s.commission_date,
        "projects": list(
            db.scalars(select(items.c.scope).where(items.c.sample_id == sid).order_by(items.c.scope))
        ),
        "actions": actions,
        "targets": p.candidates("test") if "transfer" in actions else [],
        "rules": [dict(row._mapping) for row in db.execute(select(sequences.c.id, sequences.c.prefix))],
        "reports": rows,
    }
