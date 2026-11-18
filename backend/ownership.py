from sqlalchemy import func, update
from .policy import Problem
from .schema import samples, tasks


def change_owner(db, policy, action, data, audit):
    sample_id = policy.row.id
    actor = policy.actor
    reason = data.get("reason", "").strip()
    owner = actor.id if action == "claim" else None
    if action == "transfer":
        owner = data["targetId"]
        if owner not in {c["id"] for c in policy.candidates("test")}:
            raise Problem("接收人不具备覆盖全部项目的有效授权。")
    db.execute(update(samples).where(samples.c.id == sample_id).values(owner=owner))
    db.execute(
        update(tasks)
        .where(tasks.c.sample_id == sample_id, tasks.c.report_id.is_(None), ~tasks.c.closed)
        .values(closed=True)
    )
    db.execute(
        update(tasks)
        .where(tasks.c.sample_id == sample_id, tasks.c.kind == "author", ~tasks.c.closed)
        .values(assigned=owner, arrived=func.now())
    )
    if owner is None:
        db.execute(tasks.insert().values(sample_id=sample_id, kind="claim", closed=False))
    audit.update(owner=owner, reason=reason)
