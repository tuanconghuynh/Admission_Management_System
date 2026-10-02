from fastapi import HTTPException
from app.core.config import settings
from sqlalchemy.orm import raiseload
from app.models.applicant import Applicant


def report_rows(query):
    rows = query.options(raiseload(Applicant.docs)).limit(settings.MAX_REPORT_ROWS + 1).all()
    if len(rows) > settings.MAX_REPORT_ROWS:
        raise HTTPException(422, f"Báo cáo vượt {settings.MAX_REPORT_ROWS} hồ sơ. Vui lòng chia nhỏ phạm vi.")
    return rows
