# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index
)
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.applicant import Applicant  # để relationship gọn

class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Khóa tham chiếu CHUẨN theo schema của anh (VARCHAR[10])
    applicant_ma_so_hv = Column(
        String(10),
        ForeignKey("applicants.ma_so_hv", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )

    # Optional: lưu thêm mã hồ sơ (trống cũng được) để tra cứu mềm
    applicant_ma_ho_so = Column(String(64), nullable=True, index=True)

    to_email = Column(String(255), nullable=False, index=True)
    subject  = Column(String(255), nullable=False)
    success  = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Quan hệ ngược theo ma_so_hv
    applicant = relationship(
        Applicant,
        primaryjoin="EmailLog.applicant_ma_so_hv==Applicant.ma_so_hv",
        viewonly=True,
    )

# Index tổng hợp (tùy chọn)
Index("ix_email_logs_created_email", EmailLog.created_at, EmailLog.to_email)
