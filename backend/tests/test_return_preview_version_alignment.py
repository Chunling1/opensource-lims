"""Regression tests ensuring returned/edited reports never serve stale preview or version pointers."""
import hashlib
import pytest

from app import create_app
from app.applications.report_lifecycle.commands import apply_return_plan
from app.extensions import db
from app.models import Department, Entrust, Report, ReportDocumentVersion, User
from app.preview_cache import _locked, status as preview_status
from app.report_preview_revision import revision_key


@pytest.fixture
def app_ctx(tmp_path):
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "test.db"}',
        'STORAGE_ROOT': str(tmp_path / 'storage'),
        'AUTO_BOOTSTRAP': False,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.engine.dispose()


def test_apply_return_plan_clears_stale_document_version_pointers(app_ctx):
    dept = Department(code='D_RET', name='退回测试部')
    db.session.add(dept)
    db.session.flush()
    user = User(
        account='reviewer_ret',
        name='审核员',
        password_hash='x',
        department_id=dept.id,
        role_key='admin',
        role_name='审核员',
        home_path='/dashboard',
    )
    db.session.add(user)
    report = Report(
        report_no='LAB-2026RET-0001',
        sample_no='2026RET-0001',
        entrust_no='WT-2026-RET1',
        client='原委托单位',
        project='测试项目',
        department=dept.name,
        status='待审核',
        sample_status='已领取',
        detail={'rawSample': {'sampleName': '原样品'}},
    )
    db.session.add(report)
    db.session.flush()
    old_ver = ReportDocumentVersion(
        report_no=report.report_no,
        output_kind='official',
        version_no=1,
        profile_code='fallback',
        source_hash='old-source-hash-v1',
        sha256=hashlib.sha256(b'%PDF-1.4 old').hexdigest(),
        pdf_data=b'%PDF-1.4 old',
        created_by=user.account,
    )
    db.session.add(old_ver)
    db.session.flush()
    report.current_document_version_id = old_ver.id
    report.approved_document_version_id = old_ver.id
    db.session.commit()

    apply_return_plan(report, user, 'report.review.return', '修改委托单位', 'entrust_only')
    db.session.commit()

    assert report.status == '委托更改中'
    assert report.current_document_version_id is None
    assert report.approved_document_version_id is None
    assert db.session.get(ReportDocumentVersion, old_ver.id) is not None


def test_entrust_only_review_without_frozen_version_uses_live_preview_not_stale_official(app_ctx):
    dept = Department(code='D_LIVE', name='预览测试部')
    db.session.add(dept)
    db.session.flush()
    entrust = Entrust(
        entrust_no='WT-2026-RET2',
        client='旧委托单位',
        project_name='旧工程名',
        department=dept.name,
        status='委托完成',
    )
    report = Report(
        report_no='LAB-2026RET-0002',
        sample_no='2026RET-0002',
        entrust_no=entrust.entrust_no,
        client='旧委托单位',
        project='测试项目',
        department=dept.name,
        status='待审核',
        sample_status='已领取',
        current_document_version_id=None,
        approved_document_version_id=None,
        detail={'rawSample': {'sampleName': '修改后样品'}},
    )
    db.session.add_all([entrust, report])
    db.session.commit()

    assert _locked(report) is False
    st = preview_status(report)
    assert st['status'] == 'missing'
    assert not str(st.get('sourceHash') or '').startswith('official-')

    key_before = revision_key(report, 'eng-test')
    entrust.client = '新委托单位'
    db.session.commit()
    key_after = revision_key(report, 'eng-test')
    assert key_before != key_after
