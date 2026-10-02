import os
import tempfile
import uuid
from pathlib import Path

# Never load or modify the operational database when executing tests.
TEST_DATABASE = Path(tempfile.gettempdir()) / f"ams-tests-{uuid.uuid4().hex}.sqlite3"
os.environ.update(ENVIRONMENT="test", DATABASE_URL=f"sqlite:///{TEST_DATABASE.as_posix()}",
    SESSION_SECRET="test-only-session-secret-with-at-least-32-characters", EMAIL_ENABLED="false",
    COOKIE_SECURE="false", AUTO_CREATE_TABLES="true", ALLOWED_HOSTS="testserver,localhost,127.0.0.1",
    ALLOWED_ORIGINS="http://testserver", BCRYPT_ROUNDS="4")

import pytest
from starlette.testclient import TestClient
from app.main import app
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User
from app.models.applicant import Applicant
from app.models.checklist import ChecklistVersion
from app.core.security import hash_password

PASSWORD = "test-password-12345"


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        for role in ("Admin", "Manager", "NhanVien", "CongTacVien"):
            db.add(User(username=role, password_hash=hash_password(PASSWORD), role=role, is_active=True,
                full_name=role, must_change_password=False))
        version = ChecklistVersion(version_name="v1", active=True)
        db.add(version)
        db.flush()
        db.add(Applicant(ma_so_hv="1234567890", ma_ho_so="0001", khoa="2026", dot="1", ho_ten="Nguyễn Văn An",
            ho_dem="Nguyễn Văn", ten="An", email_hoc_vien="an@example.com", checklist_version_id=version.id))
    yield


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as instance:
        instance.get("/health")
        yield instance


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get("ams_csrf")}


def login(client, role="Admin"):
    response = client.post("/api/login", data={"username": role, "password": PASSWORD}, headers=csrf(client))
    assert response.status_code == 200, response.text
    return response


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    TEST_DATABASE.unlink(missing_ok=True)
