"""Read-only deployment evidence; writes only the requested local receipt."""
import argparse
import hashlib
import json
from pathlib import Path
from sqlalchemy import create_engine, text


def snapshot(connection):
    digest = hashlib.sha256()
    count = 0
    for row in connection.execute(text(
        'SELECT id, archive_no, actual_cal_date, last_cal_date, plan_cal_date, '
        'valid_until, certificate_no, keeper FROM equipment_items '
        'WHERE deleted_at IS NULL ORDER BY id'
    )):
        digest.update((json.dumps(list(row), ensure_ascii=False, separators=(',', ':')) + '\n').encode())
        count += 1
    return dict(count=count, sha256=digest.hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--phase', required=True, choices=('before', 'after'))
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text()) if args.receipt.exists() else {}
    evidence = receipt.setdefault('equipmentItemsFingerprint', {})
    if args.phase == 'before' and 'before' in evidence:
        raise RuntimeError('Before fingerprint already recorded; preserve the original release evidence')
    if args.phase == 'after' and 'before' not in evidence:
        raise RuntimeError('Before fingerprint is required')
    engine = create_engine(json.loads(args.runtime.read_text())['DATABASE_URL'])
    with engine.connect() as connection:
        try:
            if connection.dialect.name == 'mysql':
                connection.exec_driver_sql('SET SESSION max_execution_time=120000')
                connection.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
                connection.commit()
            evidence[args.phase] = snapshot(connection)
        finally:
            connection.rollback()
    engine.dispose()
    if args.phase == 'after':
        evidence['identical'] = evidence['before'] == evidence['after']
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    if args.phase == 'after' and not evidence['identical']:
        raise SystemExit('Equipment ledger fingerprint changed; inspect business writes before accepting release')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
