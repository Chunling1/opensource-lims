"""Keep descriptive workflow content intact; layout limits belong to templates."""
from alembic import op
import sqlalchemy as sa

revision = 'b186f0112026'
down_revision = 'a182e0112026'
branch_labels = None
depends_on = None

FIELDS = {
    'reports': ('project', 'project_name', 'client', 'out_of_scope_note'),
    'equipment_usage_records': ('project',),
    'operation_audits': ('message',),
    'report_render_jobs': ('message',),
    'report_attachments': ('name', 'content_type'),
}


def upgrade():
    bind = op.get_bind()
    for table, names in FIELDS.items():
        columns = {c['name']: c for c in sa.inspect(bind).get_columns(table)}
        for name in names:
            column = columns[name]
            # MySQL DDL commits per statement: an interrupted upgrade can resume.
            if isinstance(column['type'], sa.Text):
                continue
            if not isinstance(column['type'], sa.String):
                raise RuntimeError(f'Unexpected type for {table}.{name}')
            if bind.dialect.name == 'dm':
                op.execute(sa.text(f'ALTER TABLE {table} MODIFY {name} CLOB'))
            else:
                with op.batch_alter_table(table) as batch:
                    batch.alter_column(name, existing_type=column['type'],
                                       type_=sa.Text(), existing_nullable=column['nullable'])


def downgrade():
    raise RuntimeError('Code rollback retains widened text fields; narrowing could lose business content')
