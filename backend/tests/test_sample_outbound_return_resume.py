"""An already stocked sample resumes pickup after its entrust is corrected."""
import inspect

from flask import g
import pytest

from app.audit import add_operation_audit
from app.extensions import db
from app.applications.report_lifecycle import (
    apply_return_plan, apply_sample_outbound_return_transition, resumes_sample_outbound,
)
from app.platform.workflow.visibility import sample_matches_view
from test_compliance_review_round import case, payload

pytest_plugins = ("testkit.fixtures",)


@pytest.fixture()
def workflow(case, monkeypatch):
    app, user, report = case
    from app.blueprints import reports
    from app import workflow_hooks as hooks
    # Keep real state handlers, authorization, compliance rounds and persistence.
    # Exclude unrelated finance side effects and sample field validators.
    monkeypatch.setattr(hooks, "blocker", lambda *a: None)
    monkeypatch.setattr(hooks, "capture", lambda *a: None)
    monkeypatch.setattr(reports, "_sample_configuration", lambda *a, **k: {"ready": True})
    for name in ("sample_party_error", "sample_pricing_error", "sample_price_error"):
        monkeypatch.setattr(reports, name, lambda *a, **k: None)
    monkeypatch.setattr(reports, "_validate_sample_detail_dates", lambda u, d, e, **k: (d, None))
    monkeypatch.setattr(reports, "_apply_report_prefix_change", lambda *a: None)

    def invoke(handler, body):
        with app.test_request_context(json=body):
            g.current_user = user
            response = inspect.unwrap(handler)(report.report_no)
            result = (response[0] if isinstance(response, tuple) else response).get_json()
            assert result["code"] == 0, result
            return result

    def resubmit():
        invoke(reports.change_resubmit, {"editVersion": report.edit_version})
        assert report.status == "待合同评审"

    def review():
        invoke(reports.contract_review, {
            **payload(report, "contract_review"), "action": "pass", "cma": True, "cnas": True,
            "items": {key: True for key, _ in reports.CR_ITEMS},
        })

    return user, report, resubmit, review


@pytest.mark.parametrize("source_status,sample_status", [
    ("待样品领取", "已入库"), ("检测录入中", "已领取"),
])
@pytest.mark.parametrize("legacy", [False, True])
def test_outbound_return_resumes_pickup_without_repeating_stock(workflow, source_status, sample_status, legacy):
    user, report, resubmit, review = workflow
    inbound_dates = {"sampleInboundAt": "2026-10-20T09:00:00"}
    report.detail = {**report.detail, "workflowDates": inbound_dates}
    # Two complete return/review rounds must remain independently confirmable.
    for _ in range(2):
        report.status, report.sample_status = source_status, sample_status
        report.sample_pickup = {"signed": True, "account": user.account}
        apply_sample_outbound_return_transition(report, note="修改样品信息", actor_account=user.account,
            actor_name=user.name, occurred_on="2026-10-22")
        if legacy:
            plan = {**report.detail["returnPlan"], "afterContractReview": "sample_inbound"}
            plan.pop("preservedSampleStatus", None)
            report.detail = {**report.detail, "returnPlan": plan}
        add_operation_audit("sample.out_warehouse.return", "report", report.report_no, actor=user)
        db.session.commit()
        assert report.status == "委托更改中"
        assert report.sample_pickup["signed"] is False
        resubmit()
        assert report.sample_status == "已入库"
        review()
        assert (report.status, report.sample_status) == ("待样品领取", "已入库")
        assert sample_matches_view(report, report.to_row(), "outbound")
        assert report.detail["workflowDates"] == inbound_dates
        assert report.sample_pickup["signed"] is False


@pytest.mark.parametrize("legacy", [False, True])
def test_review_rejection_preserves_outbound_destination(workflow, legacy):
    user, report, resubmit, review = workflow
    report.detail = {**report.detail, "returnPlan": {
        "sourceAction": "sample.out_warehouse.return",
        "afterContractReview": "sample_inbound" if legacy else "sample_outbound",
    }}
    report.status, report.sample_status = "待合同评审", "已入库"
    for _ in range(2):
        apply_return_plan(report, user, "report.contract_review.return", "再次修改")
        db.session.commit()
        assert report.detail["returnPlan"]["afterContractReview"] == "sample_outbound"
        resubmit()
    review()
    assert (report.status, report.sample_status) == ("待样品领取", "已入库")


def test_first_review_and_ordinary_review_return_still_require_stock(workflow):
    user, report, resubmit, review = workflow
    review()
    assert (report.status, report.sample_status) == ("待样品入库", "待入库")
    apply_return_plan(report, user, "report.contract_review.return", "普通退回")
    db.session.commit()
    resubmit()
    review()
    assert (report.status, report.sample_status) == ("待样品入库", "待入库")


@pytest.mark.parametrize("plan", [{}, {"afterContractReview": "sample_inbound"},
    {"sourceAction": "testing.data_entry.return", "afterContractReview": "data_entry"},
    {"sourceAction": "report.review.return", "afterContractReview": "review"}])
def test_unrelated_destinations_are_not_treated_as_outbound(plan):
    assert not resumes_sample_outbound({"returnPlan": plan})
