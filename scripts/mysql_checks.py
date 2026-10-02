"""Integration checks in an owned disposable MySQL schema, never in live tables."""
import os
import sys
import re
import uuid
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))
from app.core.config import settings
from app.db.base import Base
import app.models
from app.models.applicant import Applicant
from app.services.receipt_sequence import next_major_receipt
from app.services import email_queue
from app.models.operations import EmailJob
from app.models.user import User
from app.models.audit import AuditLog
from app.services.print_confirmation import print_headers
from app.routers.print_confirmation import confirm, ConfirmPrint
from starlette.requests import Request
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-root", action="store_true", help="Test via the legacy local root account without changing .env")
    args = parser.parse_args()
    url = sa.engine.make_url("mysql+pymysql://root:@127.0.0.1:3306" if args.local_root else settings.SQLALCHEMY_DATABASE_URI)
    if url.host not in {"localhost", "127.0.0.1"} or url.get_backend_name() != "mysql":
        raise SystemExit("Integration check requires local MySQL; live remote databases are excluded")
    name = "ams_test_" + uuid.uuid4().hex
    assert re.fullmatch(r"ams_test_[a-f0-9]{32}", name)
    server = sa.create_engine(url.set(database=None), connect_args={"connect_timeout": 5})
    created = False
    test_engine = None
    try:
        with server.connect() as connection:
            connection.execute(sa.text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            created = True
        test_engine = sa.create_engine(url.set(database=name), pool_size=10, max_overflow=5)
        with test_engine.begin() as connection:
            cfg = Config(str(root/'alembic.ini'))
            cfg.attributes['connection'] = connection
            command.upgrade(cfg, 'head')
        Session = sessionmaker(bind=test_engine)
        def reserve(index):
            with Session.begin() as db:
                code = next_major_receipt(db, 'CNTT', "2026", "1")
                db.add(Applicant(ma_so_hv=f"{index:010d}", ma_ho_so=code, khoa="2026", dot="1"))
                return code
        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = list(pool.map(reserve, range(1, 25)))
        assert len(set(codes)) == 24
        assert sorted(codes) == [f"CNTT-01-{n:04d}" for n in range(1, 25)]
        with Session.begin() as db:
            assert next_major_receipt(db, 'CNTT', '2026', '2') == 'CNTT-02-0001'
            assert next_major_receipt(db, 'NNA', '2026', '1') == 'NNA-01-0001'
            user = User(username='print-check', password_hash='test-only-unused', role='Admin', must_change_password=False)
            db.add(user)
            db.flush()
            uid = user.id
        request = Request({'type':'http','method':'POST','path':'/print-confirm','headers':[],
            'query_string':b'', 'scheme':'http','server':('localhost',80),'client':('127.0.0.1',1234),'session':{'uid':uid}})
        token = print_headers(request, ['0000000001'], 'A4')['X-Print-Token']
        def confirm_once(_):
            with Session() as db:
                return confirm(ConfirmPrint(token=token), request, db, SimpleNamespace(id=uid))
        with ThreadPoolExecutor(max_workers=8) as pool:
            confirmations = list(pool.map(confirm_once, range(8)))
        assert sum(not result.get('already_confirmed',False) for result in confirmations) == 1
        with Session() as db:
            assert db.query(AuditLog).filter_by(action='PRINT').count() == 1
            assert db.query(AuditLog).filter(AuditLog.target_type == 'PrintJob',
                sa.cast(AuditLog.new_values['mshv'], sa.String).contains('"0000000001"')).count() == 1
            assert db.get(Applicant,'0000000001').printed is True
        email_queue.SessionLocal = Session
        with Session.begin() as db:
            db.add(EmailJob(id=str(uuid.uuid4()), dedup_key="claim-test", applicant_ma_so_hv="0000000001",
                to_email="an@example.com", subject="test", html_body="test", state="pending", attempts=0))
        with ThreadPoolExecutor(max_workers=8) as pool:
            claims = list(pool.map(lambda _: email_queue.claim_job(), range(8)))
        claimed = sum(claim is not None for claim in claims)
        with Session() as db:
            job = db.query(EmailJob).one()
            assert claimed == 1, f"claims={claimed} state={job.state} attempts={job.attempts} available={job.available_at}"
        print("MySQL migration, 24 receipt reservations, 8 print confirmations (one log) and 8 email claims passed")
    finally:
        if test_engine:
            test_engine.dispose()
        if created:
            # Only delete the exact randomly named schema created by this invocation.
            with server.connect() as connection:
                connection.execute(sa.text(f"DROP DATABASE `{name}`"))
        server.dispose()


if __name__ == '__main__':
    try:
        main()
    except sa.exc.OperationalError as exc:
        code = exc.orig.args[0] if exc.orig.args else "unknown"
        raise SystemExit(f"MySQL integration unavailable (error {code}); check database authentication and privileges") from None
