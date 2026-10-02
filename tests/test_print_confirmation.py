from datetime import date
from types import SimpleNamespace
import pytest
from app.db.session import SessionLocal
from app.models.applicant import Applicant
from app.models.audit import AuditLog
from app.routers import print_confirmation as confirmations
from conftest import login, csrf


def print_logs():
    with SessionLocal() as db:
        return db.query(AuditLog).filter(AuditLog.action.in_(['PRINT','PRINT_IN'])).count()


@pytest.mark.parametrize('path', [
    '/api/print/a4/1234567890', '/api/print/a5/1234567890',
    '/applicants/1234567890/print', '/applicants/1234567890/folder-cover',
    '/applicants/print/email-receipt/1234567890',
])
def test_preview_never_marks_or_logs_printing_and_confirmation_is_idempotent(client, path):
    login(client)
    response=client.get(path)
    assert response.status_code == 200
    token=response.headers['X-Print-Token']
    assert print_logs() == 0
    with SessionLocal() as db:
        assert db.get(Applicant,'1234567890').printed is False
    for _ in range(2):
        result=client.post('/api/print-confirm', headers=csrf(client),json={'token':token})
        assert result.status_code == 200, result.text
    assert print_logs() == 1
    logs = client.get('/api/journal/?action=PRINT&target_id=1234567890')
    assert logs.status_code == 200
    assert logs.json()['total'] == 1
    with SessionLocal() as db:
        assert db.get(Applicant,'1234567890').printed is True
        row=db.query(AuditLog).filter_by(action='PRINT').one()
        assert row.new_values['mshv'] == ['1234567890']
        assert row.new_values['confirmed_by_user'] is True


def test_confirmation_rejects_tampering_wrong_actor_expiry_and_deleted_applicant(client, monkeypatch):
    login(client)
    token=client.get('/api/print/a4/1234567890').headers['X-Print-Token']
    assert client.post('/api/print-confirm',headers=csrf(client),json={'token':token+'x'}).status_code == 422
    login(client,'Manager')
    assert client.post('/api/print-confirm',headers=csrf(client),json={'token':token}).status_code == 422
    login(client)
    from app.services import print_confirmation as service
    now=service.time.time()
    with monkeypatch.context() as patch:
        patch.setattr(service,'time',SimpleNamespace(time=lambda:now+7201))
        assert client.post('/api/print-confirm',headers=csrf(client),json={'token':token}).status_code == 422
    assert client.request('DELETE','/api/applicants/1234567890',headers=csrf(client),json={'reason':'Dữ liệu thử'}).status_code == 204
    assert client.post('/api/print-confirm',headers=csrf(client),json={'token':token}).status_code == 409
    assert print_logs() == 0


def test_confirmation_failure_rolls_back_print_status(client, monkeypatch):
    login(client)
    token=client.get('/api/print/a4/1234567890').headers['X-Print-Token']
    def fail(*args, **kwargs):
        raise RuntimeError('Simulated audit failure')
    monkeypatch.setattr(confirmations,'write_audit',fail)
    assert client.post('/api/print-confirm',headers=csrf(client),json={'token':token}).status_code == 500
    with SessionLocal() as db:
        assert db.get(Applicant,'1234567890').printed is False
    assert print_logs() == 0


def test_batch_print_exact_intake_and_one_confirmation_log(client):
    login(client)
    with SessionLocal.begin() as db:
        a=db.get(Applicant,'1234567890');a.ngay_nhan_hs=date(2026,10,2)
        db.add(Applicant(ma_so_hv='1234567891',khoa=a.khoa,dot='10',checklist_version_id=a.checklist_version_id))
    response=client.get('/api/batch/print-dot?dot=1&type=A4')
    assert response.status_code == 200
    assert print_logs() == 0
    result=client.post('/api/print-confirm',headers=csrf(client),json={'token':response.headers['X-Print-Token']})
    assert result.json()['count'] == 1
    with SessionLocal() as db:
        assert db.get(Applicant,'1234567891').printed is False
    result=client.get('/api/batch/print?day=2026-10-02&type=COVER')
    assert result.status_code == 200
    assert print_logs() == 1


def test_routine_views_and_legacy_click_tracking_do_not_fill_audit(client):
    login(client)
    for _ in range(3):
        assert client.get('/api/applicants/1234567890').status_code == 200
        for action in ['PRINT_IN','EXPORT']:
            assert client.post('/api/journal/track',headers=csrf(client),json={'action':action}).json()['recorded'] is False
    with SessionLocal() as db:
        assert db.query(AuditLog).filter(AuditLog.action.in_(['READ','PRINT_IN','EXPORT'])).count() == 0
