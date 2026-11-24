"""Explicit, audited consolidation of one unsigned legacy internal GZ.

Run in the configured service environment after the release backup. Default is
transaction rollback. --apply requires the SHA256 returned by a prior dry run;
any intervening business change requires another review. No provider calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.extensions import db
from app.models import Report, ReportCorrectionRequest, ReportAttachment, ReportDocumentContent, ReportEsignFlow, User
from app.organization_privileges import has_full_platform_authority
from app.internal_report_corrections import consolidate_legacy_internal


def columns(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def run(args):
    with create_app().app_context():
        try:
            request = ReportCorrectionRequest.query.filter_by(id=args.request_id).with_for_update().one()
            reports = Report.query.filter(Report.id.in_([args.main_id, args.derivative_id])).order_by(Report.id).with_for_update().all()
            if len(reports) != 2:
                raise ValueError('需要两个已核实的报告 ID')
            actor = User.query.filter_by(account=args.actor, enabled=True).one()
            if not has_full_platform_authority(actor):
                raise ValueError('维护操作须归属现有管理员账号')
            numbers = [r.report_no for r in reports]
            state = {'request': columns(request), 'reports': [columns(r) for r in reports],
                'content': [columns(r) for r in ReportDocumentContent.query.filter(ReportDocumentContent.report_no.in_(numbers)).order_by(ReportDocumentContent.id).all()],
                'attachments': [columns(r) for r in ReportAttachment.query.filter(ReportAttachment.report_no.in_(numbers)).order_by(ReportAttachment.id).all()],
                'flows': [columns(r) for r in ReportEsignFlow.query.filter(ReportEsignFlow.report_id.in_([args.main_id, args.derivative_id])).order_by(ReportEsignFlow.id).all()]}
            digest = hashlib.sha256(json.dumps(state, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
            if args.apply and digest != args.expected_sha256:
                raise ValueError('状态摘要与预演不一致，未执行归并')
            main = consolidate_legacy_internal(args.request_id, actor,
                main_id=args.main_id, derivative_id=args.derivative_id)
            db.session.flush()
            result = {'applied': bool(args.apply), 'beforeSha256': digest, 'reportNo': main.report_no,
                      'status': main.status, 'archivedReportId': args.derivative_id, 'requestId': args.request_id}
            if args.apply:
                db.session.commit()
            else:
                db.session.rollback()
            print(json.dumps(result, ensure_ascii=False))
        except Exception:
            db.session.rollback()
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-id', type=int, required=True)
    parser.add_argument('--main-id', type=int, required=True)
    parser.add_argument('--derivative-id', type=int, required=True)
    parser.add_argument('--actor', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-sha256', default='')
    args = parser.parse_args()
    if args.apply and len(args.expected_sha256) != 64:
        parser.error('--apply requires --expected-sha256 from a reviewed dry run')
    run(args)
