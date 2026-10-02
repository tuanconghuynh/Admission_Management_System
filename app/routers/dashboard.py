from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.applicant import Applicant
from app.routers.auth import require_roles
from app.utils.soft_delete import exclude_deleted

router = APIRouter(dependencies=[Depends(require_roles("Admin", "NhanVien", "CongTacVien", "Manager"))])


@router.get('/applicants/majors')
def major_catalog():
    from app.services.majors import MAJORS
    return {'items': [{'name': name, 'code': code} for name, code in MAJORS],
        'receipt_format': 'MA_NGANH-DOT-0001', 'sequence_scope': 'major_khoa_dot'}


@router.get('/applicants/receipt-code-preview')
def receipt_code_preview(major: str, khoa: str, dot: str, db: Session = Depends(get_db)):
    from app.services.receipt_sequence import preview_major_receipt
    return {'ma_ho_so': preview_major_receipt(db, major, khoa, dot), 'reserved': False}


@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    query = db.query(Applicant.khoa, Applicant.dot, Applicant.nganh_nhap_hoc,
        func.count(Applicant.ma_so_hv), func.sum(case((Applicant.ma_ho_so.is_not(None), 1), else_=0)))
    rows = exclude_deleted(Applicant, query).group_by(Applicant.khoa, Applicant.dot, Applicant.nganh_nhap_hoc).all()
    return {"groups": [{"khoa": khoa, "dot": dot, "nganh_nhap_hoc": major or "", "total": total,
        "done": int(done or 0)} for khoa, dot, major, total, done in rows]}


@router.get("/applicants/filter-options")
def filter_options(db: Session = Depends(get_db)):
    rows = exclude_deleted(Applicant, db.query(Applicant.khoa, Applicant.dot)).distinct().all()
    return {"items": [{"khoa": khoa, "dot": dot} for khoa, dot in rows]}
