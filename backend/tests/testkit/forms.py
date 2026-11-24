"""Explicit form-load snapshot for non-concurrency integration scenarios.

Never patches the client or endpoint. Stale/missing-version tests use raw bodies.
"""
from contextlib import nullcontext
from flask import has_app_context
from app.models import Report, Entrust, Agreement
from app.extensions import db


def loaded_form(client, path, body):
    from urllib.parse import unquote, urlsplit
    segments = unquote(urlsplit(path).path).strip('/').split('/')
    if not isinstance(body, dict) or 'editVersion' in body:
        return body
    with nullcontext() if has_app_context() else client.application.app_context():
        row = None
        if len(segments) == 4 and segments[1] == 'reports' and segments[3] in ('edit', 'change-save', 'change-resubmit', 'testinfo'):
            row = Report.query.filter_by(report_no=segments[2]).first()
        elif len(segments) == 3 and segments[1] in ('entrust', 'agreements') and segments[2].isdigit():
            row = db.session.get(Entrust if segments[1] == 'entrust' else Agreement, int(segments[2]))
        if row and segments[-1] == 'testinfo':
            from app.edit_concurrency import test_form_version
            return {**body, 'testEditVersion': test_form_version(row)}
        return {**body, 'editVersion': row.edit_version} if row else body
