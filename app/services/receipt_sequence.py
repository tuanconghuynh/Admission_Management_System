import hashlib
import json
import re
from sqlalchemy import select, func, or_
from fastapi import HTTPException
from app.services.majors import MAJORS, resolve_major
from app.models.applicant import Applicant
from app.models.operations import ReceiptSequence


def next_receipt_number(db, khoa, dot):
    """Reserve a number in the caller's transaction, serialized per scope."""
    khoa, dot = (khoa or "").strip(), (dot or "").strip()
    scope = hashlib.sha256(json.dumps([khoa.casefold(), dot.casefold()], ensure_ascii=False).encode()).hexdigest()
    table = ReceiptSequence.__table__
    if db.bind.dialect.name == "mysql":
        from sqlalchemy.dialects.mysql import insert
        statement = insert(table).values(scope=scope, value=0).on_duplicate_key_update(scope=scope)
    else:
        from sqlalchemy.dialects.sqlite import insert
        statement = insert(table).values(scope=scope, value=0).on_conflict_do_nothing()
    db.execute(statement)
    counter = db.execute(select(ReceiptSequence).where(ReceiptSequence.scope == scope).with_for_update()).scalar_one()
    if counter.value == 0:
        # Seed legacy data once; stream only the code column, never ORM objects.
        for (code,) in db.query(Applicant.ma_ho_so).filter(Applicant.khoa == khoa, Applicant.dot == dot).yield_per(500):
            match = re.search(r"(\d{4})$", code or "")
            if match:
                counter.value = max(counter.value, int(match[1]))
    while True:
        counter.value += 1
        code = f"{counter.value:04d}"
        if not db.query(Applicant.ma_so_hv).filter(Applicant.khoa == khoa, Applicant.dot == dot, Applicant.ma_ho_so == code).first():
            db.flush()
            return code


def _intake_scope(khoa, dot):
    khoa, dot = str(khoa or '').strip(), str(dot or '').strip()
    if not khoa or not dot:
        raise HTTPException(422, 'Cần chọn khóa và đợt để cấp mã hồ sơ')
    if re.fullmatch(r'[0-9]+', dot):
        dot = str(int(dot))
    return khoa, dot


def _format_dot(dot):
    if not re.fullmatch(r'[0-9]+', dot) or int(dot) < 1:
        raise HTTPException(422, 'Đợt cấp mã hồ sơ phải là số nguyên dương')
    return f'{int(dot):02d}'


def _number_pattern(prefix, dot):
    # Older major-STT identifiers remain valid and seed the same counter.
    return re.compile(re.escape(prefix) + r'-(?:' + re.escape(_format_dot(dot)) + r'-)?(\d{4,})$', re.I)


def _scope_query(query, khoa, dot):
    return query.filter(func.lower(func.trim(Applicant.khoa)) == khoa.lower(),
        or_(func.lower(func.trim(Applicant.dot)) == dot.lower(), func.trim(Applicant.dot) == _format_dot(dot)))


def _scope_key(prefix, khoa, dot):
    return hashlib.sha256(json.dumps(['major-intake-receipt-v1', prefix, khoa.casefold(), dot.casefold()], ensure_ascii=False).encode()).hexdigest()


def _major_counter(db, prefix, khoa, dot):
    scope = _scope_key(prefix, khoa, dot)
    table = ReceiptSequence.__table__
    if db.bind.dialect.name == 'mysql':
        from sqlalchemy.dialects.mysql import insert
        statement = insert(table).values(scope=scope, value=0).on_duplicate_key_update(scope=scope)
    else:
        from sqlalchemy.dialects.sqlite import insert
        statement = insert(table).values(scope=scope, value=0).on_conflict_do_nothing()
    db.execute(statement)
    counter = db.execute(select(ReceiptSequence).where(ReceiptSequence.scope == scope).with_for_update()).scalar_one()
    if counter.value == 0:
        pattern = _number_pattern(prefix, dot)
        for (code,) in _scope_query(db.query(Applicant.ma_ho_so), khoa, dot).filter(Applicant.ma_ho_so.ilike(prefix + '-%')).yield_per(500):
            match = pattern.fullmatch(code or '')
            if match:
                counter.value = max(counter.value, int(match[1]))
    return counter


def next_major_receipt(db, major, khoa, dot):
    resolved = resolve_major(major)
    if not resolved:
        raise HTTPException(422, 'Cần chọn ngành trong danh mục để cấp mã hồ sơ')
    prefix = resolved[1]
    khoa, dot = _intake_scope(khoa, dot)
    dot_code = _format_dot(dot)
    counter = _major_counter(db, prefix, khoa, dot)
    while True:
        counter.value += 1
        code = f'{prefix}-{dot_code}-{counter.value:04d}'
        # Include deleted records: issued numbers are never recycled.
        if not _scope_query(db.query(Applicant.ma_so_hv), khoa, dot).filter(Applicant.ma_ho_so == code).first():
            db.flush()
            return code


def reserve_imported_major_receipt(db, code, khoa, dot):
    """Advance the same counter for imported numbered codes, within this transaction."""
    for _, prefix in MAJORS:
        match = re.fullmatch(re.escape(prefix) + r'-(?:(\d+)-)?(\d{4,})', code or '', flags=re.I)
        if match:
            khoa, dot = _intake_scope(khoa, dot)
            if match[1] is not None and _format_dot(match[1]) != _format_dot(dot):
                raise HTTPException(422, 'Đợt trong mã hồ sơ không khớp đợt đã chọn')
            counter = _major_counter(db, prefix, khoa, dot)
            code = f'{prefix}-' + (f'{_format_dot(dot)}-' if match[1] is not None else '') + f'{int(match[2]):04d}'
            if _scope_query(db.query(Applicant.ma_so_hv), khoa, dot).filter(Applicant.ma_ho_so == code).first():
                raise HTTPException(409, 'Mã hồ sơ theo ngành đã tồn tại')
            counter.value = max(counter.value, int(match[2]))
            db.flush()
            return code
    return code


def preview_major_receipt(db, major, khoa, dot):
    resolved = resolve_major(major)
    if not resolved:
        raise HTTPException(422, 'Cần chọn ngành trong danh mục để cấp mã hồ sơ')
    khoa, dot = _intake_scope(khoa, dot)
    prefix = resolved[1]
    value = db.query(ReceiptSequence.value).filter_by(scope=_scope_key(prefix, khoa, dot)).scalar() or 0
    pattern = _number_pattern(prefix, dot)
    for (code,) in _scope_query(db.query(Applicant.ma_ho_so), khoa, dot).filter(Applicant.ma_ho_so.ilike(prefix + '-%')).yield_per(500):
        match = pattern.fullmatch(code or '')
        if match:
            value = max(value, int(match[1]))
    return f'{prefix}-{_format_dot(dot)}-{value + 1:04d}'
