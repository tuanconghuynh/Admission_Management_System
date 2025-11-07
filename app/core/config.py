# file: app/core/config.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
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
    SMTP_PORT: int = 587
    SMTP_USER: Optional[EmailStr] = None
    SMTP_PASS: Optional[str] = None
    SMTP_FROM: Optional[EmailStr] = None          # sẽ fallback = SMTP_USER nếu None
    SMTP_FROM_NAME: str = "Viện Hợp tác và Phát triển Đào tạo (no-reply)"
    REPLY_TO_EMAIL: Optional[EmailStr] = "no-reply@hutech.edu.vn"

    # Cờ TLS/SSL & timeout (giúp bắt lỗi kết nối rõ ràng)
    SMTP_STARTTLS: bool = True                     # Gmail: True với port 587
    SMTP_SSL_TLS: bool = False                     # Gmail: False (SSL thuần là 465)
    SMTP_TIMEOUT: int = 20                         # giây

    # ======== Security ========
    AUDIT_HMAC_SECRET: Optional[str] = None
    DELETE_KEY_SECRET: Optional[str] = None

    # ======== Pydantic v2 Config ========
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
