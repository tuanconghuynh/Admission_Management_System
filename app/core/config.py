# file: app/core/config.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
import secrets
from pydantic import EmailStr
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    SESSION_SECRET: str = ""
    COOKIE_SECURE: bool = False
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver"
    ALLOWED_ORIGINS: str = ""
    AUTO_CREATE_TABLES: bool = True
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 30
    MAX_REPORT_ROWS: int = 1000
    MAX_EMAIL_BATCH: int = 100
    MAX_REQUEST_BYTES: int = 10 * 1024 * 1024
    LOGIN_RATE_LIMIT: int = 10
    EMAIL_RATE_LIMIT: int = 20
    EMAIL_MAX_ATTEMPTS: int = 3
    PASSWORD_PEPPER: str = ""
    BCRYPT_ROUNDS: int = 12
    # ======== App meta & server ========
    APP_NAME: str = "Admission Management System"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ======== Database ========
    DATABASE_URL: Optional[str] = None
    DB_URL: str = "mysql+pymysql://root:@localhost:3306/Admission_Management_System?charset=utf8mb4"

    # ======== PDF / Font / Templates ========
    FONT_PATH: str = "assets/TimesNewRoman.ttf"
    FONT_PATH_BOLD: str = "assets/TimesNewRoman-Bold.ttf"
    TEMPLATES_DIR: str = "app/templates"
    RECEIPTS_DIR: str = "assets/receipts"
    PDF_ENGINE: str = "xhtml2pdf"  # hoặc "weasyprint"

    # ======== SMTP / Email ========
    EMAIL_ENABLED: bool = True
    EMAIL_LOG_DETAIL: bool = True  # <-- thêm: để service có thể in log chi tiết

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USER: Optional[EmailStr] = None
    SMTP_PASS: Optional[str] = None
    SMTP_FROM: Optional[EmailStr] = None          # sẽ fallback = SMTP_USER nếu None
    SMTP_FROM_NAME: str = "Viện Đại học Mở HUTECH (no-reply)"
    REPLY_TO_EMAIL: Optional[EmailStr] = "no-reply@hutech.edu.vn"

    # Cờ TLS/SSL & timeout (giúp bắt lỗi kết nối rõ ràng)
    SMTP_STARTTLS: bool = False                    # Gmail: True với port 587
    SMTP_SSL_TLS: bool = True                     # Gmail: False (SSL thuần là 465)
    SMTP_TIMEOUT: int = 20                         # giây

    # ======== Security ========
    AUDIT_HMAC_SECRET: Optional[str] = None
    DELETE_KEY_SECRET: Optional[str] = None

    # ======== Pydantic v2 Config ========
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("SMTP_USER", "SMTP_FROM", "REPLY_TO_EMAIL", mode="before")
    @classmethod
    def empty_email(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_environment(self):
        if self.ENVIRONMENT not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test or production")
        if self.ENVIRONMENT == "production":
            for name in ("SESSION_SECRET", "AUDIT_HMAC_SECRET", "DELETE_KEY_SECRET"):
                value = getattr(self, name) or ""
                if len(value) < 32 or value in {"change-me-please", "audit-dev", "delete-dev"}:
                    raise ValueError(f"Production requires a strong {name} (at least 32 characters)")
            if not self.COOKIE_SECURE or self.AUTO_CREATE_TABLES:
                raise ValueError("Production requires COOKIE_SECURE=true and AUTO_CREATE_TABLES=false")
            if "*" in self.ALLOWED_HOSTS or "*" in self.ALLOWED_ORIGINS:
                raise ValueError("Production requires explicit hosts and origins")
            if self.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
                raise ValueError("Production requires MySQL/MariaDB")
        else:
            self.SESSION_SECRET = self.SESSION_SECRET or secrets.token_urlsafe(48)
        for name in ("DB_POOL_SIZE", "DB_POOL_TIMEOUT", "MAX_REPORT_ROWS", "MAX_EMAIL_BATCH", "MAX_REQUEST_BYTES", "LOGIN_RATE_LIMIT", "EMAIL_RATE_LIMIT", "EMAIL_MAX_ATTEMPTS"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.EMAIL_ENABLED and self.SMTP_STARTTLS and self.SMTP_SSL_TLS:
            if self.ENVIRONMENT == "production":
                raise ValueError("Choose either SMTP_STARTTLS or SMTP_SSL_TLS")
            # Preserve legacy development settings, which already preferred SSL.
            self.SMTP_STARTTLS = False
        return self

    # ---------- Helpers ----------
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.DATABASE_URL or self.DB_URL

    @property
    def templates_path(self) -> Path:
        return Path(self.TEMPLATES_DIR).resolve()

    @property
    def receipts_path(self) -> Path:
        return Path(self.RECEIPTS_DIR).resolve()

    @property
    def font_path(self) -> Path:
        return Path(self.FONT_PATH).resolve()

    @property
    def font_path_bold(self) -> Path:
        return Path(self.FONT_PATH_BOLD).resolve()

    @property
    def mail_from_effective(self) -> Optional[EmailStr]:
        """
        Trả về địa chỉ From hiệu lực (fallback SMTP_FROM <- SMTP_USER).
        Dùng trong service khi build ConnectionConfig.
        """
        return self.SMTP_FROM or self.SMTP_USER

    @property
    def mail_from_display(self) -> Optional[str]:
        """
        Chuỗi 'Tên hiển thị <email>' để show UI.
        """
        if self.mail_from_effective:
            return f"{self.SMTP_FROM_NAME} <{self.mail_from_effective}>"
        return None

    @property
    def smtp_ready(self) -> bool:
        """
        Có đủ điều kiện để gửi email hay chưa (dùng cho service để cảnh báo sớm).
        """
        return bool(
            self.EMAIL_ENABLED
            and self.SMTP_HOST
            and self.SMTP_PORT
            and self.SMTP_USER
            and self.SMTP_PASS
            and self.mail_from_effective
        )

# Khởi tạo Settings toàn cục
settings = Settings()
