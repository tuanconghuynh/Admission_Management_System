from pathlib import Path
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.applicant import Applicant
from app.models.audit import AuditLog
from app.routers.auth import require_roles
from app.services.audit import write_audit
from app.services.print_confirmation import read_print_token

staff = require_roles('Admin', 'NhanVien', 'CongTacVien', 'Manager')
router = APIRouter(dependencies=[Depends(staff)])


@router.get('/print-preview', response_class=HTMLResponse)
def preview():
    return HTMLResponse((Path(__file__).resolve().parents[1] / 'templates/web/print_preview.html').read_text(encoding='utf-8'))


class ConfirmPrint(BaseModel):
    token: str = Field(min_length=20, max_length=50000)


@router.post('/print-confirm')
def confirm(payload: ConfirmPrint, request: Request, db: Session = Depends(get_db), user=Depends(staff)):
    data = read_print_token(payload.token, user.id)
    # Serialize confirmations by actor so retries cannot create duplicate logs.
    db.query(User).filter(User.id == user.id).with_for_update().one()
    if db.query(AuditLog.id).filter(AuditLog.target_type == 'PrintJob', AuditLog.target_id == data['nonce']).with_for_update().first():
        return {'ok': True, 'already_confirmed': True}
    apps = db.query(Applicant).filter(Applicant.ma_so_hv.in_(data['ids'])).order_by(Applicant.ma_so_hv).with_for_update().all()
    if len(apps) != len(data['ids']) or any(a.deleted_at or a.status == 'deleted' for a in apps):
        raise HTTPException(409, 'Có hồ sơ đã bị xóa. Hãy mở lại bản in.')
    for applicant in apps:
        applicant.printed = True
        if applicant.status in {None, 'saved', 'draft'}:
            applicant.status = 'printed'
    write_audit(db, action='PRINT', target_type='PrintJob', target_id=data['nonce'],
        new_values={'confirmed_by_user': True, 'paper': data['paper'], 'name_mode': data['paper'],
            'scope': 'SINGLE' if len(apps) == 1 else 'MULTIPLE', 'count': len(apps), 'mshv': data['ids']}, request=request)
    db.commit()
    return {'ok': True, 'count': len(apps)}
