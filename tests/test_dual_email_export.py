from datetime import date
from io import BytesIO
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from openpyxl import load_workbook
from fastapi import HTTPException

from conftest import login, csrf
from test_email_queue import enable_email
from test_migrations import config, legacy_schema
from app.db.session import SessionLocal
from app.models.applicant import Applicant
from app.models.operations import EmailJob
from app.core.config import settings
from app.services.email_recipients import recipients


def test_update_second_email_and_reject_invalid(client):
    login(client)
    r = client.put('/applicants/1234567890', headers=csrf(client), json={'email_hoc_vien_2': 'second@example.com', 'update_reason': {'key':'khac','text':'Bổ sung email liên hệ'}})
    assert r.status_code == 200, r.text
    response = client.get('/applicants/1234567890')
    assert response.status_code == 200, response.text
    data = response.json()['applicant']
    assert data['email_hoc_vien'] == 'an@example.com'
    assert data['email_hoc_vien_2'] == 'second@example.com'
    r = client.put('/applicants/1234567890', headers=csrf(client), json={'email_hoc_vien_2': 'invalid'})
    assert r.status_code == 422


@pytest.mark.parametrize('choice,expected', [('email1', ['an@example.com']), ('email2', ['second@example.com']), ('both', ['an@example.com','second@example.com'])])
def test_email_selection_and_retry_dedup(client, monkeypatch, choice, expected):
    enable_email(monkeypatch)
    login(client)
    with SessionLocal.begin() as db:
        db.get(Applicant, '1234567890').email_hoc_vien_2 = 'second@example.com'
    for _ in range(2):
        r = client.post('/applicants/1234567890/send-email', headers={**csrf(client), 'Idempotency-Key': 'selection'},
                        json={'recipient_choice': choice})
        assert r.status_code == 202, r.text
        assert r.json()['to_emails'] == expected
    with SessionLocal() as db:
        assert sorted(j.to_email for j in db.query(EmailJob)) == sorted(expected)


def test_both_deduplicates_and_missing_selection_rejected():
    a = SimpleNamespace(email_hoc_vien='an@example.com', email_hoc_vien_2='AN@example.com')
    assert recipients(a, 'both') == ['an@example.com']
    a.email_hoc_vien_2 = None
    with pytest.raises(HTTPException):
        recipients(a, 'email2')


def test_batch_second_email_is_atomic_on_missing(client, monkeypatch):
    enable_email(monkeypatch)
    login(client)
    with SessionLocal.begin() as db:
        db.get(Applicant,'1234567890').email_hoc_vien_2='second@example.com'
        db.add(Applicant(ma_so_hv='1234567891', khoa='26',dot='1',email_hoc_vien='other@example.com'))
    r=client.post('/applicants/send-email-batch',headers=csrf(client),json={
        'ma_so_hv_list':['1234567890','1234567891'],'recipient_choice':'email2'})
    assert r.status_code == 422,r.text
    with SessionLocal() as db:
        assert db.query(EmailJob).count()==0


def test_excel_over_1000_includes_both_emails_and_no_formula(client, monkeypatch):
    login(client)
    monkeypatch.setattr(settings,'MAX_REPORT_ROWS',1000)
    with SessionLocal.begin() as db:
        db.query(Applicant).delete()
        db.add_all([Applicant(ma_so_hv=f'{i:010d}',khoa='26',dot='1',ngay_nhan_hs=date(2026,10,3),
            ho_ten='=1+1', email_hoc_vien='one@example.com',email_hoc_vien_2='two@example.com') for i in range(1001)])
    for path in ['/api/export/excel?date=03/10/2026','/api/export/excel-dot?dot=1&khoa=26']:
        r=client.get(path)
        assert r.status_code==200,r.text
        book=load_workbook(BytesIO(r.content),read_only=True)
        rows=list(book.active.rows)
        assert len(rows)==1002
        headers=[c.value for c in rows[0]]
        assert rows[-1][headers.index('Email 2')].value=='two@example.com'
        assert rows[-1][headers.index('Email 1')].value=='one@example.com'
        assert rows[-1][headers.index('Họ và tên')].data_type=='s'
        book.close()


def test_migration_adds_email2_preserves_email1(tmp_path):
    engine=sa.create_engine(f"sqlite:///{tmp_path/'email.sqlite3'}")
    legacy_schema(engine)
    with engine.begin() as conn:
        conn.execute(sa.text('ALTER TABLE applicants DROP COLUMN email_hoc_vien_2'))
        conn.execute(sa.text("INSERT INTO applicants(ma_so_hv,khoa,dot,email_hoc_vien) VALUES('1234567890','26','1','old@example.com')"))
        command.upgrade(config(conn),'head')
        assert tuple(conn.execute(sa.text('SELECT email_hoc_vien,email_hoc_vien_2 FROM applicants')).one())==('old@example.com',None)
        command.upgrade(config(conn),'head')
    engine.dispose()
