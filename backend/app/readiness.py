"""Bounded dependency readiness, separate from process liveness."""
import os
import threading
import time
from pathlib import Path

from flask import jsonify
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from .extensions import db

REVISION = '20261014-stability-v1'


def install_readiness(app):
    lock = threading.Lock()
    cached = {'until': 0.0, 'body': None, 'status': 503}
    probe_engine = None

    def database_ready():
        nonlocal probe_engine
        if probe_engine is None:
            live = db.engine
            driver = live.url.drivername
            # Separate bounded connection: an exhausted business pool cannot
            # hold a readiness request for the pool's ordinary long timeout.
            args = dict((app.config.get('SQLALCHEMY_ENGINE_OPTIONS') or {}).get('connect_args') or {})
            if driver == 'mysql+pymysql':
                args.update(connect_timeout=2, read_timeout=2, write_timeout=2)
            elif driver.startswith('sqlite'):
                args.update(timeout=2)
            else:
                return False
            probe_engine = create_engine(live.url, connect_args=args,
                pool_size=1, max_overflow=0, pool_timeout=0.2,
                pool_recycle=60, pool_pre_ping=False,
                poolclass=QueuePool)
        try:
            with probe_engine.connect() as connection:
                return connection.execute(text('SELECT 1')).scalar() == 1
        except Exception:
            # A failed connection is discarded before the next bounded probe.
            probe_engine.dispose()
            return False

    @app.get('/api/ready')
    def ready():
        now = time.monotonic()
        if cached['body'] is not None and now < cached['until']:
            return jsonify(cached['body']), cached['status'], {'Cache-Control': 'no-store'}
        if not lock.acquire(blocking=False):
            return jsonify({'code': 503, 'message': 'readiness probe busy',
                'data': {'status': 'not_ready', 'revision': REVISION}}), 503, {'Cache-Control': 'no-store'}
        try:
            # Avoid a second probe after a contender observed an expired cache.
            if cached['body'] is None or time.monotonic() >= cached['until']:
                try:
                    database = database_ready()
                except Exception:
                    database = False
                root = app.config.get('STORAGE_ROOT')
                try:
                    storage = bool(root and Path(root).is_dir() and os.access(root, os.R_OK | os.X_OK))
                except (OSError, TypeError, ValueError):
                    storage = False
                healthy = database and storage
                cached.update(until=time.monotonic() + 5, status=200 if healthy else 503,
                    body={'code': 0 if healthy else 503, 'message': 'ok' if healthy else 'not ready',
                          'data': {'status': 'ready' if healthy else 'not_ready',
                                   'checks': {'database': database, 'storageReadable': storage},
                                   'revision': REVISION}})
            return jsonify(cached['body']), cached['status'], {'Cache-Control': 'no-store'}
        finally:
            lock.release()
