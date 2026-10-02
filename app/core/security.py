# app/core/security.py
import os
from app.core.config import settings
from typing import Optional
from passlib.context import CryptContext

# cấu hình rounds có thể chỉnh qua ENV
BCRYPT_ROUNDS = settings.BCRYPT_ROUNDS
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)

# Pepper bí mật (tùy chọn). Nếu không dùng thì để rỗng cũng ok.
_PEPPER = settings.PASSWORD_PEPPER

def _with_pepper(plain: str) -> str:
    return f"{plain}{_PEPPER}"

def hash_password(password: str) -> str:
    if len(_with_pepper(password).encode("utf-8")) > 72:
        raise ValueError("Password exceeds bcrypt's 72-byte limit")
    return _pwd.hash(_with_pepper(password))

def verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if len(_with_pepper(plain_password).encode("utf-8")) > 72:
        return False
    try:
        return _pwd.verify(_with_pepper(plain_password), password_hash)
    except Exception:
        return False

def needs_rehash(password_hash: str) -> bool:
    try:
        return _pwd.needs_update(password_hash)
    except Exception:
        return False

def try_rehash_on_success(plain_password: str, password_hash: str) -> Optional[str]:
    """
    Nếu verify OK và policy hash đã đổi (ví dụ tăng rounds) → trả về hash mới để lưu DB.
    Nếu không cần nâng cấp → trả về None.
    """
    if not verify_password(plain_password, password_hash):
        return None
    if needs_rehash(password_hash):
        return hash_password(plain_password)
    return None
