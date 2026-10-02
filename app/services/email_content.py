from datetime import datetime
from typing import List, Dict, Any
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.applicant import Applicant, ApplicantDoc
from app.models.checklist import ChecklistItem
import json

# ---------- Helper ----------
def _load_items_docs(db: Session, a: Applicant):
    """
    Trả về: (items_checklist, docs_ctx_list)
    docs_ctx_list: list[{'code','name','received','so_luong','received_at','note'}]
    """
    items = []
    if getattr(a, "checklist_version_id", None):
        items = (
            db.query(ChecklistItem)
            .filter(ChecklistItem.version_id == a.checklist_version_id)
            .order_by(ChecklistItem.id.asc())
            .all()
        )

    # Ưu tiên bảng ApplicantDoc
    docs_db = (
        db.query(ApplicantDoc)
        .filter(ApplicantDoc.applicant_ma_so_hv == a.ma_so_hv)
        .all()
    )
    if docs_db:
        docs_ctx = []
        for x in docs_db:
            qty = getattr(x, "so_luong", 0) or 0
            try:
                qty = int(qty)
            except Exception:
                qty = 0
            docs_ctx.append({
                "code": getattr(x, "code", None),
                "name": getattr(x, "name", None) or getattr(x, "code", None),
                "so_luong": qty,
                "received": qty > 0 if getattr(x, "received", None) is None else bool(getattr(x, "received")),
                "received_at": getattr(x, "received_at", None),
                "note": getattr(x, "note", None),
            })
        return items, docs_ctx

    # Rơi về JSON
    return items, build_docs_from_json(a)

def _ensure_to_email(a: Applicant) -> str:
    to_email = getattr(a, "email_hoc_vien", None) or getattr(a, "email", None)
    if not to_email:
        raise HTTPException(status_code=400, detail="Applicant has no email")
    return to_email

def build_docs_from_json(ap: "Applicant") -> List[Dict[str, Any]]:
    raw = getattr(ap, "docs_json", None)
    if not raw:
        return []
    import json
    docs = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    out: List[Dict[str, Any]] = []
    for d in docs:
        qty = d.get("so_luong")
        if qty is None:
            # nếu không có so_luong: đã nhận -> 1, chưa nhận -> 0
            qty = 1 if d.get("received") else 0
        try:
            qty = int(qty)
        except Exception:
            qty = 0
        out.append({
            "code": d.get("code"),
            "name": d.get("name") or d.get("code"),
            "so_luong": qty,
            "received": bool(d.get("received")) if d.get("received") is not None else (qty > 0),
            "received_at": d.get("received_at"),
            "note": d.get("note"),
        })
    return out

def _normalize_docs_for_pdf(docs):
    """
    Trả về list object có thuộc tính .code, .so_luong (int)
    docs có thể là list[ApplicantDoc ORM] hoặc list[dict] từ JSON
    """
    out = []
    for d in docs or []:
        if isinstance(d, dict):
            code = d.get("code") or d.get("name") or ""
            qty  = d.get("so_luong")
            if qty is None:
                # nếu không có so_luong trong JSON, suy luận: nhận rồi -> 1, chưa nhận -> 0
                qty = 1 if d.get("received") else 0
            try:
                qty = int(qty)
            except Exception:
                qty = 0
            out.append(SimpleNamespace(code=code, so_luong=qty))
        else:
            # ORM ApplicantDoc: ưu tiên .code; fallback các tên cột khác nếu có
            code = getattr(d, "code", None) or getattr(d, "ten_giay_to", "") or ""
            qty  = getattr(d, "so_luong", 0) or 0
            try:
                qty = int(qty)
            except Exception:
                qty = 0
            out.append(SimpleNamespace(code=code, so_luong=qty))
    return out

# ====== NEW: merge items + docs for email view ======
def _merge_items_with_docs_for_email(items, docs_ctx):
    """
    Trả về list dict cho email:
    [{'code','name','so_luong','received'}]
    - 'name' ưu tiên từ checklist; nếu không có => tra bảng map; cuối cùng mới dùng code.
    """

    # Fallback map cho các mã phổ biến
    VN_LABELS = {
        "so_yeu_ly_lich": "Sơ yếu lý lịch",
        "bang_tot_nghiep_thpt": "Bằng tốt nghiệp THPT (hoặc tương đương)",
        "hoc_ba_thpt": "Học bạ THPT (hoặc Bảng điểm THPT)",
        "bang_tot_nghiep_dai_hoc": "Bằng tốt nghiệp Đại học",
        "bang_diem_dai_hoc": "Bảng điểm toàn khoá học Đại học",
        "bang_tot_nghiep_cao_dang": "Bằng tốt nghiệp Cao đẳng",
        "bang_diem_cao_dang": "Bảng điểm toàn khóa học Cao đẳng",
        "bang_tot_nghiep_trung_cap": "Bằng tốt nghiệp Trung Cấp",
        "bang_diem_trung_cap": "Bảng điểm toàn khóa Trung Cấp",
        "can_cuoc_cong_dan": "Căn cước công dân",
        "anh_3x4": "Ảnh 3x4",
        "giay_kham_suc_khoe": "Giấy Khám sức khỏe",
        "don_mien_giam": "Đơn miễn giảm",
    }

    def keyify(v: str) -> str:
        return (v or "").strip().lower()

    def pretty_name_from_item(it) -> str:
        # thử hết các khả năng có thể tồn tại trong ChecklistItem
        for attr in (
            "display_name", "label", "vi_name", "vi_label",
            "ten_giay_to", "ten", "title", "name",
        ):
            val = getattr(it, attr, None)
            if val:
                return str(val)
        code = getattr(it, "code", None) or getattr(it, "ma", None) or ""
        # tra mapping code -> tên đẹp
        return VN_LABELS.get(keyify(code), code)

    # Map docs by code (lowercase)
    doc_by_code = { keyify(d.get("code") or d.get("name")): d for d in (docs_ctx or []) }

    merged = []
    for it in (items or []):
        code = getattr(it, "code", None) or getattr(it, "ma", None) or ""
        name = pretty_name_from_item(it)
        d = doc_by_code.get(keyify(code)) or {}
        qty = d.get("so_luong", 0) if isinstance(d, dict) else 0
        try:
            qty = int(qty)
        except Exception:
            qty = 0
        merged.append({
            "code": code,
            "name": name,          # ← luôn là tên đẹp
            "so_luong": qty,
            "received": (qty > 0),
        })

    # Thêm mục phát sinh ngoài checklist (nếu có)
    for d in (docs_ctx or []):
        k = keyify(d.get("code") or d.get("name"))
        if not any(keyify(x["code"]) == k for x in merged):
            qty = d.get("so_luong", 0)
            try:
                qty = int(qty)
            except Exception:
                qty = 0
            merged.append({
                "code": d.get("code") or d.get("name") or "",
                "name": d.get("name") or VN_LABELS.get(k, d.get("code") or ""),
                "so_luong": qty,
                "received": (qty > 0),
            })

    return merged
