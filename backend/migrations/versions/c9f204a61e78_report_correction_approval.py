"""Typed correction requests, required receipt and appointed approver evidence."""
from alembic import op
import sqlalchemy as sa
revision = "c9f204a61e78"
down_revision = "c4d8a7e10620"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("report_correction_requests") as batch:
        batch.add_column(sa.Column("correction_type", sa.String(16), nullable=True))
        batch.add_column(sa.Column("receipt_attachment_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("approver_account", sa.String(40), nullable=True))
        batch.add_column(sa.Column("approver_name", sa.String(60), nullable=True))
        batch.add_column(sa.Column("approver_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("approver_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_correction_receipt", "report_attachments", ["receipt_attachment_id"], ["id"])

def downgrade():
    raise RuntimeError("Keep correction approval evidence on application rollback; schema removal requires a separate data plan")
