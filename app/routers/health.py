# ================================
# file: app/routers/health.py
# ================================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db
from datetime import timezone, datetime

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True, "time": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"ok": True}
