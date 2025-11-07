# file: app/services/sendmail_service.py
from __future__ import annotations
from typing import List, Optional
import mimetypes
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from email.message import EmailMessage
from email.utils import formataddr
import aiosmtplib

from app.core.config import settings

# ---- Jinja (để render template HTML) ----
_env = Environment(
    loader=FileSystemLoader(str(settings.templates_path)),
    autoescape=select_autoescape(["html", "xml"]),
)

def render_email(template_relpath: str, context: dict) -> str:
    tpl = _env.get_template(template_relpath)
    return tpl.render(**context)

# ---- SMTP flags (tương thích cấu hình cũ) ----
SMTP_STARTTLS: bool = bool(getattr(settings, "SMTP_STARTTLS", True))
SMTP_SSL_TLS:  bool = bool(getattr(settings, "SMTP_SSL_TLS", False))
SMTP_TIMEOUT:  int  = int(getattr(settings, "SMTP_TIMEOUT", 20))

def _fmt_from() -> str:
    display = settings.SMTP_FROM_NAME or ""
    email   = settings.SMTP_FROM or settings.SMTP_USER
    return formataddr((display, str(email)))

async def send_html_email(
    subject: str,
    recipients: List[str],
    html_body: str,
    attachments: Optional[List[str]] = None,
) -> None:
    """
    Gửi email HTML + file đính kèm bằng aiosmtplib.
    (Không nhúng logo CID; nếu cần logo thì đã để sẵn trong template/ngoài hệ thống.)
    """
    if not settings.EMAIL_ENABLED:
        return

    # ---- Tạo message (multipart/mixed) ----
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _fmt_from()
    msg["To"] = ", ".join([str(x) for x in recipients if x])
    if getattr(settings, "REPLY_TO_EMAIL", None):
        msg["Reply-To"] = str(settings.REPLY_TO_EMAIL)

    # Text fallback
    msg.set_content("Vui lòng xem email ở chế độ HTML để hiển thị đầy đủ nội dung.")

    # HTML body (không dùng multipart/related, không CID)
    msg.add_alternative(html_body or "", subtype="html")

    # ---- Đính kèm file (PDF biên nhận, v.v.) ----
    for p in attachments or []:
        path = Path(str(p))
        if not path.exists():
            print(f"[EMAIL] ⚠️ File đính kèm không tồn tại: {p}")
            continue
        ctype, _ = mimetypes.guess_type(str(path))
        if not ctype:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        with open(path, "rb") as f:
            data = f.read()
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)

    # ---- Gửi qua SMTP ----
    print(f"[EMAIL] ▶ Gửi tới {recipients} | attach: {[str(a) for a in (attachments or [])]}")
    try:
        await aiosmtplib.send(
            msg,
            hostname=str(settings.SMTP_HOST),
            port=int(settings.SMTP_PORT),
            username=str(settings.SMTP_USER),
            password=str(settings.SMTP_PASS),
            start_tls=bool(SMTP_STARTTLS) if not SMTP_SSL_TLS else False,
            use_tls=bool(SMTP_SSL_TLS),
            timeout=SMTP_TIMEOUT,
        )
        print("[EMAIL] ✅ Đã gửi xong.")
    except Exception as e:
        print(f"[EMAIL] ❌ Lỗi gửi SMTP: {e}")
        # Tuỳ anh có muốn raise hay không; giữ nguyên hành vi hiện tại là không raise.
