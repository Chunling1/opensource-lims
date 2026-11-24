"""Administrator reset returns account + five random digits, never a fixed suffix."""
import json
import string

from app.extensions import db
from app.models import OperationAudit
from app.platform.identity.login_security import password_is_strong
from app.security import issue_token, verify_password

pytest_plugins = ('testkit.fixtures',)


def test_admin_reset_generates_five_digits_and_keeps_password_out_of_audit(isolated_client, scenario_factory, monkeypatch):
    department = scenario_factory.department()
    admin = scenario_factory.user(department, permissions=['system.user.view'])
    target = scenario_factory.user(department, account='fixture_reset')
    db.session.commit()
    headers = {'Authorization': 'Bearer ' + issue_token(admin)}
    random_values = iter([0, 89999])
    monkeypatch.setattr('app.platform.identity.login_security.secrets.randbelow', lambda limit: next(random_values))
    previous = None
    for suffix in ['10000', '99999']:
        response = isolated_client.post(f'/api/admin/users/{target.id}/reset-password', headers=headers).get_json()
        assert response['code'] == 0
        temporary = response['data']['tempPassword']
        assert temporary == target.account + suffix
        db.session.refresh(target)
        assert verify_password(temporary, target.password_hash)
        assert target.must_change_password
        assert not verify_password(target.account + '123', target.password_hash)
        if previous:
            assert not verify_password(previous, target.password_hash)
        previous = temporary
        audits = OperationAudit.query.filter_by(object_type='user', object_id=str(target.id)).all()
        assert audits
        for audit in audits:
            values = {column.name: getattr(audit, column.name) for column in audit.__table__.columns}
            content = json.dumps(values, default=str)
            assert temporary not in content
            assert target.password_hash not in content


def test_ascii_punctuation_including_exclamation_matches_frontend_policy():
    for symbol in string.punctuation:
        assert password_is_strong('Abcdef12' + symbol)
    for value in ['Abcdef12', 'Abcdef12 ', 'Abcdef12中', 'abcdef12!', 'ABCDEF12!', 'Abcdefgh!']:
        assert not password_is_strong(value)
