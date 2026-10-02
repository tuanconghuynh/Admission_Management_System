from datetime import datetime, timedelta
from aiosmtplib.errors import SMTPConnectError
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import EmailJob
from app.models.applicant import Applicant
from app.models.email_log import EmailLog
from app.services import email_queue
from conftest import login, csrf


def enable_email(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_USER", "sender@example.com")
    monkeypatch.setattr(settings, "SMTP_PASS", "test-only")


def queue(client):
    return client.post("/applicants/1234567890/send-email", headers={**csrf(client), "Idempotency-Key": "test-request"},
        json={"subject": "Test", "html_body": "<p>Hello</p>", "attach_receipt": False})


def test_enqueue_dedup_and_delivery(client, monkeypatch):
    enable_email(monkeypatch)
    login(client)
    first, second = queue(client), queue(client)
    assert first.status_code == second.status_code == 202, first.text
    assert first.json()["job_id"] == second.json()["job_id"]
    with SessionLocal() as db:
        assert db.get(Applicant, "1234567890").status == "saved"
        assert db.query(EmailJob).count() == 1
    sent = []
    async def fake(*args, **kwargs):
        sent.append(args)
    monkeypatch.setattr(email_queue, "send_html_email", fake)
    assert email_queue.process_one()
    assert not email_queue.process_one()
    assert len(sent) == 1
    with SessionLocal() as db:
        assert db.get(Applicant, "1234567890").status == "emailed"
        assert db.query(EmailLog).one().success is True
    assert client.get("/applicants/email-jobs/" + first.json()["job_id"]).json()["state"] == "sent"


def test_smtp_failure_not_logged_as_success(client, monkeypatch):
    enable_email(monkeypatch)
    login(client)
    assert queue(client).status_code == 202
    async def fail(*args, **kwargs):
        raise SMTPConnectError("offline")
    monkeypatch.setattr(email_queue, "send_html_email", fail)
    email_queue.process_one()
    with SessionLocal() as db:
        assert db.query(EmailJob).one().state == "retry"
        assert db.query(EmailLog).one().success is False
        assert db.get(Applicant, "1234567890").status == "saved"


def test_crashed_delivery_requires_review(client, monkeypatch):
    enable_email(monkeypatch)
    login(client)
    assert queue(client).status_code == 202
    claim = email_queue.claim_job()
    assert claim
    with SessionLocal.begin() as db:
        db.get(EmailJob, claim["id"]).locked_until = datetime.utcnow() - timedelta(seconds=1)
    assert email_queue.claim_job() is None
    with SessionLocal() as db:
        assert db.get(EmailJob, claim["id"]).state == "uncertain"


def test_disabled_email_and_invalid_template(client):
    login(client)
    assert queue(client).status_code == 503
    assert client.get("/applicants/1234567890/email-draft?tpl=../../secret").status_code == 422


def test_deleted_applicant_cancels_pending_delivery(client, monkeypatch):
    enable_email(monkeypatch)
    login(client)
    assert queue(client).status_code == 202
    with SessionLocal.begin() as db:
        db.get(Applicant, "1234567890").status = "deleted"
    async def unexpected(*args, **kwargs):
        raise AssertionError("Deleted applicant must not receive queued email")
    monkeypatch.setattr(email_queue, "send_html_email", unexpected)
    assert email_queue.process_one()
    with SessionLocal() as db:
        assert db.query(EmailJob).one().state == "cancelled"
        assert db.query(EmailLog).count() == 0
