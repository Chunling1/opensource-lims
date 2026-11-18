import hashlib
import json
from datetime import date, datetime, timezone
from .ownership import change_owner
from .documents import append_pdf
from .reporting import create_report, submit_report, cancel_draft
from sqlalchemy import select, update
from .policy import Problem, SamplePolicy, current_documents, notify_catalog
from .schema import events, grants, items, reports, samples


def perform(db, actor, sample_id, action, data, upload, store, created_paths, max_bytes):
    key, version = data["requestId"], data["version"]
    content = upload.stream.read(max_bytes + 1) if upload is not None else b""
    digest = hashlib.sha256(content).hexdigest()
    signature = hashlib.sha256(
        json.dumps(
            [sample_id, action, data, upload.filename if upload else "", digest],
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()
    # Serialize the sample aggregate before replay lookup and authorization.
    db.execute(select(samples.c.id).where(samples.c.id == sample_id).with_for_update()).first()
    policy = SamplePolicy(db, actor, sample_id)
    previous = db.execute(
        select(events).where(events.c.actor == actor.id, events.c.request_id == key)
    ).first()
    if previous:
        if previous.fingerprint != signature:
            raise Problem("同一请求编号已用于其他内容。", 409)
        return previous.payload["result"]
    s = policy.row
    if action == "claim" and s.owner is not None:
        raise Problem("样品已被领取，请刷新列表。", 409)
    report_id = data.get("reportId")
    is_report_action = report_id is not None
    if not is_report_action and version != s.version:
        raise Problem("样品已由其他操作更新，请刷新后再办理。", 409)
    decisions = policy.actions()
    if action in {"upload", "cancel", "submit"}:
        report = policy.report(report_id)
        if report.version != version:
            raise Problem("本报告已被更新，请刷新后再办理。", 409)
        docs = current_documents(db, report_id)
        reviewers = policy.candidates("review", report_id)
        decisions = policy.report_actions(report, docs, reviewers)
    if action not in decisions:
        raise Problem("当前身份不能办理此动作。", 403)
    if (
        action == "submit"
        and s.owner == actor.id
        and report.state == "draft"
        and s.review_mode == "designated"
        and not reviewers
    ):
        notify_catalog(db, report_id)
        return {"error": "未找到合格审核人，已提醒资料管理员。"}
    if decisions[action]:
        raise Problem(decisions[action])
    now = datetime.now(timezone.utc)
    audit = {"previousOwner": s.owner, "versionBefore": version}
    if action in {"claim", "return", "transfer"}:
        change_owner(db, policy, action, data, audit)
    if action == "create":
        report_id = create_report(db, sample_id, actor.id, data)
    if action == "upload":
        append_pdf(
            db,
            actor,
            report_id,
            data,
            upload,
            content,
            digest,
            store,
            created_paths,
            max_bytes,
            docs,
            now,
            audit,
        )
        if s.review_mode == "designated" and not reviewers:
            notify_catalog(db, report_id)
    if action == "submit":
        submit_report(db, s, report_id, docs, reviewers, data, audit)
    if action == "cancel":
        cancel_draft(db, report_id, data["reason"].strip(), audit)
    record = reports if is_report_action else samples
    db.execute(
        update(record)
        .where(record.c.id == (report_id if is_report_action else sample_id))
        .values(version=version + 1)
    )
    result = {"sampleId": sample_id, "reportId": report_id, "version": version + 1}
    grant_user = audit.get("owner") if action in {"claim", "transfer"} else actor.id
    audit["testGrants"] = list(
        db.scalars(
            select(grants.c.id).where(
                grants.c.user_id == grant_user,
                grants.c.duty == "test",
                grants.c.scope.in_(select(items.c.scope).where(items.c.sample_id == sample_id)),
                grants.c.start <= date.today(),
                grants.c.end >= date.today(),
            )
        )
    )
    db.execute(
        events.insert().values(
            sample_id=sample_id,
            report_id=report_id,
            actor=actor.id,
            action=action,
            at=now,
            request_id=key,
            fingerprint=signature,
            payload={**audit, "result": result},
        )
    )
    return result
