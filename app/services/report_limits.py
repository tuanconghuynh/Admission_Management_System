from fastapi import HTTPException
from app.core.config import settings
from sqlalchemy.orm import raiseload
from app.models.applicant import Applicant


def report_rows(query, *, excel=False):
    limit = min(settings.MAX_EXCEL_ROWS, 1048575) if excel else settings.MAX_REPORT_ROWS
    rows = query.options(raiseload(Applicant.docs)).limit(limit + 1).all()
    if len(rows) > limit:
        raise HTTPException(422, f"Báo cáo vượt {limit} hồ sơ. Vui lòng chia nhỏ phạm vi.")
    return rows
