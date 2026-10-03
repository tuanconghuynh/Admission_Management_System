"""Durable email outbox. SMTP delivery is never an exactly-once transaction."""
import asyncio
import hashlib
import json
import logging
import uuid
from datetime import timezone, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from aiosmtplib.errors import SMTPConnectError, SMTPAuthenticationError, SMTPRecipientsRefused

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import EmailJob
from app.models.applicant import Applicant
from app.models.email_log import EmailLog
from app.services.audit import write_audit
from app.services.sendmail_service import send_html_email

log = logging.getLogger("email-worker")


def enqueue(db, request, applicant, subject, html, attachments, idempotency_key=None, *, to_email=None):
    if not settings.smtp_ready:
        raise HTTPException(503, "Email chưa được cấu hình hoặc đang tắt")
    if len(subject) > 255 or len(html.encode()) > 200_000:
        raise HTTPException(422, "Email content too large")
    to_email = to_email or applicant.email_hoc_vien
    uid = request.session.get("uid")
    content = [uid, applicant.ma_so_hv, to_email, subject, html, bool(attachments)]
    # Default suppresses accidental repeated clicks for five minutes.
    content.append(idempotency_key or str(int(datetime.now(timezone.utc).timestamp()) // 300))
    key = hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()
    existing = db.query(EmailJob).filter_by(dedup_key=key).first()
    if existing:
        return existing
    actor = {k: request.session.get(k) for k in ("uid", "full_name", "username", "role")}
    job = EmailJob(id=str(uuid.uuid4()), dedup_key=key, applicant_ma_so_hv=applicant.ma_so_hv,
        to_email=to_email, subject=subject, html_body=html, attachments=attachments,
        actor=actor, state="pending", attempts=0)
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        return db.query(EmailJob).filter_by(dedup_key=key).one()
    write_audit(db, action="EMAIL_QUEUED", target_type="Applicant", target_id=applicant.ma_so_hv,
        new_values={"job_id": job.id}, status="SUCCESS", request=request)
    return job


def claim_job():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Release housekeeping locks before claiming. InnoDB can lock non-matching
    # rows during UPDATE under REPEATABLE READ, causing SKIP LOCKED starvation.
    with SessionLocal.begin() as db:
        # A crashed worker may already have handed the message to SMTP.
        # Never resend automatically when that outcome is unknown.
        db.execute(update(EmailJob).where(EmailJob.state == "processing", EmailJob.locked_until < now)
            .values(state="uncertain", last_error="Worker stopped during delivery; verify mailbox before resending"))
    with SessionLocal.begin() as db:
        query = select(EmailJob).where(EmailJob.state.in_(["pending", "retry"]),
            EmailJob.available_at <= now, EmailJob.attempts < settings.EMAIL_MAX_ATTEMPTS).order_by(EmailJob.created_at).limit(1)
        if db.bind.dialect.name == "mysql":
            query = query.with_for_update(skip_locked=True)
        job = db.execute(query).scalar_one_or_none()
        if not job:
            return None
        lease = str(uuid.uuid4())
        changed = db.execute(update(EmailJob).where(EmailJob.id == job.id, EmailJob.state.in_(["pending", "retry"]))
            .values(state="processing", attempts=EmailJob.attempts + 1, lease_token=lease,
                locked_until=now + timedelta(minutes=5)))
        if not changed.rowcount:
            return None
        db.flush()
        db.refresh(job)
        return {"id": job.id, "lease": lease, "to_email": job.to_email, "subject": job.subject,
            "html_body": job.html_body, "attachments": job.attachments, "attempts": job.attempts}


def process_one():
    payload = claim_job()
    if not payload:
        return False
    with SessionLocal.begin() as db:
        job = db.get(EmailJob, payload["id"])
        applicant = db.get(Applicant, job.applicant_ma_so_hv)
        if not applicant or applicant.status == "deleted":
            job.state = "cancelled"
            job.last_error = "Applicant no longer available"
            job.locked_until = None
            job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            write_audit(db, action="EMAIL_CANCELLED", target_type="Applicant",
                target_id=job.applicant_ma_so_hv, new_values={"job_id": job.id}, status="SUCCESS", request=None)
            return True
    error, safe_retry = None, False
    try:
        asyncio.run(send_html_email(payload["subject"], [payload["to_email"]], payload["html_body"], payload["attachments"]))
    except Exception as exc:
        # Connect/auth/recipient rejection happened before successful acceptance.
        safe_retry = isinstance(exc, (SMTPConnectError, SMTPAuthenticationError, SMTPRecipientsRefused, FileNotFoundError))
        error = type(exc).__name__  # do not persist SMTP credentials or full message data
        log.warning("Delivery failed job=%s error=%s", payload["id"], error)
    with SessionLocal.begin() as db:
        job = db.query(EmailJob).filter_by(id=payload["id"], lease_token=payload["lease"], state="processing").with_for_update().first()
        if not job:
            return True
        applicant = db.get(Applicant, job.applicant_ma_so_hv)
        if error:
            job.last_error = error
            job.state = "retry" if safe_retry and job.attempts < settings.EMAIL_MAX_ATTEMPTS else ("failed" if safe_retry else "uncertain")
            job.available_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=60 * job.attempts)
        else:
            job.state, job.completed_at = "sent", datetime.now(timezone.utc).replace(tzinfo=None)
            if applicant and applicant.status != "deleted":
                applicant.status = "emailed"
        job.locked_until = None
        db.add(EmailLog(applicant_ma_so_hv=applicant.ma_so_hv if applicant else None,
            applicant_ma_ho_so=applicant.ma_ho_so if applicant else None, to_email=job.to_email,
            subject=job.subject, success=error is None, error_message=error))
        write_audit(db, action="EMAIL_SENT" if error is None else "EMAIL_FAILED", target_type="Applicant",
            target_id=job.applicant_ma_so_hv, new_values={"job_id": job.id, "state": job.state, "actor": job.actor},
            status="SUCCESS" if error is None else "FAILURE", request=None)
    return True
