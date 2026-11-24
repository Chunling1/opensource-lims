"""Exercise rework completion with the real endpoint, freeze and persistence."""
import hashlib
import inspect
import pytest
from flask import g
from app.extensions import db
from app.models import Report, ReportDocumentVersion, OperationAudit
from app.applications.report_lifecycle.commands import apply_return_plan
from app.platform.workflow import report_projection

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('source', ['report.review.return', 'report.approval.return'])
def test_rework_completion_returns_to_review_and_reuses_ready_version(isolated_app, scenario_factory, monkeypatch, source):
    from app.blueprints import reports
    from app import review_version
    from app.applications.report_lifecycle.records import report_records
    with isolated_app.app_context():
        identity = scenario_factory.identity_scenario(
            permission_codes=('testing.data_change.view', 'report.review.view'),
            granted_step_codes=('data_entry', 'report_review'))
        report = Report(report_no='QA-REWORK', sample_no='QA-S1', client='虚拟客户',
            project=identity.project.name, department=identity.department.name,
            owner=identity.user.name, status='待审核', sample_status='已领取', sample_reg_state='登记完成')
        db.session.add(report)
        raw = b'%PDF-isolated-existing-version'
        snapshot = {'fixture': 'unchanged'}
        version = ReportDocumentVersion(report_no=report.report_no, output_kind='official',
            version_no=1, profile_code='QA', composition={}, snapshot=snapshot,
            source_hash=review_version.snapshot_hash(snapshot), sha256=hashlib.sha256(raw).hexdigest(),
            pdf_data=raw, created_by=identity.user.account)
        db.session.add(version); db.session.flush()
        report.current_document_version_id = version.id
        monkeypatch.setattr(review_version, 'document_preflight', lambda *a: {'missing': [], 'warnings': []})
        monkeypatch.setattr(review_version, 'source_snapshot', lambda r: snapshot)
        monkeypatch.setattr('app.preview_cache.cached_pdf', lambda r: (raw, {'pdfHash': version.sha256}))
        db.session.add(OperationAudit(object_type='report', object_id=report.report_no,
            action='report.preview.confirm', category='report', success=True,
            after_data={'sourceHash': review_version.snapshot_hash(snapshot), 'pdfHash': version.sha256}))
        for _ in range(2):
            apply_return_plan(report, identity.user, source, '更正检测结果', 'data_only')
            db.session.commit()
            assert report.status == '检测更改中'
            assert report.detail['returnPlan']['afterDataChange'] == 'review'
            with isolated_app.test_request_context(json={}):
                g.current_user = identity.user
                response = inspect.unwrap(reports.change_test_complete)(report.report_no)
                result = (response[0] if isinstance(response, tuple) else response).get_json()
            assert result['code'] == 0, result
            db.session.expire_all()
            assert report.status == '待审核'
            assert report.to_row()['dataStatus'] == '报告审核中'
            assert report_projection(report.to_row(), 'review') == 'active'
            assert report_projection(report.to_row(), 'data_change') is None
            assert report.sample_status == '已领取'
            assert report.current_document_version_id == version.id
            assert ReportDocumentVersion.query.count() == 1
        assert OperationAudit.query.filter_by(action='report.test_change.complete').count() == 2
        records = report_records(report.report_no, 'testing', 1, 10)
        assert records['total'] == 4  # status and dataStatus in each of two real events
        assert {item['sequence'] for item in records['items']} == {1, 2}
        assert all(item['type'] == '完成检测更改' for item in records['items'])
        from app.applications.report_lifecycle.query_details import query_details
        assert query_details([report])[report.report_no]['dataCompletedBy'] == identity.user.name
