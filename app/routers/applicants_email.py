from pathlib import Path
from typing import Literal
import uuid
from fastapi import APIRouter, Depends, Request, HTTPException, Query, Body, Header
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.models.applicant import Applicant
from app.models.operations import EmailJob
from app.routers.auth import require_roles
from app.services.rate_limit import limit_email
from app.services.email_queue import enqueue
from app.services.sendmail_service import render_email
from app.services.email_content import _load_items_docs, _merge_items_with_docs_for_email, _normalize_docs_for_pdf, _ensure_to_email
from app.services.pdf_service import render_student_receipt_pdf_a5
from app.utils.soft_delete import ensure_not_deleted

def limit_email_writes(request: Request):
    if request.method == "POST":
        limit_email(request)


router = APIRouter(prefix="/applicants", tags=["applicants-email"],
    dependencies=[Depends(limit_email_writes), Depends(require_roles("Admin", "NhanVien", "Manager"))])
Template = Literal["confirmation", "student_card"]


def content(db, mshv, tpl, attach=False):
    applicant = db.get(Applicant, mshv)
    if not applicant:
        raise HTTPException(404, "Applicant not found")
    ensure_not_deleted(applicant)
    _ensure_to_email(applicant)
    items, docs = _load_items_docs(db, applicant)
    docs = _merge_items_with_docs_for_email(items, docs)
    missing = [d["name"] for d in docs if int(d.get("so_luong") or 0) <= 0]
    subject = "[V.ĐHM] BIÊN NHẬN HỒ SƠ NHẬP HỌC" if tpl == "confirmation" else "[V.ĐHM] THÔNG BÁO PHÁT HÀNH THẺ SINH VIÊN"
    html = render_email("email/confirmation.html" if tpl == "confirmation" else "email/student_card_email.html", {
        "applicant": {"full_name": applicant.full_name, "ma_ho_so": applicant.ma_ho_so or applicant.ma_so_hv,
            "ma_so_hv": applicant.ma_so_hv, "ngay_sinh": applicant.ngay_sinh.strftime("%d/%m/%Y") if applicant.ngay_sinh else "",
            "nganh": applicant.nganh_nhap_hoc}, "org_name": "Viện Đại học Mở HUTECH",
        "docs": docs, "has_missing": bool(missing), "missing_list": missing})
    attachments = []
    if attach and tpl == "confirmation":
        path = settings.receipts_path / f"{uuid.uuid4()}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render_student_receipt_pdf_a5(applicant, _normalize_docs_for_pdf(docs)))
        attachments.append(str(path))
    return applicant, subject, html, attachments


@router.get("/{ma_so_hv}/email-draft")
def draft(ma_so_hv: str, db: Session = Depends(get_db), tpl: Template = Query("confirmation")):
    applicant, subject, html, attachments = content(db, ma_so_hv, tpl, attach=True)
    return {"to_email": applicant.email_hoc_vien, "subject": subject, "html_body": html,
        "attachment_url": "/static/receipts/" + Path(attachments[0]).name if attachments else None, "template": tpl}


@router.post("/{ma_so_hv}/send-email", status_code=202)
def send_email(ma_so_hv: str, request: Request, db: Session = Depends(get_db), tpl: Template = Query("confirmation"),
    subject: str | None = Body(None), html_body: str | None = Body(None), attach_receipt: bool = Body(False),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=128)):
    applicant, default_subject, default_html, attachments = content(db, ma_so_hv, tpl, attach_receipt)
    job = enqueue(db, request, applicant, subject or default_subject, html_body or default_html, attachments, idempotency_key)
    db.commit()
    return {"ok": True, "job_id": job.id, "delivery_state": job.state, "ma_so_hv": ma_so_hv, "status": applicant.status, "template": tpl}


@router.post("/send-email-batch", status_code=202)
def batch(request: Request, db: Session = Depends(get_db), tpl: Template = Query("confirmation"), payload: dict = Body(...),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=128)):
    raw = payload.get("ma_so_hv_list")
    if not isinstance(raw, list) or not raw or len(raw) > settings.MAX_EMAIL_BATCH:
        raise HTTPException(422, f"Danh sách phải có 1–{settings.MAX_EMAIL_BATCH} hồ sơ")
    jobs = []
    for mshv in dict.fromkeys(map(str, raw)):
        applicant, subject, html, attachments = content(db, mshv, tpl)
        job = enqueue(db, request, applicant, subject, html, attachments, idempotency_key)
        jobs.append(job.id)
    db.commit()
    return {"ok": True, "count": len(jobs), "job_ids": jobs, "template": tpl, "delivery_state": "queued"}


@router.get("/email-jobs/{job_id}")
def job_status(job_id: str, request: Request, db: Session = Depends(get_db)):
    job = db.get(EmailJob, job_id)
    if not job or (request.session.get("role") != "Admin" and job.actor.get("uid") != request.session.get("uid")):
        raise HTTPException(404, "Job not found")
    return {"id": job.id, "state": job.state, "attempts": job.attempts, "error": job.last_error,
        "completed_at": job.completed_at}
