# app/services/audit.py
from __future__ import annotations

import os
import json
import hmac
import hashlib
from typing import Optional, Any, Dict

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog

# Bí mật ký HMAC cho audit (đặt biến môi trường ở production)
AUDIT_HMAC_SECRET = os.getenv("AUDIT_HMAC_SECRET", "audit-dev")

# Giới hạn dung lượng JSON lưu trong cột JSON (bytes sau khi dumps)
AUDIT_JSON_MAX_BYTES = int(os.getenv("AUDIT_JSON_MAX_BYTES", "200000"))  # ~200 KB

# Các khóa cần ẩn giá trị khi log
REDACT_KEYS = {
    "password",
    "password_hash",
    "reset_password_hash",
    "new_password",
    "old_password",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "secret",
    "client_secret",
    "api_key",
    "key",
    "otp",
    "pin",
    "credential",
}

REDACT_REPLACEMENT = "***REDACTED***"


def _redact_in_obj(val: Any) -> Any:
    """
    Ẩn thông tin nhạy cảm trong dict/list lồng nhau.
    Không phá cấu trúc, chỉ thay thế value bằng chuỗi REDACTED.
    """
    try:
        if isinstance(val, dict):
            out = {}
            for k, v in val.items():
                if str(k).lower() in REDACT_KEYS:
                    out[k] = REDACT_REPLACEMENT
                else:
                    out[k] = _redact_in_obj(v)
            return out
        if isinstance(val, list):
            return [_redact_in_obj(v) for v in val]
        # kiểu cơ bản giữ nguyên
        return val
    except Exception:
        # Nếu có lỗi trong quá trình redact, fallback an toàn
        return {"_raw": str(val)}


def _norm_json(val: Any) -> Dict[str, Any]:
    """
    Chuẩn hoá prev_values/new_values thành dict để lưu JSON.
    - Nếu là None -> {}
    - Nếu là dict -> redact rồi giữ nguyên
    - Nếu là chuỗi JSON -> parse -> redact
    - Còn lại -> bọc vào {"_raw": ...}
    """
    if val is None:
        return {}
    if isinstance(val, dict):
        return _redact_in_obj(val)  # redact ngay tại đây
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return _redact_in_obj(parsed)
            return {"_raw": parsed}
        except Exception:
            return {"_raw": val}
    return {"_raw": val}


def _compact_json_size(d: Dict[str, Any], max_bytes: int) -> Dict[str, Any]:
    """
    Cố gắng đảm bảo json.dumps(d) không vượt quá max_bytes.
    Chiến lược:
      - Thử dumps; nếu vượt -> cắt ngắn các chuỗi dài trong dict (đệ quy).
      - Nếu vẫn vượt -> thêm cờ "_truncated": true và loại bớt một số trường ít quan trọng.
    Lưu ý: Chỉ áp dụng cắt giảm nhẹ để tránh mất dữ liệu chính.
    """
    def dumps(x) -> bytes:
        return json.dumps(x, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    if len(dumps(d)) <= max_bytes:
        return d

    # Hàm cắt chuỗi dài
    def truncate_val(v: Any) -> Any:
        if isinstance(v, str):
            if len(v) > 2048:
                return v[:2048] + "...(truncated)"
            return v
        if isinstance(v, list):
            # Rút gọn list quá dài
            if len(v) > 200:
                head = v[:100]
                tail = v[-50:]
                return [_compact_walk(x) for x in head] + ["...(truncated list)..."] + [_compact_walk(x) for x in tail]
            return [_compact_walk(x) for x in v]
        if isinstance(v, dict):
            return {k: _compact_walk(vv) for k, vv in v.items()}
        return v

    def _compact_walk(obj: Any) -> Any:
        try:
            return truncate_val(obj)
        except Exception:
            return str(obj)

    compacted = _compact_walk(d)
    if len(dumps(compacted)) <= max_bytes:
        return compacted

    # Nếu vẫn vượt -> loại bớt một số trường dễ “phình to”
    def drop_heavy_fields(obj: Any) -> Any:
        if isinstance(obj, dict):
            out = dict(obj)
            for k in list(out.keys()):
                lname = str(k).lower()
                if lname in {"_raw", "stack", "trace", "stacktrace", "html", "content", "body"}:
                    out[k] = "...(dropped)"
            return out
        if isinstance(obj, list):
            return obj[:100] + ["...(truncated)..."] if len(obj) > 100 else obj
        return obj

    final = drop_heavy_fields(compacted)
    if len(dumps(final)) <= max_bytes:
        final["_truncated"] = True
        return final

    # Phòng xa: nếu vẫn quá lớn thì chỉ giữ bộ khung rất gọn
    return {
        "_note": "payload too large; truncated to fit",
        "_truncated": True,
    }


def _build_hmac_hash(
    *,
    action: str,
    status: Optional[str],
    target_type: Optional[str],
    target_id: Optional[str],
    correlation_id: Optional[str],
    prev_values: Dict[str, Any],
    new_values: Dict[str, Any],
) -> str:
    """
    Tạo chữ ký HMAC-SHA256 trên payload audit (đã chuẩn hoá).
    """
    payload = {
        "action": action or "",
        "status": status or "",
        "target_type": target_type or "",
        "target_id": str(target_id or ""),
        "correlation_id": correlation_id or "",
        "prev_values": prev_values,
        "new_values": new_values,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(AUDIT_HMAC_SECRET.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def write_audit(
    db: Session,
    *,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    status: str = "SUCCESS",
    prev_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """
    Ghi 1 dòng audit. Không commit ở đây (để caller chủ động).
    Bắt buộc set được hmac_hash để phù hợp DB NOT NULL.
    """
    # Lấy actor từ session (nếu có)
    actor_id = None
    actor_name = None
    if request is not None:
        try:
            sess = getattr(request, "session", {}) or {}
            actor_id = sess.get("uid") or sess.get("user_id") or sess.get("id")
            actor_name = (
                sess.get("full_name")
                or sess.get("username")
                or sess.get("email")
                or str(actor_id or "")
            ) or None
            # Cho phép request.state.override_name nếu middleware có set
            state_name = getattr(getattr(request, "state", None), "actor_name", None)
            if state_name and not actor_name:
                actor_name = str(state_name)
        except Exception:
            pass

    ip = request.client.host if (request and request.client) else None
    path = request.url.path if request else None
    cid = getattr(request.state, "correlation_id", None) if request else None
    if not cid:
        # Không tự generate UUID để tránh lệch với middleware tracing,
        # chỉ để rỗng nếu upstream chưa set.
        cid = None

    # Chuẩn hoá + redact JSON cho cột JSON của DB
    prev_j = _norm_json(prev_values)
    new_j = _norm_json(new_values)

    # Giới hạn kích thước để tránh lỗi DB (payload quá lớn)
    prev_j = _compact_json_size(prev_j, AUDIT_JSON_MAX_BYTES)
    new_j = _compact_json_size(new_j, AUDIT_JSON_MAX_BYTES)

    # Tính chữ ký hmac
    h = _build_hmac_hash(
        action=action,
        status=status,
        target_type=target_type,
        target_id=target_id,
        correlation_id=cid,
        prev_values=prev_j,
        new_values=new_j,
    )

    row = AuditLog(
        action=action,
        status=status,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        prev_values=prev_j,
        new_values=new_j,
        actor_id=str(actor_id) if actor_id is not None else None,
        actor_name=str(actor_name) if actor_name is not None else None,
        ip_address=ip,
        path=path,
        correlation_id=cid,
        hmac_hash=h,  # 👈 quan trọng: set giá trị NOT NULL
    )
    db.add(row)
    return row
