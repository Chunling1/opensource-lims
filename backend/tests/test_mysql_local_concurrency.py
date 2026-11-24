"""Optional real MySQL checks; creates its own Unix-socket-only test server.

No database URI/credentials are accepted from the environment. No production
connection is possible. Install mysql-server-core-8.0 in the QA image to run.
"""
from pathlib import Path
import shutil
import subprocess
import time
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor

import pytest
import pymysql
from sqlalchemy.orm import Query
from app import create_app
from app.extensions import db
from app.models import ExternalAccount
from app.security import verify_password
from testkit.app import isolated_config
import test_external_login_security as cases


@pytest.fixture(scope='module')
def mysql_server(tmp_path_factory):
    executable = shutil.which('mysqld')
    if not executable:
        pytest.skip('isolated MySQL server binary is unavailable')
    root = tmp_path_factory.mktemp('mysql167')
    data = root / 'data'
    subprocess.run([executable, '--no-defaults', '--initialize-insecure', '--user=root',
                    f'--datadir={data}'], check=True, capture_output=True, timeout=60)
    socket = root / 'mysql.sock'
    process = subprocess.Popen([executable, '--no-defaults', '--user=root', f'--datadir={data}',
        f'--socket={socket}', f'--pid-file={root / "mysql.pid"}', f'--log-error={root / "mysql.log"}',
        '--skip-networking', '--mysqlx=OFF', '--innodb-buffer-pool-size=64M', f'--secure-file-priv={root}'])
    try:
        for _ in range(100):
            try:
                connection = pymysql.connect(unix_socket=str(socket), user='root')
                connection.close()
                break
            except pymysql.Error:
                assert process.poll() is None, (root / 'mysql.log').read_text()
                time.sleep(.1)
        else:
            pytest.fail('isolated MySQL startup timed out')
        yield socket
    finally:
        process.terminate(); process.wait(timeout=30)


@pytest.fixture
def mysql_app(mysql_server, tmp_path):
    connection = pymysql.connect(unix_socket=str(mysql_server), user='root', autocommit=True)
    with connection.cursor() as cursor:
        cursor.execute('CREATE DATABASE IF NOT EXISTS qa167')
        cursor.execute('DROP TABLE IF EXISTS qa167.external_accounts')
    connection.close()
    config = isolated_config(tmp_path)
    # This separate fixture intentionally supports only the socket it just made.
    config.SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://root@localhost/qa167?unix_socket={mysql_server}'
    app = create_app(config)
    with app.app_context():
        assert db.engine.url.query['unix_socket'] == str(mysql_server)
        ExternalAccount.__table__.create(db.engine)
    yield app
    with app.app_context():
        db.session.remove(); db.engine.dispose()


@pytest.mark.parametrize('failure_first', [True, False])
@pytest.mark.parametrize('expired', [True, False])
def test_mysql_success_failure_serialization(mysql_app, monkeypatch, failure_first, expired):
    cases.test_success_and_fifth_failure_are_serialized(mysql_app, monkeypatch, failure_first, expired)


def test_mysql_failures_and_legitimate_controls(mysql_app):
    cases.test_concurrent_failures_count_and_lock(mysql_app)


def test_mysql_rehash_and_unknown_account(mysql_app):
    cases.test_valid_login_rehash_and_unknown_release_lock(mysql_app)


def test_mysql_original_lost_increment_negative_control(mysql_app, monkeypatch):
    from app.blueprints import public_portal
    cases.seed(mysql_app, failed=3)
    barrier = Barrier(2)
    def verify(password, stored):
        barrier.wait(timeout=4)
        return verify_password(password, stored)
    monkeypatch.setattr(Query, 'with_for_update', lambda self, **kwargs: self)
    monkeypatch.setattr(public_portal, 'verify_password', verify)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: cases.login(mysql_app, 'wrong'), range(2)))
    assert [r.status_code for r in results] == [401, 401]
    assert cases.state(mysql_app)[0] == 4  # Old implementation loses one failure.


def test_mysql_additive_migration_resume_and_old_code_compatibility(mysql_app):
    import importlib.util
    from sqlalchemy import text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'migrations/versions/e167c01a2026_business_edit_versions.py'
    spec = importlib.util.spec_from_file_location('revision167mysql', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with mysql_app.app_context(), db.engine.begin() as connection:
        for table in ('reports', 'entrusts', 'agreements'):
            connection.execute(text(f'CREATE TABLE {table} (id INT PRIMARY KEY, client VARCHAR(100))'))
            connection.execute(text(f"INSERT INTO {table} VALUES (1, 'unchanged')"))
        # Simulate an interrupted migration after the first MySQL auto-commit.
        connection.execute(text('ALTER TABLE reports ADD edit_version INT NOT NULL DEFAULT 1'))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
        for table in ('reports', 'entrusts', 'agreements'):
            assert connection.execute(text(f'SELECT client, edit_version FROM {table}')).one() == ('unchanged', 1)
            # The previous release omits the additive column on insert/update.
            connection.execute(text(f"INSERT INTO {table} (id, client) VALUES (2, 'old-code')"))
            connection.execute(text(f"UPDATE {table} SET client='retained' WHERE id=1"))
            assert connection.execute(text(f'SELECT edit_version FROM {table} WHERE id=2')).scalar() == 1
