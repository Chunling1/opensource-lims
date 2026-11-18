"""Record arrival times for the worklist. Legacy rows without evidence stay undated."""

from alembic import op
import sqlalchemy as sa

revision = "p02_002"
down_revision = "p10_001"


def upgrade():
    op.add_column("tasks", sa.Column("arrived", sa.DateTime(timezone=True), nullable=True))
    op.execute("""UPDATE tasks SET arrived=(
        SELECT MAX(h.at) FROM action_history h WHERE h.sample_id=tasks.sample_id
        AND ((tasks.kind='author' AND ((h.report_id=tasks.report_id AND h.action='create') OR h.action='transfer'))
          OR (tasks.kind='review1' AND h.report_id=tasks.report_id AND h.action='submit')
          OR (tasks.kind='claim' AND h.action='return')))
        WHERE NOT closed""")
