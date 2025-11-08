from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal, get_db
from app.core.config import settings
from app.services.sendmail_service import send_html_email, render_email
from app.services import pdf_service
from app.models.applicant import Applicant, ApplicantDoc
from app.models.checklist import ChecklistItem
from app.models.email_log import EmailLog

router = APIRouter(prefix="/applicants", tags=["applicants-email"])


# ---------- Helper ----------
def _load_items_docs(db: Session, a: Applicant):
    items = []
    if getattr(a, "checklist_version_id", None):
        items = (
            db.query(ChecklistItem)
            .filter(ChecklistItem.version_id == a.checklist_version_id)
            .order_by(ChecklistItem.id.asc())
            .all()
        )
    docs = db.query(ApplicantDoc).filter(ApplicantDoc.applicant_ma_so_hv == a.ma_so_hv).all()
    return items, docs


def _ensure_to_email(a: Applicant) -> str:
    to_email = getattr(a, "email_hoc_vien", None) or getattr(a, "email", None)
    if not to_email:
        raise HTTPException(status_code=400, detail="Applicant has no email")
    return to_email


# ---------- Template router ----------
@router.get("/{ma_so_hv}/email-draft")
def get_email_draft(
    ma_so_hv: str,
    db: Session = Depends(get_db),
    a5: bool = Query(True, description="A5 cho biên nhận hồ sơ"),
    tpl: str = Query("confirmation", description="confirmation | student_card | ..."),
):
    """
    Tạo bản nháp email theo template được chỉ định.
    """
    a = db.query(Applicant).filter(Applicant.ma_so_hv == ma_so_hv).first()
    if not a:
        raise HTTPException(404, "Applicant not found")

    to_email = _ensure_to_email(a)
    items, docs = _load_items_docs(db, a)

    # --- render template ---
    if tpl == "student_card":
        subject = "[V-HTPTĐT] THÔNG BÁO PHÁT HÀNH THẺ SINH VIÊN"
        html_body = render_email(
            "email/student_card_email.html",
            {
                "applicant": {
                    "full_name": a.full_name,
                    "ma_so_hv": a.ma_so_hv,
                    "ngay_sinh": a.ngay_sinh.strftime("%d/%m/%Y") if a.ngay_sinh else "",
                    "nganh": getattr(a, "nganh_nhap_hoc", None) or getattr(a, "nganh", None),
                },
                "org_name": "Viện Hợp tác và Phát triển Đào tạo",
            },
        )
        attach_path = None  # thẻ SV không có file đính kèm
    else:
        subject = "[V-HTPTĐT] BIÊN NHẬN HỒ SƠ NHẬP HỌC"
        html_body = render_email(
            "email/confirmation.html",
            {
                "applicant": {
                    "full_name": a.full_name,
                    "ma_ho_so": a.ma_ho_so or a.ma_so_hv,
                    "ma_so_hv": a.ma_so_hv,
                    "ngay_sinh": a.ngay_sinh.strftime("%d/%m/%Y") if a.ngay_sinh else "",
                    "nganh": getattr(a, "nganh_nhap_hoc", None) or getattr(a, "nganh", None),
                },
                "org_name": "Viện Hợp tác và Phát triển Đào tạo",
            },
        )
        pdf_path = pdf_service.save_receipt_pdf_file(
            a=a, items=items, docs=docs, a5=a5, out_dir=settings.RECEIPTS_DIR
        )
        attach_path = pdf_path

    return {
        "to_email": to_email,
        "subject": subject,
        "html_body": html_body,
        "attachment_url": attach_path,
        "a5": a5,
        "template": tpl,
    }


# ---------- Send mail ----------
@router.post("/{ma_so_hv}/send-email")
def send_email_generic(
    ma_so_hv: str,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    tpl: str = Query("confirmation"),
    a5: bool = Query(True),
    subject: str | None = Body(None),
    html_body: str | None = Body(None),
    attach_receipt: bool = Body(False),
):
    """
    Gửi email theo template (xài chung cho mọi mẫu).
    tpl = confirmation | student_card | ...
    """
    a = db.query(Applicant).filter(Applicant.ma_so_hv == ma_so_hv).first()
    if not a:
        raise HTTPException(404, "Applicant not found")

    to_email = _ensure_to_email(a)
    items, docs = _load_items_docs(db, a)
    att_paths = []

    if tpl == "confirmation" and attach_receipt:
        pdf_path = pdf_service.save_receipt_pdf_file(
            a=a, items=items, docs=docs, a5=a5, out_dir=settings.RECEIPTS_DIR
        )
        att_paths.append(pdf_path)

    subj = subject or ( "[V-HTPTĐT] BIÊN NHẬN HỒ SƠ NHẬP HỌC" if tpl == "confirmation"
                        else "[V-HTPTĐT] THÔNG BÁO THẺ SINH VIÊN" )
    html = html_body or render_email(
        f"email/{tpl}.html", {"applicant": {"full_name": a.full_name, "ma_so_hv": a.ma_so_hv}}
    )

    async def _task(ma_so_hv, to_email, subj, html, att_paths):
        session = SessionLocal()
        ok, err = True, None
        try:
            try:
                await send_html_email(
                    subject=subj,
                    recipients=[to_email],
                    html_body=html,
                    attachments=att_paths or None,
                )
            except Exception as e:
                ok, err = False, str(e)
            session.add(EmailLog(
                applicant_ma_so_hv=ma_so_hv,
                applicant_ma_ho_so=getattr(a, "ma_ho_so", None),
                to_email=to_email or "",
                subject=subj,
                success=ok,
                error_message=err,
            ))
            session.commit()
        except SQLAlchemyError:
            session.rollback()
        finally:
            session.close()

    bg.add_task(_task, a.ma_so_hv, to_email, subj, html, att_paths)
    return {"ok": True, "ma_so_hv": a.ma_so_hv, "template": tpl}


# ---------- Batch ----------
@router.post("/send-email-batch")
def send_email_batch(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    tpl: str = Query("confirmation"),
    payload: dict = Body(...),
):
    """
    Gửi email hàng loạt (dùng chung cho mọi template)
    """
    ids = list(map(str, payload.get("ma_so_hv_list") or []))
    if not ids:
        raise HTTPException(400, "ma_so_hv_list is empty")

    async def _task_batch(ids: list[str], tpl: str):
        session = SessionLocal()
        try:
            for mshv in ids:
                a = session.query(Applicant).filter(Applicant.ma_so_hv == mshv).first()
                if not a:
                    continue
                to_email = _ensure_to_email(a)
                subj = "[V-HTPTĐT] BIÊN NHẬN HỒ SƠ NHẬP HỌC" if tpl == "confirmation" else "[V-HTPTĐT] THẺ SINH VIÊN"
                html = render_email(
                    f"email/{tpl}.html",
                    {"applicant": {"full_name": a.full_name, "ma_so_hv": a.ma_so_hv}},
                )
                await send_html_email(
                    subject=subj, recipients=[to_email], html_body=html
                )
                session.add(EmailLog(
                    applicant_ma_so_hv=a.ma_so_hv,
                    applicant_ma_ho_so=a.ma_ho_so,
                    to_email=to_email or "",
                    subject=subj,
                    success=True,
                ))
                session.commit()
        finally:
            session.close()

    bg.add_task(_task_batch, ids, tpl)
    return {"ok": True, "count": len(ids), "template": tpl}
