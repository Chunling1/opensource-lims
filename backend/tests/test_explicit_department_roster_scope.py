"""Explicit data grants augment roster visibility without granting workflow rights."""
import pytest
from app.extensions import db
from app.models import Report, Entrust, user_data_departments
from app.security import issue_token
from app.authorization_scope import user_has_project_step
from app.applications.report_lifecycle import scoped_report_query, get_visible_report
from app.platform.identity.department_project_scope import report_is_visible
from app.blueprints.entrust import _scope as entrust_scope

pytest_plugins = ("testkit.fixtures",)


@pytest.fixture()
def scope_case(isolated_client, scenario_factory):
    f = scenario_factory
    home = f.department(name="虚拟办公室")
    lab = f.department(name="虚拟检测部")
    child = f.department(name="虚拟下属部", parent=lab)
    foreign = f.department(name="虚拟跨部")
    member_only = f.department(name="虚拟成员部")
    projects, steps, reports = {}, {}, {}
    for dept in (home, lab, child, foreign, member_only):
        project, ps = f.project(dept)
        projects[dept.name], steps[dept.name] = project, {s.step_code: s for s in ps}
        row = Report(report_no=f"QA-{dept.id}", sample_no=f"S-{dept.id}",
            department=dept.name, project=project.name, owner="虚拟他人", client="虚拟客户",
            status="待样品领取", sample_status="已入库", detail={})
        db.session.add(row)
        reports[dept.name] = row
        db.session.add(Entrust(entrust_no=f"WT-{dept.id}", department=dept.name, owner="虚拟他人"))
    user = f.user(home, data_scope_type="department_project", permissions=[
        "entrust.query.view", "entrust.sample_register.view", "sample.flow_query.view",
        "sample.inbound.view", "sample.outbound.view", "report.review.view",
    ])
    f.grant_data_department(user, lab, include_children=True)
    f.grant_data_department(user, member_only, see_data=False, see_members=True)
    db.session.commit()
    return isolated_client, f, user, (home, lab, child, foreign, member_only), projects, steps, reports


def visible(user):
    return {r.department for r in scoped_report_query(Report.query, user).all()}


def test_roster_unions_home_explicit_children_and_appointed_projects(scope_case):
    _, _, user, (home, lab, child, foreign, member_only), _, steps, reports = scope_case
    assert visible(user) == {home.name, lab.name, child.name}
    assert report_is_visible(user, reports[lab.name])
    assert get_visible_report(user, reports[lab.name].report_no) is not None
    assert get_visible_report(user, reports[member_only.name].report_no) is None
    assert {e.department for e in entrust_scope(Entrust.query, user)} == {home.name, lab.name, child.name}
    user.project_steps.append(steps[foreign.name]["report_review"])
    db.session.commit()
    assert visible(user) == {home.name, lab.name, child.name, foreign.name}
    assert report_is_visible(user, reports[foreign.name])
    assert scoped_report_query(Report.query.filter_by(department=lab.name), user).count() == 1
    user.project_steps.clear()
    db.session.commit()
    assert foreign.name not in visible(user)


def test_grants_revoke_immediately_and_member_only_does_not_grant_data(scope_case):
    _, _, user, (home, lab, child, _, member_only), _, _, reports = scope_case
    db.session.execute(user_data_departments.update().where(
        user_data_departments.c.user_id == user.id,
        user_data_departments.c.department_id == lab.id).values(include_children=False))
    db.session.commit()
    assert visible(user) == {home.name, lab.name}
    db.session.execute(user_data_departments.update().where(
        user_data_departments.c.user_id == user.id).values(see_data=False))
    db.session.commit()
    assert visible(user) == {home.name}
    assert not report_is_visible(user, reports[member_only.name])
    user.enabled = False
    assert visible(user) == set()
    assert not report_is_visible(user, reports[home.name])


def test_data_grants_do_not_derive_cross_department_workflow_rights(scope_case):
    _, _, user, (home, lab, *_), projects, _, _ = scope_case
    assert user_has_project_step(user, projects[home.name], "sample_inbound")
    for step in ("sample_inbound", "sample_outbound", "entrust_review", "data_entry", "report_review", "report_approval"):
        assert not user_has_project_step(user, projects[lab.name], step), step
    assert lab.name in visible(user)


@pytest.mark.parametrize("mode", ["self", "authorization", "department", "all"])
def test_other_explicit_scope_modes_keep_their_limits(scope_case, mode):
    _, _, user, (_, lab, child, _, _), _, _, _ = scope_case
    user.data_scope_type = mode
    db.session.commit()
    expected = {lab.name, child.name} if mode == "department" else set()
    if mode == "all":
        expected = {r.department for r in Report.query.all()}
    assert visible(user) == expected


def test_read_query_lists_granted_samples_but_outbound_tasks_remain_restricted(scope_case):
    client, _, user, (home, lab, child, *_), _, _, _ = scope_case
    headers = {"Authorization": "Bearer " + issue_token(user)}
    body = client.post("/api/samples/query", headers=headers,
        json={"view": "flow_query", "page": 1, "pageSize": 2}).get_json()
    assert body["code"] == 0, body
    assert body["data"]["total"] == 3
    page2 = client.post("/api/samples/query", headers=headers,
        json={"view": "flow_query", "page": 2, "pageSize": 2}).get_json()
    rows = body["data"]["rows"] + page2["data"]["rows"]
    assert {r["department"] for r in rows} == {home.name, lab.name, child.name}
    tasks = client.post("/api/samples/query", headers=headers,
        json={"view": "outbound"}).get_json()
    assert tasks["code"] == 0, tasks
    assert {r["department"] for r in tasks["data"]["rows"]} == {home.name}


def test_all_departments_plus_archive_only_still_sees_samples(scope_case):
    _, f, user, (home, lab, child, foreign, member_only), _, steps, _ = scope_case
    for dept in (home, child, foreign):
        f.grant_data_department(user, dept)
    db.session.execute(user_data_departments.update().where(
        user_data_departments.c.user_id == user.id,
        user_data_departments.c.department_id == member_only.id).values(see_data=True))
    user.project_steps.append(steps[foreign.name]["report_archive"])
    db.session.commit()
    assert len(visible(user)) == 5


def test_search_candidates_include_granted_samples_and_respect_revocation(scope_case):
    from app.functions import ai_index

    _, _, user, (home, lab, child, _, member_only), _, _, reports = scope_case
    for report in reports.values():
        ai_index.upsert("sample", report)
    db.session.commit()
    rows = ai_index.search(user, "虚拟客户")
    assert {r["entityId"] for r in rows} == {
        reports[d.name].sample_no for d in (home, lab, child)
    }
    target = reports[lab.name].sample_no
    assert [r["entityId"] for r in ai_index.search(user, target)] == [target]
    assert not ai_index.search(user, reports[member_only.name].sample_no)
    db.session.execute(user_data_departments.update().where(
        user_data_departments.c.user_id == user.id).values(see_data=False))
    db.session.commit()
    assert not ai_index.search(user, target)
