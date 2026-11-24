from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from app.models import Department, Personnel, User
from config import Config


class TestConfig(Config):
    TESTING = True
    PROD = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET = "personnel-management-test-secret-with-32-bytes"
    JWT_SECRET_IS_DEFAULT = False
    ADMIN_PASSWORD = "TestAdmin!2026"


@pytest.fixture()
def app(tmp_path):
    class IsolatedTestConfig(TestConfig):
        STORAGE_ROOT = str(tmp_path / "personnel-management-files")

    application = create_app(IsolatedTestConfig)
    with application.app_context():
        db.create_all()
        from app.seed import seed_all
        from app.security import hash_password
        seed_all()
        admin = User.query.filter_by(account="admin").first()
        admin.password_hash = hash_password("123456")
        admin.must_change_password = False
        if not Department.query.filter_by(name="建筑热工检测部").first():
            db.session.add(Department(code="THERMAL_BLDG", name="建筑热工检测部"))
        db.session.commit()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


def _admin_headers(client):
    response = client.post(
        "/api/auth/login",
        json={"account": "admin", "password": "123456"},
    ).get_json()
    assert response["code"] == 0
    return {"Authorization": f"Bearer {response['data']['token']}"}


def test_create_personnel_builds_one_login_identity_and_roster_record(client, app):
    with app.app_context():
        department = Department.query.filter_by(name="建筑热工检测部").one()
        department_id = department.id

    response = client.post(
        "/api/admin/users",
        headers=_admin_headers(client),
        json={
            "account": "qa_new_person",
            "name": "演示新人员",
            "password": "qa_new_person123",
            "departmentId": department_id,
            "roleName": "检测员",
            "personnel": {
                "position": "检测岗位",
                "title": "助理工程师",
                "education": "本科",
                "mobile": "13800000009",
            },
        },
    ).get_json()

    assert response["code"] == 0
    temp_password = response["data"]["tempPassword"]
    assert temp_password and temp_password.startswith("qa_new_person")
    user_id = response["data"]["user"]["id"]
    personnel_id = response["data"]["personnelId"]

    with app.app_context():
        user = db.session.get(User, user_id)
        person = db.session.get(Personnel, personnel_id)
        assert user.account == "qa_new_person"
        assert user.must_change_password is True
        assert user.department_id == department_id
        assert person.code == user.account
        assert person.name == user.name
        assert person.dept == "建筑热工检测部"
        assert person.position == "检测岗位"
        assert person.title == "助理工程师"
        assert person.mobile == "13800000009"
        assert Personnel.query.filter_by(code="qa_new_person", deleted_at=None).count() == 1

    detail = client.get(
        f"/api/quality/personnel/{personnel_id}",
        headers=_admin_headers(client),
    ).get_json()
    assert detail["code"] == 0
    assert detail["data"]["mobile"] == "13800000009"
    assert "idNo" not in detail["data"]

    first_login = client.post(
        "/api/auth/login",
        json={"account": "qa_new_person", "password": temp_password},
    ).get_json()
    assert first_login["code"] == 3


def test_personnel_adjustment_preserves_ids_and_synchronizes_department(client, app):
    headers = _admin_headers(client)
    with app.app_context():
        source = Department.query.filter_by(name="建筑热工检测部").one()
        target = (
            Department.query.filter(
                Department.id != source.id,
                Department.code != "ROOT",
            )
            .order_by(Department.id)
            .first()
        )
        assert target is not None
        target_name = target.name
        source_id, target_id = source.id, target.id

    created = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "account": "qa_adjust_person",
            "name": "调整前姓名",
            "password": "qa_adjust_person123",
            "departmentId": source_id,
            "roleName": "检测员",
        },
    ).get_json()
    assert created["code"] == 0
    user_id = created["data"]["user"]["id"]
    personnel_id = created["data"]["personnelId"]

    adjusted = client.put(
        f"/api/admin/users/{user_id}",
        headers=headers,
        json={
            "name": "调整后姓名",
            "departmentId": target_id,
            "roleName": "审核岗位",
            "enabled": False,
            "personnel": {"position": "审核岗位"},
        },
    ).get_json()
    assert adjusted["code"] == 0
    assert adjusted["data"]["id"] == user_id
    assert adjusted["data"]["departmentId"] == target_id
    assert adjusted["data"]["enabled"] is False

    with app.app_context():
        user = db.session.get(User, user_id)
        person = db.session.get(Personnel, personnel_id)
        assert user.id == user_id
        assert person.id == personnel_id
        assert user.account == person.code == "qa_adjust_person"
        assert user.name == person.name == "调整后姓名"
        assert person.dept == target_name
        assert person.assigned_depts == target_name
        assert person.position == "审核岗位"


def test_quality_roster_rejects_account_renumber_and_removal_disables_login(client, app):
    headers = _admin_headers(client)
    with app.app_context():
        department_id = Department.query.filter_by(name="建筑热工检测部").one().id

    created = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "account": "qa_remove_person",
            "name": "待移出人员",
            "password": "qa_remove_person123",
            "departmentId": department_id,
        },
    ).get_json()
    personnel_id = created["data"]["personnelId"]
    user_id = created["data"]["user"]["id"]

    rejected = client.put(
        f"/api/quality/personnel/{personnel_id}",
        headers=headers,
        json={"code": "renumbered-account", "name": "待移出人员"},
    ).get_json()
    assert rejected["code"] == 1
    assert "不可修改" in rejected["message"]

    removed = client.delete(
        f"/api/quality/personnel/{personnel_id}",
        headers=headers,
    ).get_json()
    assert removed["code"] == 0

    with app.app_context():
        user = db.session.get(User, user_id)
        person = db.session.get(Personnel, personnel_id)
        assert user.enabled is False
        assert person.deleted_at is not None
        assert user.id == user_id
        assert person.id == personnel_id

    # Saving a later account adjustment must not silently restore an explicitly
    # removed roster entry while the login remains disabled.
    adjusted = client.put(
        f"/api/admin/users/{user_id}",
        headers=headers,
        json={"enabled": False},
    ).get_json()
    assert adjusted["code"] == 0
    with app.app_context():
        assert db.session.get(Personnel, personnel_id).deleted_at is not None

    login = client.post(
        "/api/auth/login",
        json={"account": "qa_remove_person", "password": "qa_remove_person123"},
    ).get_json()
    assert login["code"] != 0
