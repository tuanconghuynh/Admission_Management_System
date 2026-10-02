from app.db.session import SessionLocal
from app.models.applicant import Applicant
from app.models.audit import AuditLog
from conftest import login, csrf


def test_stop_on_error_rolls_back_every_row(client):
    login(client)
    response = client.post('/api/applicants/batch-update', headers=csrf(client), json={'stop_on_error':True,
        'items':[{'ma_so_hv':'1234567890','ten':'Changed'}, {'ma_so_hv':'1234567891','ten':'Missing'}]})
    assert response.status_code == 200, response.text
    assert response.json()['ok'] is False and response.json()['updated'] == 0
    with SessionLocal() as db:
        assert db.get(Applicant,'1234567890').ten == 'An'
        assert db.query(AuditLog).filter_by(action='BATCH_UPDATE').count() == 0
