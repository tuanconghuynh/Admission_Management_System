import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic import command
from app.db.base import Base
from pathlib import Path


def config(connection):
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.attributes["connection"] = connection
    return cfg


def legacy_schema(engine):
    metadata = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name in {"rate_windows", "receipt_sequences", "email_jobs"}:
            continue
        copy = table.to_metadata(metadata)
        if table.name == "applicants":
            for name in ("deleted_at", "deleted_by", "deleted_reason"):
                copy._columns.remove(copy.c[name])
            copy.constraints = {constraint for constraint in copy.constraints if not isinstance(constraint, sa.UniqueConstraint)}
            copy.indexes = set()
            copy.c.khoa.nullable = copy.c.dot.nullable = True
        if table.name == "users":
            copy._columns.remove(copy.c.session_version)
    metadata.create_all(engine)


def test_migrate_legacy_preserves_data_and_is_repeatable(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'migration.sqlite3'}")
    legacy_schema(engine)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO applicants(ma_so_hv,ma_ho_so,khoa,dot) VALUES ('1234567890','0001',NULL,NULL)"))
        command.upgrade(config(conn), "head")
        row = conn.execute(sa.text("SELECT ma_so_hv,ma_ho_so,khoa,dot FROM applicants")).one()
        assert tuple(row) == ("1234567890", "0001", "", "")
        command.upgrade(config(conn), "head")
        assert sa.inspect(conn).has_table("email_jobs")
        assert "session_version" in {c['name'] for c in sa.inspect(conn).get_columns("users")}
    engine.dispose()


def test_migrate_duplicate_preflight_preserves_legacy(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'duplicate.sqlite3'}")
    legacy_schema(engine)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO applicants(ma_so_hv,ma_ho_so,khoa,dot) VALUES ('1234567890','0001',NULL,NULL),('1234567891','0001','','')"))
    with engine.begin() as conn, pytest.raises(RuntimeError, match="Duplicate"):
        command.upgrade(config(conn), "head")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM applicants")).scalar() == 2
        assert "deleted_at" not in {c['name'] for c in sa.inspect(conn).get_columns("applicants")}
    engine.dispose()


def test_migrate_fresh_database(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'fresh.sqlite3'}")
    with engine.begin() as conn:
        command.upgrade(config(conn), "head")
        assert sa.inspect(conn).has_table("applicants")
        assert sa.inspect(conn).has_table("receipt_sequences")
    engine.dispose()
