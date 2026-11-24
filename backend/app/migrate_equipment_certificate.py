"""Additive, explicit migration. Run before deploying the certificate-aware model.

DATABASE_URL=<existing configured URL> python -m app.migrate_equipment_certificate
Default is dry-run; --apply adds one nullable column. Never seeds or drops data.
"""
import argparse
import json
import os
from sqlalchemy import create_engine, inspect, text


def migrate(engine, apply=False):
    inspector = inspect(engine)
    if not inspector.has_table('equipment_items'):
        raise RuntimeError('equipment_items does not exist; refusing to initialize a database')
    if 'certificate_no' in {column['name'] for column in inspector.get_columns('equipment_items')}:
        return {'status': 'already-present', 'changed': False}
    if not apply:
        return {'status': 'pending', 'changed': False, 'column': 'equipment_items.certificate_no'}
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE equipment_items ADD COLUMN certificate_no VARCHAR(160) NULL'))
    assert 'certificate_no' in {c['name'] for c in inspect(engine).get_columns('equipment_items')}
    return {'status': 'applied', 'changed': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    url = os.environ.get('DATABASE_URL')
    if not url:
        parser.error('DATABASE_URL is required; use the existing application database configuration')
    engine = create_engine(url)
    try:
        print(json.dumps(migrate(engine, args.apply)))
    finally:
        engine.dispose()
