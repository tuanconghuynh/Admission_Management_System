"""Add optional second student email without changing the first address."""
from alembic import op
import sqlalchemy as sa

revision = "20261003_02"
down_revision = "20261002_01"
branch_labels = None
depends_on = None


def upgrade():
    if "email_hoc_vien_2" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("applicants")}:
        op.add_column("applicants", sa.Column("email_hoc_vien_2", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("applicants", "email_hoc_vien_2")
