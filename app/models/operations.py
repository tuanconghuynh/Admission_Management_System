from datetime import timezone, datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index
from sqlalchemy.dialects.mysql import DATETIME
from app.db.base import Base
precise_datetime = DateTime().with_variant(DATETIME(fsp=6), "mysql")


class RateWindow(Base):
    __tablename__ = "rate_windows"
    key = Column(String(64), primary_key=True)
    window = Column(Integer, nullable=False)
    count = Column(Integer, nullable=False, default=0)


class ReceiptSequence(Base):
    __tablename__ = "receipt_sequences"
    scope = Column(String(64), primary_key=True)
    value = Column(Integer, nullable=False, default=0)


class EmailJob(Base):
    __tablename__ = "email_jobs"
    id = Column(String(36), primary_key=True)
    applicant_ma_so_hv = Column(String(10), nullable=False)
    dedup_key = Column(String(64), nullable=False, unique=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    html_body = Column(Text, nullable=False)
    attachments = Column(JSON, nullable=False, default=list)
    actor = Column(JSON, nullable=False, default=dict)
    state = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(precise_datetime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    locked_until = Column(precise_datetime, nullable=True)
    lease_token = Column(String(36), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(precise_datetime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at = Column(precise_datetime, nullable=True)
    __table_args__ = (Index("ix_email_jobs_due", "state", "available_at"),
        Index("ix_email_jobs_lease", "state", "locked_until"))
