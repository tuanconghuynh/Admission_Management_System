from pathlib import Path
from app.core.config import settings, Settings
from app.db.session import SessionLocal, DB_URL
from app.models.user import User
from conftest import login, csrf, PASSWORD


def test_database_url_is_respected():
    assert DB_URL == settings.DATABASE_URL


def test_sensitive_routes_need_login(client):
    for path in ("/api/applicants/recent", "/api/applicants/1234567890/print", "/applicants/1234567890/email-draft", "/api/journal/"):
        assert client.get(path).status_code == 401, path
    assert client.post("/applicants/send-email-batch", json={"ma_so_hv_list": ["1234567890"]}, headers=csrf(client)).status_code == 401


def test_csrf_and_origin(client):
    assert client.post("/api/login", data={"username": "Admin", "password": PASSWORD}).status_code == 403
    assert client.post("/api/login", data={"username": "Admin", "password": PASSWORD},
        headers={**csrf(client), "Origin": "https://evil.example"}).status_code == 403
    login(client)
    assert client.get("/api/me").status_code == 200


def test_manager_cannot_admin_or_hard_delete(client):
    login(client, "Manager")
    assert client.get("/admin").status_code == 403
    assert client.post("/api/journal/hard-delete", json={}, headers=csrf(client)).status_code == 403


def test_receipts_private_and_no_traversal(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RECEIPTS_DIR", str(tmp_path))
    (tmp_path / "sample.pdf").write_bytes(b"%PDF-test")
    assert client.get("/static/receipts/sample.pdf").status_code == 401
    login(client)
    assert client.get("/static/receipts/sample.pdf").status_code == 200
    assert client.get("/static/receipts/secret.txt").status_code == 404


def test_login_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", 2)
    for _ in range(2):
        assert client.post("/api/login", data={"username": "Admin", "password": "wrong"}, headers=csrf(client)).status_code == 401
    assert client.post("/api/login", data={"username": "Admin", "password": "wrong"}, headers=csrf(client)).status_code == 429


def test_admin_bootstrap_disabled(client):
    assert client.post("/api/init-admin", headers=csrf(client)).status_code == 404


def test_first_change_and_reset_invalidate_sessions(client):
    login(client, "Manager")
    with SessionLocal.begin() as db:
        user = db.query(User).filter_by(username="Manager").one()
        user.must_change_password = True
    assert client.get("/api/applicants/recent").status_code == 403
    with SessionLocal.begin() as db:
        db.query(User).filter_by(username="Manager").one().session_version += 1
    assert client.get("/api/me").status_code == 401


def test_production_refuses_unsafe_configuration():
    import pytest
    with pytest.raises(ValueError):
        Settings(_env_file=None, ENVIRONMENT="production", SESSION_SECRET="weak")


def test_body_limit_and_untrusted_host(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_REQUEST_BYTES", 100)
    assert client.post("/api/login", content=b"x" * 101, headers=csrf(client)).status_code == 413
    assert client.get("/health", headers={"Host": "evil.example"}).status_code == 400


def test_journal_client_cannot_forge_email_success(client):
    login(client)
    assert client.post("/api/journal/track", json={"action": "EMAIL_SENT"}, headers=csrf(client)).status_code == 422
    assert client.get("/api/journal/track?action=EXPORT").status_code == 405


def test_forms_accept_csrf_and_password_redirect_stays_local(client):
    login(client)
    response = client.post("/account/change-password", data={"old_password": PASSWORD,
        "new_password": "new-test-password-123", "confirm_password": "new-test-password-123",
        "next": "https://evil.example", "csrf_token": client.cookies.get("ams_csrf")}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/ams_home.html"
