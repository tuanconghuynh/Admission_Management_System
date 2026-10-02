from datetime import date
import io
from openpyxl import load_workbook
from app.db.session import SessionLocal
from app.models.applicant import Applicant
from app.models.audit import AuditLog
from app.services.export_service import build_excel_bytes_by_items
from conftest import login, csrf


def test_pages_and_pdf_paths(client):
    assert client.get('/auth_login.html').status_code == 200
    login(client)
    for path in ('/ams_home.html', '/students_list.html', '/account', '/admin'):
        assert client.get(path).status_code == 200, path
    for path in ('/api/applicants/1234567890/print-a5', '/api/print/a5/1234567890', '/api/print/a4/1234567890'):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.content.startswith(b'%PDF')


def test_server_pagination_filters_and_dashboard(client):
    login(client)
    with SessionLocal.begin() as db:
        db.add(Applicant(ma_so_hv='1234567891', khoa='2026', dot='2', ho_ten='Second', nganh_nhap_hoc='IT'))
    response = client.get('/api/applicants/search?khoa=2026&dot=2&size=1&sort_by=ten')
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['ma_so_hv'] == '1234567891'
    assert client.get('/api/applicants/search?sort_by=DROP_TABLE').status_code == 422
    assert client.get('/api/applicants/search?size=500').status_code == 422
    groups = client.get('/api/dashboard/stats').json()['groups']
    assert sum(row['total'] for row in groups) == 2
    assert all('email_hoc_vien' not in row for row in groups)
    assert len(client.get('/api/applicants/filter-options').json()['items']) == 2


def test_soft_delete_restore(client):
    login(client)
    response = client.request('DELETE', '/api/applicants/1234567890', json={'reason':'mistake'}, headers=csrf(client))
    assert response.status_code == 204
    with SessionLocal() as db:
        log_id = db.query(AuditLog).filter_by(action='DELETE_SOFT').one().id
    response = client.post(f'/api/journal/restore/{log_id}', json={}, headers=csrf(client))
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        applicant = db.get(Applicant, '1234567890')
        assert applicant.deleted_at is None and applicant.status == 'saved'


def test_batch_date_and_row_savepoints(client):
    login(client)
    with SessionLocal.begin() as db:
        db.add(Applicant(ma_so_hv='1234567891', khoa='2026', dot='2', ma_ho_so='0001'))
    response = client.post('/api/applicants/batch-update', headers=csrf(client), json={'items':[
        {'ma_so_hv':'1234567890', 'ngay_sinh':'01/02/2000', 'ho_ten':'Nguyễn Thị B'},
        {'ma_so_hv':'1234567891', 'dot':'1'}]})
    assert response.status_code == 200, response.text
    assert response.json()['updated'] == 1 and response.json()['invalid'] == 1
    with SessionLocal() as db:
        assert db.get(Applicant, '1234567890').ngay_sinh == date(2000,2,1)
        assert db.get(Applicant, '1234567890').ten == 'B'
        assert db.get(Applicant, '1234567891').dot == '2'


def test_batch_dry_run_never_changes_data(client):
    login(client)
    response = client.post('/api/applicants/batch-update?dry_run=true', headers=csrf(client),
        json={'items':[{'ma_so_hv':'1234567890', 'ten':'Preview'}]})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.get(Applicant,'1234567890').ten == 'An'
        assert db.query(AuditLog).filter_by(action='BATCH_UPDATE_PREVIEW').count() == 0


def test_spreadsheet_values_cannot_become_formulas():
    with SessionLocal() as db:
        applicant = db.get(Applicant, '1234567890')
        applicant.ho_dem = '=HYPERLINK("https://evil.example")'
        data = build_excel_bytes_by_items([applicant], [], [], split_name=True)
    workbook = load_workbook(io.BytesIO(data), data_only=False)
    assert all(cell.data_type != 'f' for sheet in workbook for row in sheet for cell in row)


def test_invalid_document_payload_returns_422(client):
    login(client)
    response = client.post('/api/applicants', headers=csrf(client), json={'ma_so_hv':'1234567891',
        'ho_ten':'Test', 'ngay_nhan_hs':'2026-10-02', 'docs':[{'code':'hoc_ba', 'so_luong':-1}]})
    assert response.status_code == 422
