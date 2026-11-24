"""Department instrument combinations; existing business data is unchanged."""
from alembic import op
import sqlalchemy as sa
from app.models import JSONText

revision = "e112f0112026"
down_revision = "d109f0112026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("equipment_schemes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("equipment_ids", JSONText(), nullable=False),
        sa.Column("project_ids", JSONText(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("department_id", "name", name="uq_equipment_scheme_department_name"))
    op.create_index("ix_equipment_schemes_department_id", "equipment_schemes", ["department_id"])


def downgrade():
    op.drop_table("equipment_schemes")
