"""Add server-owned optimistic versions without changing business fields."""
from alembic import op
import sqlalchemy as sa

revision = 'e167c01a2026'
down_revision = 'c9f204a61e78'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('reports', 'entrusts', 'agreements'):
        # MySQL DDL commits per statement. Resume a partially applied upgrade
        # without discarding an existing version or touching business fields.
        existing = next((c for c in sa.inspect(op.get_bind()).get_columns(table)
                         if c['name'] == 'edit_version'), None)
        if existing:
            if not isinstance(existing['type'], sa.Integer) or existing['nullable']:
                raise RuntimeError(f'{table}.edit_version has an incompatible definition')
            continue
        op.add_column(table, sa.Column('edit_version', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    raise RuntimeError('Code rollback retains additive edit_version columns; do not remove concurrency history automatically')
