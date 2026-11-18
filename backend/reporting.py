from datetime import date
from sqlalchemy import update
from .policy import Problem
from .schema import reports, samples, sequences, tasks


def create_report(db, sample_id, owner, data):
    number = db.execute(
        update(sequences)
        .where(sequences.c.id == data["ruleId"])
        .values(last=sequences.c.last + 1)
        .returning(sequences.c.prefix, sequences.c.last)
    ).first()
    if number is None:
        raise Problem("所选报告编号规则不可用。")
    report_id = db.scalar(
        reports.insert()
        .values(sample_id=sample_id, number=f"{number.prefix}-{number.last:05d}", state="draft")
        .returning(reports.c.id)
    )

    db.execute(
        tasks.insert().values(
            sample_id=sample_id, report_id=report_id, kind="author", assigned=owner, closed=False
        )
    )
    return report_id


def submit_report(db, s, report_id, docs, reviewers, data, audit):
    sample_id = s.id
    start, end = data["start"], data["end"]
    if start > end or end > date.today() or (s.received_date and start < s.received_date):
        raise Problem("请核对检测日期：开始不晚于结束，结束不晚于今天；有收样日期时开始不能早于收样。")
    if not s.physical:
        site = data.get("siteDate", s.site_date)
        if not site or not s.commission_date <= site <= date.today():
            raise Problem("现场检测日期须在委托日期与今天之间。")
        if site != s.site_date:
            db.execute(update(samples).where(samples.c.id == sample_id).values(site_date=site))
        audit["siteDate"] = site.isoformat()
    reviewer = data.get("reviewerId") if s.review_mode == "designated" else None
    if s.review_mode == "designated" and reviewer not in {u["id"] for u in reviewers}:
        raise Problem("请选择具备授权且符合回避要求的审核人。")
    snapshot = [{"id": f["id"], "sha256": f["sha256"], "kind": f["kind"]} for f in docs]
    db.execute(
        update(reports)
        .where(reports.c.id == report_id)
        .values(state="review", reviewer=reviewer, start=start, end=end, snapshot=snapshot)
    )
    db.execute(update(tasks).where(tasks.c.report_id == report_id, ~tasks.c.closed).values(closed=True))
    db.execute(
        tasks.insert().values(
            sample_id=sample_id, report_id=report_id, kind="review1", assigned=reviewer, closed=False
        )
    )
    audit.update(
        templateId=s.template_id,
        reviewer=reviewer,
        files=snapshot,
        start=start.isoformat(),
        end=end.isoformat(),
    )


def cancel_draft(db, report_id, reason, audit):
    db.execute(update(reports).where(reports.c.id == report_id).values(state="cancelled"))
    db.execute(update(tasks).where(tasks.c.report_id == report_id, ~tasks.c.closed).values(closed=True))
    audit.update(reason=reason)
