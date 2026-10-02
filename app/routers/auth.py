# app/routers/auth.py
import time
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_password, hash_password, try_rehash_on_success
from app.services.rate_limit import limit_login

router = APIRouter()

# Idle timeout: 1 giờ (đồng bộ với main.py)
IDLE_TIMEOUT_SEC = 1 * 60 * 60

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    sess = request.session
    now = int(time.time())
    last = int(sess.get("_last_seen") or 0)
    if last and (now - last) > IDLE_TIMEOUT_SEC:
        sess.clear()
        return None
    # cập nhật mốc hoạt động cuối
    sess["_last_seen"] = now

    uid = sess.get("uid")
    if not uid:
        return None
    user = db.get(User, uid)
    if user and sess.get("session_version", 0) != user.session_version:
        sess.clear()
        return None
    return user

def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại!")
    if not user.is_active:
        raise HTTPException(HTTP_403_FORBIDDEN, "User disabled")
    return user

def require_roles(*roles: str):
    def _dep(
        request: Request,
        user: User = Depends(require_user)
    ) -> User:
        # Kiểm tra nếu user có vai trò là Admin hoặc Manager
        if roles and user.role not in roles:
            raise HTTPException(HTTP_403_FORBIDDEN, "Forbidden")
        if user.must_change_password and request.url.path not in {"/account", "/account/change-password", "/api/account/change-password"}:
            raise HTTPException(HTTP_403_FORBIDDEN, "Vui lòng đổi mật khẩu trước khi tiếp tục.")

        # Bơm đầy đủ thông tin vào session cho chắc
        s = request.session
        s["uid"] = getattr(user, "id", s.get("uid"))
        s["full_name"] = (
            getattr(user, "full_name", None)
            or getattr(user, "username", None)
            or getattr(user, "email", None)
            or s.get("full_name")
        )
        s["username"] = getattr(user, "username", s.get("username"))
        s["email"]    = getattr(user, "email", s.get("email"))
        s["role"]     = getattr(user, "role", s.get("role"))
        s["must_change_password"] = bool(getattr(user, "must_change_password", False))
        return user
    return _dep

require_admin = require_roles("Admin")

@router.get("/login")
def login_page():
    # Trang HTML login tĩnh
    return RedirectResponse(url="/auth_login.html", status_code=302)

@router.post("/api/login", dependencies=[Depends(limit_login)])
@router.post("/login", dependencies=[Depends(limit_login)])
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(or_(User.username == username, User.email == username))
        .first()
    )
    # Xác thực
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(HTTP_403_FORBIDDEN, "User disabled")

    # Nâng cấp hash nếu cần (đổi cost/scheme)
    try:
        new_hash = try_rehash_on_success(password, user.password_hash)
        if new_hash:
            user.password_hash = new_hash
    except Exception:
        # không chặn đăng nhập nếu rehash lỗi
        pass

    # Ghi nhận thời điểm đăng nhập
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Lưu phiên + thông tin để audit dùng ngay
    request.session.clear()
    request.session["uid"] = user.id
    request.session["session_version"] = user.session_version
    request.session["_last_seen"] = int(time.time())
    request.session["full_name"] = user.full_name or user.username or user.email
    request.session["username"]  = user.username
    request.session["email"]     = user.email
    request.session["role"]      = user.role
    request.session["must_change_password"] = bool(getattr(user, "must_change_password", False))

    # Nếu lần đầu/đã reset → yêu cầu đổi mật khẩu
    must_change = bool(getattr(user, "must_change_password", False))
    is_api = request.url.path.startswith("/api")

    if must_change:
        if is_api:
            return {
                "ok": True,
                "require_change_password": True,
                "redirect": "/account?first=1",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "role": user.role,
                    "is_active": user.is_active,
                },
            }
        # form login HTML → chuyển hướng thẳng
        return RedirectResponse(url="/account?first=1", status_code=302)

    # Đăng nhập bình thường
    if is_api:
        return {
            "ok": True,
            "require_change_password": False,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
            },
        }
    return RedirectResponse(url="/ams_home.html", status_code=302)

@router.post("/logout")
@router.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    # Redirect đến trang login với thông báo "expired=1"
    return RedirectResponse(url="/login?expired=1", status_code=302)

@router.get("/me")
@router.get("/api/me")
def me(user: User = Depends(require_user)):
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "must_change_password": bool(getattr(user, "must_change_password", False)),
        "last_login_at": user.last_login_at,
        "password_changed_at": getattr(user, "password_changed_at", None),
    }

@router.post("/api/init-admin")
def init_admin(db: Session = Depends(get_db)):
    raise HTTPException(404, "Use python -m scripts.create_admin on the server")
