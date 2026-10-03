from fastapi import HTTPException
from pydantic import TypeAdapter, EmailStr, ValidationError
from app.models.applicant import Applicant


def validate_applicant_payload(payload):
    for column in Applicant.__table__.columns:
        name = column.name
        if name not in payload or payload[name] is None:
            continue
        length = getattr(column.type, "length", None)
        if length and (not isinstance(payload[name], str) or len(payload[name]) > length):
            raise HTTPException(422, f"{name} phải là chuỗi tối đa {length} ký tự")
    for name in ("email_hoc_vien", "email_hoc_vien_2"):
        if name in payload:
            value = payload[name]
            try:
                payload[name] = TypeAdapter(EmailStr).validate_python(value) if value else None
            except ValidationError:
                raise HTTPException(422, f"{name}: Email học viên không hợp lệ")
    docs = payload.get("docs")
    if docs is not None:
        if not isinstance(docs, list) or len(docs) > 100:
            raise HTTPException(422, "Danh sách giấy tờ tối đa 100 mục")
        for item in docs:
            if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not 1 <= len(item["code"]) <= 64:
                raise HTTPException(422, "Mã giấy tờ không hợp lệ")
            value = item.get("so_luong")
            if value in (None, ""):
                continue
            try:
                number = int(value)
            except (ValueError, TypeError):
                raise HTTPException(422, "Số lượng giấy tờ không hợp lệ")
            if isinstance(value, bool) or str(number) != str(value).strip() or not 0 <= number <= 1000:
                raise HTTPException(422, "Số lượng giấy tờ phải là số nguyên 0–1000")
            item["so_luong"] = number
