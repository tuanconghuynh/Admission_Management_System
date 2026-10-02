import hashlib
import time
from fastapi import HTTPException, Request
from sqlalchemy import case
from app.db.session import SessionLocal
from app.models.operations import RateWindow
from app.core.config import settings


def consume_rate(namespace: str, identity: str, limit: int, seconds: int = 60):
    key = hashlib.sha256(f"{namespace}:{identity}".encode()).hexdigest()
    window = int(time.time()) // seconds
    table = RateWindow.__table__
    with SessionLocal.begin() as db:
        dialect = db.bind.dialect.name
        if dialect == "mysql":
            from sqlalchemy.dialects.mysql import insert
            statement = insert(table).values(key=key, window=window, count=1)
            statement = statement.on_duplicate_key_update(
                count=case((table.c.window == window, table.c.count + 1), else_=1), window=window)
        else:
            from sqlalchemy.dialects.sqlite import insert
            statement = insert(table).values(key=key, window=window, count=1).on_conflict_do_update(
                index_elements=[table.c.key], set_={"count": case((table.c.window == window, table.c.count + 1), else_=1), "window": window})
        db.execute(statement)
        count = db.query(RateWindow.count).filter_by(key=key).scalar()
    if count > limit:
        raise HTTPException(429, "Too many requests; try again later", headers={"Retry-After": str(seconds)})


def limit_login(request: Request):
    consume_rate("login", request.client.host if request.client else "unknown", settings.LOGIN_RATE_LIMIT)


def limit_email(request: Request):
    consume_rate("email", str(request.session.get("uid", "unknown")), settings.EMAIL_RATE_LIMIT)
