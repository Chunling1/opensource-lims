"""Explicit-transaction release primitives; no CLI, commit, network or files.

Caller binds the application's Session to the supplied connection and holds a
maintenance window. The journal is private reference-catalog data, not a backup
of reports. Production orchestration and backups remain separate release gates.
"""
import hashlib
import json

CATALOG_TABLES = ('standards', 'std_library_items', 'capability_import_batches',
                  'capability_entries', 'capability_departments', 'user_standard_denials')
DELETE_ORDER = ('capability_departments', 'user_standard_denials', 'capability_entries',
                'capability_import_batches', 'std_library_items', 'standards')
OLD_REVISION = 'a6d2f9c4e801'
NEW_REVISION = 'b8e091c2d406'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def rows(connection, table):
    result = [dict(row) for row in connection.exec_driver_sql('SELECT * FROM ' + quote(table)).mappings()]
    return sorted(result, key=lambda row: json.dumps(row, sort_keys=True, default=str))


def schema(connection):
    return [dict(row) for row in connection.exec_driver_sql(
        'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').mappings()]


def catalog_snapshot(connection):
    return {table: rows(connection, table) for table in CATALOG_TABLES}


def protected_fingerprints(connection):
    tables = [row['name'] for row in schema(connection) if row['type'] == 'table'
        and not row['name'].startswith('sqlite_') and row['name'] not in (*CATALOG_TABLES, 'alembic_version')]
    return {table: digest(rows(connection, table)) for table in tables}


def require_transaction(connection):
    if connection.dialect.name != 'sqlite' or not connection.connection.driver_connection.in_transaction:
        raise ValueError('必须由发布调用方先在独立SQLite连接上执行BEGIN IMMEDIATE')


def stage_catalog_release(connection, bundle, *, expected_schema, expected_catalog):
    """Stage ONLY the additive column, revision and approved reference catalog.

Never commits or rolls back the caller's transaction. Any exception must cause
the caller to roll back the entire transaction, including the DDL.
"""
    require_transaction(connection)
    from .workbook_scope_import import replace_scope_workbook
    from ...extensions import db
    if db.session.connection() is not connection:
        raise ValueError('导入Session未绑定到发布事务连接')
    before_schema = schema(connection)
    before = catalog_snapshot(connection)
    if digest(before_schema) != expected_schema or digest(before) != expected_catalog:
        raise ValueError('预检后结构或标准目录变化，禁止发布')
    versions = rows(connection, 'alembic_version')
    if versions != [{'version_num': OLD_REVISION}]:
        raise ValueError('迁移版本不是本次确认基线')
    protected = protected_fingerprints(connection)
    connection.exec_driver_sql('ALTER TABLE std_library_items ADD COLUMN is_onsite_standard BOOLEAN DEFAULT 0 NOT NULL')
    after_schema = schema(connection)
    before_defs = {(r['type'], r['name']): r for r in before_schema}
    after_defs = {(r['type'], r['name']): r for r in after_schema}
    if before_defs.keys() != after_defs.keys() or {
        key for key in before_defs if before_defs[key] != after_defs[key]
    } != {('table', 'std_library_items')}:
        raise ValueError('单字段迁移之外出现结构变化')
    result = replace_scope_workbook(bundle)
    db.session.flush()
    connection.exec_driver_sql('UPDATE alembic_version SET version_num=? WHERE version_num=?', (NEW_REVISION, OLD_REVISION))
    if protected_fingerprints(connection) != protected:
        raise ValueError('导入修改了受保护的业务数据，禁止提交')
    if connection.exec_driver_sql('PRAGMA foreign_key_check').fetchone():
        raise ValueError('导入后外键检查失败')
    return {'format': 'standard-catalog-release.v1', 'before': before,
        'after': catalog_snapshot(connection), 'protected': protected,
        'schemaAfter': digest(after_schema), 'revisionAfter': NEW_REVISION, 'result': result}


def stage_catalog_rollback(connection, journal):
    """Undo this catalog batch only, before resuming business. Keep new column.

Any intervening business/catalog change blocks automatic data rollback. No
database restore and no business rows are overwritten. Caller owns commit.
"""
    require_transaction(connection)
    if journal.get('format') != 'standard-catalog-release.v1':
        raise ValueError('回滚记录格式不符')
    if digest(schema(connection)) != journal['schemaAfter'] or rows(connection, 'alembic_version') != [
        {'version_num': journal['revisionAfter']}]:
        raise ValueError('发布后结构或迁移版本已变化，停止自动回滚')
    if protected_fingerprints(connection) != journal['protected']:
        raise ValueError('发布后已有业务变化，停止目录自动回滚；不得恢复全库覆盖新数据')
    current = catalog_snapshot(connection)
    if current != journal['after']:
        raise ValueError('发布后标准目录已变化，停止自动回滚')
    keyed = {}
    for table in CATALOG_TABLES:
        columns = list(connection.exec_driver_sql('PRAGMA table_info(' + quote(table) + ')').mappings())
        primary = [r['name'] for r in sorted(columns, key=lambda r: r['pk']) if r['pk']]
        if not primary:
            raise ValueError('回滚表缺少固定主键')
        before = {tuple(row[k] for k in primary): row for row in journal['before'][table]}
        after = {tuple(row[k] for k in primary): row for row in current[table]}
        if not before.keys() <= after.keys():
            raise ValueError('导入删除了原目录行，不能使用增量回滚')
        keyed[table] = (primary, before, after)
    for table in DELETE_ORDER:
        primary, before, after = keyed[table]
        predicate = ' AND '.join(quote(key) + '=?' for key in primary)
        for key in after.keys() - before.keys():
            connection.exec_driver_sql('DELETE FROM ' + quote(table) + ' WHERE ' + predicate, key)
    for table in CATALOG_TABLES:
        primary, before, after = keyed[table]
        predicate = ' AND '.join(quote(key) + '=?' for key in primary)
        for key, original in before.items():
            changed = {field: value for field, value in original.items() if after[key].get(field) != value}
            if changed:
                connection.exec_driver_sql('UPDATE ' + quote(table) + ' SET ' + ','.join(quote(k) + '=?' for k in changed)
                    + ' WHERE ' + predicate, (*changed.values(), *key))
    if protected_fingerprints(connection) != journal['protected'] or connection.exec_driver_sql('PRAGMA foreign_key_check').fetchone():
        raise ValueError('回滚后业务保护或外键检查失败')
    for table in CATALOG_TABLES:
        restored = rows(connection, table)
        original = journal['before'][table]
        if table == 'std_library_items':
            restored = [{k: v for k, v in row.items() if k != 'is_onsite_standard'} for row in restored]
        if sorted(restored, key=lambda r: json.dumps(r, sort_keys=True)) != sorted(original, key=lambda r: json.dumps(r, sort_keys=True)):
            raise ValueError('回滚结果与原目录不符')
    return {'catalogRolledBack': True, 'businessDataRestored': False, 'additiveColumnRetained': True}
