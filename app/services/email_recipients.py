from fastapi import HTTPException


def recipients(applicant, choice="email1"):
    if choice not in {"email1", "email2", "both"}:
        raise HTTPException(422, "Chọn Email 1, Email 2 hoặc cả hai")
    first = getattr(applicant, "email_hoc_vien", None)
    second = getattr(applicant, "email_hoc_vien_2", None)
    values = [first] if choice == "email1" else [second] if choice == "email2" else [first, second]
    result = []
    for value in values:
        value = (value or "").strip()
        if value and value.casefold() not in {v.casefold() for v in result}:
            result.append(value)
    if not result:
        raise HTTPException(422, "Học viên chưa có địa chỉ email đã chọn")
    return result
