"""Local effective source fields, separate from immutable incoming events."""
from ..extensions import db
from ..models import JSONText


class SourceCorrection(db.Model):
    __tablename__ = "business_source_corrections"
    kind = db.Column(db.String(40), primary_key=True)
    source_key = db.Column(db.String(160), primary_key=True)
    effective_key = db.Column(db.String(160), nullable=True)
    __table_args__ = (db.UniqueConstraint("kind", "effective_key", name="uq_business_source_effective_key"),)
    fields = db.Column(JSONText, nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=1)


def effective(kind, rows, key):
    """Bounded lookup for the currently visible records."""
    from flask import has_app_context
    if not rows or not has_app_context():
        return rows
    keys = [str(row.get(key) or "") for row in rows]
    changes = {r.source_key: r.fields for r in SourceCorrection.query.filter(
        SourceCorrection.kind == kind, SourceCorrection.source_key.in_(keys)).all()}
    result = []
    for row in rows:
        source_key = str(row.get(key) or "")
        item = dict(row, **changes.get(source_key, {}))
        if item.get(key) != row.get(key):
            item["_sourceKey"] = source_key
        result.append(item)
    return result


def customer_search_fields():
    # Send only changed searchable fields to the local receiver, not full records.
    from flask import has_app_context
    if not has_app_context():
        return {}
    return {r.source_key: {k: v for k, v in r.fields.items() if k in ("name", "enabled", "code")}
            for r in SourceCorrection.query.filter_by(kind="customers").all()
            if any(k in r.fields for k in ("name", "enabled", "code"))}
