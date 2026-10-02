import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal
from app.models.applicant import Applicant, ApplicantDoc
from app.models.audit import AuditLog
from app.services.receipt_sequence import next_receipt_number
from app.routers import applicants
from conftest import login, csrf


def test_create_rolls_back_if_audit_fails(client, monkeypatch):
    login(client)
    def fail(*args, **kwargs):
        raise HTTPException(503, "Audit unavailable")
    monkeypatch.setattr(applicants, "write_audit", fail)
    response = client.post("/api/applicants", headers=csrf(client), json={"ma_so_hv": "1234567891",
        "ho_ten": "Test User", "ngay_nhan_hs": "2026-10-02", "docs": [{"code": "hoc_ba", "so_luong": 1}]})
    assert response.status_code == 503, response.text
    with SessionLocal() as db:
        assert db.get(Applicant, "1234567891") is None
        assert db.query(ApplicantDoc).filter_by(applicant_ma_so_hv="1234567891").count() == 0


def test_soft_delete_state_and_audit_atomic(client):
    login(client)
    assert client.request("DELETE", "/api/applicants/1234567890", json={"reason": "duplicate"}, headers=csrf(client)).status_code == 204
    with SessionLocal() as db:
        applicant = db.get(Applicant, "1234567890")
        assert applicant.deleted_at is not None and applicant.deleted_reason == "duplicate"
        assert db.query(AuditLog).filter_by(action="DELETE_SOFT").count() == 1
    assert client.get("/api/applicants/recent").json() == []


def test_sequence_rolls_back_and_skips_existing():
    with SessionLocal() as db:
        assert next_receipt_number(db, "2026", "1") == "0002"
        db.rollback()
    with SessionLocal.begin() as db:
        assert next_receipt_number(db, "2026", "1") == "0002"
        assert next_receipt_number(db, "2026", "1") == "0003"


def test_receipt_unique_per_scope():
    with pytest.raises(IntegrityError), SessionLocal.begin() as db:
        db.add(Applicant(ma_so_hv="1234567891", ma_ho_so="0001", khoa="2026", dot="1"))
    with SessionLocal.begin() as db:
        db.add(Applicant(ma_so_hv="1234567891", ma_ho_so="0001", khoa="2026", dot="2"))


def test_print_marking_requires_post(client):
    login(client)
    assert client.get("/api/applicants/1234567890/print?mark_printed=true").status_code == 405


def test_report_limits_reject_without_truncation(client, monkeypatch):
    from app.core.config import settings
    from app.services.report_limits import report_rows
    monkeypatch.setattr(settings, "MAX_REPORT_ROWS", 1)
    with SessionLocal.begin() as db:
        db.add(Applicant(ma_so_hv="1234567891"))
    with SessionLocal() as db, pytest.raises(HTTPException) as exc:
        report_rows(db.query(Applicant))
    assert exc.value.status_code == 422
