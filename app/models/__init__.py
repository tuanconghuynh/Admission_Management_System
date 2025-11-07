from app.db.base import Base

from .applicant import Applicant, ApplicantDoc
from .checklist import ChecklistItem, ChecklistVersion
from .user import User
from .user_models import Student, Application
from .email_log import EmailLog  # dùng đường tương đối là gọn hơn

__all__ = [
    "Base",
    "Applicant",
    "ApplicantDoc",
    "ChecklistItem",
    "ChecklistVersion",
    "User",
    "Student",
    "Application",
    "EmailLog",   
]
