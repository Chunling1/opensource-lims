import importlib.util
from pathlib import Path
from sqlalchemy import create_engine, text


def test_release_fingerprint_detects_field_change_but_ignores_version(tmp_path):
    path = Path(__file__).resolve().parents[2] / 'scripts' / 'equipment_fingerprint.py'
    spec = importlib.util.spec_from_file_location('equipment_fingerprint', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine('sqlite:///' + str(tmp_path / 'fingerprint.db'))
    with engine.begin() as c:
        c.execute(text('CREATE TABLE equipment_items (id INTEGER, archive_no TEXT, actual_cal_date TEXT, last_cal_date TEXT, plan_cal_date TEXT, valid_until TEXT, certificate_no TEXT, keeper TEXT, deleted_at TEXT, edit_version INTEGER)'))
        c.execute(text("INSERT INTO equipment_items VALUES (1,'A','2026-01-01','2026-01-01','2026-12-31','2026-12-31','CERT','K',NULL,1)"))
    with engine.connect() as c:
        before = module.snapshot(c)
        assert before['count'] == 1
        c.execute(text('UPDATE equipment_items SET edit_version=2'))
        assert module.snapshot(c) == before
        c.execute(text("UPDATE equipment_items SET keeper=''"))
        assert module.snapshot(c)['sha256'] != before['sha256']
        c.rollback()
    engine.dispose()
