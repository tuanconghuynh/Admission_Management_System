# app/routers/applicants_email.py
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

from app.core.config import settings
from app.services.sendmail_service import send_html_email, render_email
from app.services import pdf_service

from sqlalchemy.exc import SQLAlchemyError

try:
    from app.db.session import get_db
except Exception:
    from app.db import get_db

from app.models.applicant import Applicant, ApplicantDoc
from app.models.checklist import ChecklistItem
from app.models.email_log import EmailLog

router = APIRouter(prefix="/applicants", tags=["applicants-email"])

def _load_items_docs(db: Session, a: Applicant):
    if a.checklist_version_id is None:
        items = []
    else:
        items = (
            db.query(ChecklistItem)
            .filter(ChecklistItem.version_id == a.checklist_version_id)
            .order_by(ChecklistItem.id.asc())
            .all()
        )
    docs = (
        db.query(ApplicantDoc)
        .filter(ApplicantDoc.applicant_ma_so_hv == a.ma_so_hv)
        .all()
    )
    return items, docs

def _default_subject():
    return "[V-HTPTĐT] BIÊN NHẬN HỒ SƠ NHẬP HỌC"

def _default_html(a: Applicant):
    return render_email(
        "email/confirmation.html",
        {
            "applicant": {
                "full_name": a.full_name,
                "ma_ho_so": a.ma_ho_so or a.ma_so_hv,
                "ma_so_hv": a.ma_so_hv,
                "ngay_sinh": a.ngay_sinh.strftime("%d/%m/%Y") if a.ngay_sinh else "",
                "khoa": getattr(a, "khoa", None),
                "dot": getattr(a, "dot", None),
                "nganh": getattr(a, "nganh_nhap_hoc", None) or getattr(a, "nganh", None),
            },
            "org_name": "Viện Hợp tác và Phát triển Đào tạo",
        },
    )



def _ensure_to_email(a: Applicant) -> str:
    to_email = getattr(a, "email_hoc_vien", None) or getattr(a, "email", None)
    if not to_email:
        raise HTTPException(status_code=400, detail="Applicant has no email")
    return to_email


@router.get("/{ma_so_hv}/email-draft")
def get_email_draft(
    ma_so_hv: str,
    db: Session = Depends(get_db),
    a5: bool = Query(True, description="Luôn A5 (mặc định True)"),
):
    """
    Tạo bản nháp: subject, html, và tạo sẵn file PDF (chưa gửi).
    FE mở modal cho phép chỉnh sửa rồi bấm Send.
    """
    a = db.query(Applicant).filter(Applicant.ma_so_hv == ma_so_hv).first()
    if not a:
        raise HTTPException(status_code=404, detail="Applicant not found")

    to_email = _ensure_to_email(a)
    items, docs = _load_items_docs(db, a)

    pdf_path = pdf_service.save_receipt_pdf_file(
        a=a, items=items, docs=docs, a5=a5, out_dir=settings.RECEIPTS_DIR
    )

    return {
        "to_email": to_email,
        "subject": _default_subject(),
        "html_body": _default_html(a),
        "attachment": pdf_path,
        "a5": a5,
    }
@router.post("/{ma_so_hv}/send-confirmation")
def send_confirmation(
    ma_so_hv: str,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    a5: bool = Query(True),  # <-- mặc định True
    subject: str | None = Body(None),
    html_body: str | None = Body(None),
    attach_receipt: bool = Body(True),
):
    a = db.query(Applicant).filter(Applicant.ma_so_hv == ma_so_hv).first()
    if not a:
        raise HTTPException(status_code=404, detail="Applicant not found")

    to_email = _ensure_to_email(a)
    att_paths: list[str] = []

    if attach_receipt:
        items, docs = _load_items_docs(db, a)
        pdf_path = pdf_service.save_receipt_pdf_file(
            a=a, items=items, docs=docs, a5=a5, out_dir=settings.RECEIPTS_DIR
        )
        att_paths.append(pdf_path)

    _subject = subject or _default_subject()
    _html = html_body or _default_html(a)

    # ✅ TRUYỀN KÈM ma_ho_so để khỏi query lại
    async def _task(ma_so_hv: str, ma_ho_so: str | None, to_email: str, _subject: str, _html: str, att_paths: list[str]):
        session = SessionLocal()
        ok, err = True, None
        try:
            try:
                await send_html_email(
                    subject=_subject,
                    recipients=[to_email],
                    html_body=_html,
                    attachments=att_paths or None,
                )
            except Exception as e:
                ok, err = False, str(e)

            session.add(EmailLog(
                applicant_ma_so_hv=ma_so_hv,
                applicant_ma_ho_so=ma_ho_so,
                to_email=to_email or "",       # ✅ không để None
                subject=_subject,
                success=ok,
                error_message=err,
            ))
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()

    bg.add_task(_task, a.ma_so_hv, a.ma_ho_so, to_email, _subject, _html, att_paths)
    return {"message": "Đã xếp lịch gửi email", "ma_so_hv": a.ma_so_hv, "a5": a5, "attached": bool(att_paths)}

@router.post("/send-confirmation-batch")
def send_confirmation_batch(
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    payload: dict = Body(..., example={"ma_so_hv_list": ["2510000123","2510000456"], "a5": False}),
):
    ids = list(map(str, payload.get("ma_so_hv_list") or []))
    a5 = True 
    if not ids:
        raise HTTPException(status_code=400, detail="ma_so_hv_list is empty")

    async def _task_batch(ids: list[str], a5: bool):
        session = SessionLocal()
        try:
            for mshv in ids:
                a = session.query(Applicant).filter(Applicant.ma_so_hv == mshv).first()
                if not a:
                    session.add(EmailLog(
                        applicant_ma_so_hv=mshv,
                        applicant_ma_ho_so=None,
                        to_email="",                      # ✅ không để None
                        subject=_default_subject(),
                        success=False,
                        error_message="Applicant not found",
                    ))
                    session.commit()
                    continue

                try:
                    to_email = _ensure_to_email(a)
                except HTTPException as e:
                    session.add(EmailLog(
                        applicant_ma_so_hv=mshv,
                        applicant_ma_ho_so=a.ma_ho_so,
                        to_email="",                      # ✅ không để None
                        subject=_default_subject(),
                        success=False,
                        error_message=str(e.detail),
                    ))
                    session.commit()
                    continue

                items, docs = _load_items_docs(session, a)
                pdf_path = pdf_service.save_receipt_pdf_file(
                    a=a, items=items, docs=docs, a5=a5, out_dir=settings.RECEIPTS_DIR
                )

                _subject = _default_subject()
                _html = _default_html(a)

                ok, err = True, None
                try:
                    await send_html_email(
                        subject=_subject,
                        recipients=[to_email],
                        html_body=_html,
                        attachments=[pdf_path],
                    )
                except Exception as e:
                    ok, err = False, str(e)

                session.add(EmailLog(
                    applicant_ma_so_hv=a.ma_so_hv,
                    applicant_ma_ho_so=a.ma_ho_so,
                    to_email=to_email or "",            # ✅ không để None
                    subject=_subject,
                    success=ok,
                    error_message=err,
                ))
                session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise
        finally:
            session.close()

    bg.add_task(_task_batch, ids, a5)
    return {"message": "Đã xếp lịch gửi email hàng loạt.", "count": len(ids)}
