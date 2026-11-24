"""Independent personal equipment-use department grants; no initial broad grants."""
from alembic import op
import sqlalchemy as sa

revision = 'a182e0112026'
down_revision = 'e167c01a2026'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_equipment_departments',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), primary_key=True))


def downgrade():
    raise RuntimeError('Code rollback retains equipment grants; do not discard personal authorizations')
