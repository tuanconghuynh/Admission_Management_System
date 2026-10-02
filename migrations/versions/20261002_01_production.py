"""Adopt existing AMS database without dropping tables or applicant data."""
from alembic import op
import sqlalchemy as sa
from app.db.base import Base
import app.models

revision = "20261002_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    legacy = inspector.has_table("applicants")
    if legacy:
        # MySQL DDL commits implicitly: validate before making ANY schema changes.
        duplicate = bind.execute(sa.text("""
            SELECT COALESCE(TRIM(khoa), '') AS khoa, COALESCE(TRIM(dot), '') AS dot,
                   TRIM(ma_ho_so) AS ma_ho_so, COUNT(*) AS total
            FROM applicants WHERE ma_ho_so IS NOT NULL AND TRIM(ma_ho_so) <> ''
            GROUP BY COALESCE(TRIM(khoa), ''), COALESCE(TRIM(dot), ''), TRIM(ma_ho_so)
            HAVING COUNT(*) > 1 LIMIT 1
        """)).first()
        if duplicate:
            raise RuntimeError("Duplicate receipt numbers within khoa/dot. Resolve duplicates before migrating; no data was changed.")
        columns = {c["name"] for c in inspector.get_columns("applicants")}
        for name, typ in [("deleted_at", sa.DateTime()), ("deleted_by", sa.String(255)), ("deleted_reason", sa.Text())]:
            if name not in columns:
                op.add_column("applicants", sa.Column(name, typ, nullable=True))
        bind.execute(sa.text("UPDATE applicants SET khoa=COALESCE(TRIM(khoa), ''), dot=COALESCE(TRIM(dot), ''), ma_ho_so=NULLIF(TRIM(ma_ho_so), '')"))
        if bind.dialect.name == "mysql":
            for name in ("khoa", "dot"):
                op.alter_column("applicants", name, existing_type=sa.String(64), nullable=False, server_default="")
    if inspector.has_table("users") and "session_version" not in {c["name"] for c in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    # Only creates missing tables. Existing structures are explicitly migrated above.
    Base.metadata.create_all(bind=bind)
    inspector = sa.inspect(bind)
    existing_unique = {c["name"] for c in inspector.get_unique_constraints("applicants")}
    existing_unique |= {c["name"] for c in inspector.get_indexes("applicants") if c.get("unique")}
    if "uq_applicant_receipt_scope" not in existing_unique:
        op.create_index("uq_applicant_receipt_scope", "applicants", ["khoa", "dot", "ma_ho_so"], unique=True)
    for table_name in ("applicants", "audit_logs"):
        known = {index["name"] for index in inspector.get_indexes(table_name)}
        for index in Base.metadata.tables[table_name].indexes:
            if index.name not in known:
                index.create(bind=bind)


def downgrade():
    raise RuntimeError("Restore the verified database backup to roll back this baseline; automatic downgrade is intentionally disabled")
