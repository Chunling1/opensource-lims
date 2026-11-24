"""Add measured list-query indexes; no business-row changes."""
from alembic import op
import sqlalchemy as sa

revision = 'd109f0112026'
down_revision = 'c308f0112026'
branch_labels = None
depends_on = None

INDEXES = (
    ('operation_audits', 'ix_oa_object_action', ('object_type', 'object_id', 'action', 'success', 'id')),
    ('operation_audits', 'ix_oa_object_time', ('object_type', 'object_id', 'success', 'created_at')),
    ('reports', 'ix_reports_dept_status', ('department', 'status')),
    ('reports', 'ix_reports_status', ('status',)),
    ('reports', 'ix_reports_owner', ('owner',)),
)

def change(create):
    bind = op.get_bind()
    quote = bind.dialect.identifier_preparer.quote
    for table, name, columns in INDEXES:
        existing = {i['name']: i for i in sa.inspect(bind).get_indexes(table)}
        if name in existing and tuple(existing[name]['column_names']) != columns:
            raise RuntimeError('Index definition mismatch: ' + name)
        if (name in existing) == create:
            continue
        if bind.dialect.name in {'mysql', 'mariadb'}:
            action = ('ADD INDEX ' + quote(name) + ' (' + ', '.join(map(quote, columns)) + ')'
                      if create else 'DROP INDEX ' + quote(name))
            op.execute(sa.text('ALTER TABLE ' + quote(table) + ' ' + action + ', ALGORITHM=INPLACE, LOCK=NONE'))
        elif create:
            op.create_index(name, table, list(columns), unique=False)
        else:
            op.drop_index(name, table_name=table)

def upgrade():
    change(True)

def downgrade():
    change(False)
