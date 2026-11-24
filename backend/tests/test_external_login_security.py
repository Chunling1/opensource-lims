"""Real route, separate connections and synthetic credentials; no external calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from sqlalchemy import event
import hashlib
import pytest
from app.extensions import db
from app.models import ExternalAccount
from app.security import hash_password, verify_password

pytest_plugins = ('testkit.fixtures',)
PATH = '/api/public/v1/auth/login'
PASSWORD = 'Local-QA-password-167!'


def seed(app, failed=0, expired=False, legacy=False):
    with app.app_context():
        row = ExternalAccount(account='qa-user', name='QA', mobile='13800001670', email='qa167@example.invalid',
            password_hash=hashlib.sha256(('lims$' + PASSWORD).encode()).hexdigest() if legacy else hash_password(PASSWORD),
            failed_attempts=failed, locked_until=datetime.utcnow()-timedelta(minutes=1) if expired else None)
        db.session.add(row); db.session.commit()


def login(app, password=PASSWORD, account='qa-user'):
    with app.test_client() as client:
        return client.post(PATH, json={'account': account, 'password': password})


def state(app):
    with app.app_context():
        row = ExternalAccount.query.one()
        return row.failed_attempts, row.locked_until, row.password_hash


def test_concurrent_failures_count_and_lock(isolated_app):
    seed(isolated_app, failed=3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: login(isolated_app, 'wrong'), range(2)))
    assert [r.status_code for r in responses] == [401, 401]
    count, locked, _ = state(isolated_app)
    assert count == 5 and locked > datetime.utcnow()
    assert login(isolated_app).status_code == 423
    assert state(isolated_app)[:2] == (count, locked)


@pytest.mark.parametrize('failure_first', [True, False])
@pytest.mark.parametrize('expired', [True, False])
def test_success_and_fifth_failure_are_serialized(isolated_app, monkeypatch, failure_first, expired):
    from app.blueprints import public_portal as portal
    seed(isolated_app, failed=4, expired=expired)
    entered, release, second_started = Event(), Event(), Event()
    first_password = 'wrong' if failure_first else PASSWORD
    def verifier(password, stored):
        if password == first_password:
            entered.set(); assert release.wait(4)
        return verify_password(password, stored)
    monkeypatch.setattr(portal, 'verify_password', verifier)
    def before_sql(conn, cursor, statement, parameters, context, executemany):
        if (statement == 'BEGIN IMMEDIATE' or 'FOR UPDATE' in statement) and entered.is_set():
            second_started.set()
    with isolated_app.app_context():
        engine = db.engine
    event.listen(engine, 'before_cursor_execute', before_sql)
    def second():
        return login(isolated_app, PASSWORD if failure_first else 'wrong')
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(login, isolated_app, first_password)
        assert entered.wait(4)
        other = pool.submit(second); assert second_started.wait(4)
        release.set()
        a, b = first.result(), other.result()
    event.remove(engine, 'before_cursor_execute', before_sql)
    count, locked, _ = state(isolated_app)
    if failure_first:
        assert (a.status_code, b.status_code) == (401, 423)
        assert count == 5 and locked > datetime.utcnow()
    else:
        assert (a.status_code, b.status_code) == (200, 401)
        assert count == 1 and locked is None


def test_valid_login_rehash_and_unknown_release_lock(isolated_app):
    seed(isolated_app, failed=2, legacy=True)
    assert login(isolated_app, account='missing').status_code == 401
    response = login(isolated_app, account='  QA-USER  ')
    assert response.status_code == 200 and response.get_json()['data']['token']
    count, locked, hashed = state(isolated_app)
    assert count == 0 and locked is None and verify_password(PASSWORD, hashed)
    assert hashed != hashlib.sha256(('lims$' + PASSWORD).encode()).hexdigest()
