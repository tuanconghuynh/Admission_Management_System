import pytest
from fastapi import HTTPException
from app.db.session import SessionLocal
from app.models.applicant import Applicant
from app.models.operations import ReceiptSequence
from app.services.majors import MAJORS, resolve_major
from app.services.receipt_sequence import next_major_receipt, reserve_imported_major_receipt
from app.routers import applicants
from conftest import csrf, login


def create(client, mshv, major='Công nghệ thông tin', khoa='26', dot='1', **extra):
    return client.post('/api/applicants', headers=csrf(client), json={
        'ma_so_hv': mshv, 'ho_ten': 'Nguyễn Văn Test', 'ngay_nhan_hs': '2026-10-02',
        'nganh_nhap_hoc': major, 'khoa': khoa, 'dot': dot, 'auto_assign_ma_ho_so': True, **extra})


def test_official_catalog(client):
    login(client)
    result = client.get('/api/applicants/majors')
    assert result.status_code == 200
    items = result.json()['items']
    assert len(items) == 22
    mapping = {item['name']: item['code'] for item in items}
    assert mapping['Quản trị khách sạn'] == 'QTKH'
    assert mapping['Bất động sản'] == 'BĐS'
    assert resolve_major('tai chinh - ngan hang')[1] == 'TCNH'
    assert resolve_major('BDS')[1] == 'BĐS'
    page = client.get('/compilation.html')
    assert page.status_code == 200
    for name, code in MAJORS:
        assert f'data-code="{code}"' in page.text


def test_numbering_resets_per_major_intake(client):
    login(client)
    cases = [('1234567801','CNTT','26','1','CNTT-01-0001'),
        ('1234567802','CNTT','26','1','CNTT-01-0002'), ('1234567803','CNTT','26','2','CNTT-02-0001'),
        ('1234567804','CNTT','27','1','CNTT-01-0001'), ('1234567805','NNA','26','1','NNA-01-0001'),
        ('1234567806','BDS','26','1','BĐS-01-0001')]
    for mshv, major, khoa, dot, expected in cases:
        response = create(client, mshv, major, khoa, dot)
        assert response.status_code == 201, response.text
        assert response.json()['ma_ho_so'] == expected
    with SessionLocal() as db:
        assert db.get(Applicant, '1234567890').ma_ho_so == '0001'
        assert db.get(Applicant, '1234567806').nganh_nhap_hoc == 'Bất động sản'


def test_preview_does_not_reserve_and_save_uses_current_counter(client):
    login(client)
    path = '/api/applicants/receipt-code-preview?major=CNTT&khoa=26&dot=1'
    assert client.get(path).json() == {'ma_ho_so': 'CNTT-01-0001', 'reserved': False}
    with SessionLocal() as db:
        assert db.query(ReceiptSequence).count() == 0
    assert create(client, '1234567801').json()['ma_ho_so'] == 'CNTT-01-0001'
    assert create(client, '1234567802').json()['ma_ho_so'] == 'CNTT-01-0002'


def test_import_advances_counter_and_keeps_scope(client):
    login(client)
    assert create(client,'1234567801', ma_ho_so='CNTT-01-0088', auto_assign_ma_ho_so=False).status_code == 201
    assert create(client,'1234567802').json()['ma_ho_so'] == 'CNTT-01-0089'
    assert create(client,'1234567803', dot='2').json()['ma_ho_so'] == 'CNTT-02-0001'
    duplicate = create(client,'1234567804', ma_ho_so='cntt-01-0088', auto_assign_ma_ho_so=False)
    assert duplicate.status_code == 409


def test_deleted_numbers_not_recycled_and_transaction_rolls_back(client, monkeypatch):
    login(client)
    assert create(client,'1234567801').status_code == 201
    with SessionLocal.begin() as db:
        db.get(Applicant,'1234567801').status = 'deleted'
    def fail(*args, **kwargs):
        raise HTTPException(503, 'Audit unavailable')
    original = applicants.write_audit
    monkeypatch.setattr(applicants,'write_audit',fail)
    assert create(client,'1234567802').status_code == 503
    monkeypatch.setattr(applicants,'write_audit',original)
    assert create(client,'1234567803').json()['ma_ho_so'] == 'CNTT-01-0002'


def test_issued_code_kept_when_major_changes(client):
    login(client)
    assert create(client,'1234567801').status_code == 201
    response = client.put('/api/applicants/1234567801', headers=csrf(client), json={'nganh_nhap_hoc':'Ngôn ngữ Anh','auto_assign_ma_ho_so':True, 'update_reason': {'key': 'khac', 'text': 'Chuyển ngành theo yêu cầu'}})
    assert response.status_code == 200, response.text
    assert response.json()['ma_ho_so'] == 'CNTT-01-0001'
    response = client.put('/api/applicants/1234567801', headers=csrf(client), json={'ma_ho_so':'NNA-01-0001', 'update_reason': {'key': 'khac', 'text': 'Thử thay mã đã cấp'}})
    assert response.status_code == 422


def test_duplicate_codes_require_intake_for_lookup(client):
    login(client)
    assert create(client,'1234567801').status_code == 201
    assert create(client,'1234567802', khoa='27').status_code == 201
    assert client.get('/api/applicants/by-code/CNTT-01-0001').status_code == 409
    assert client.get('/api/applicants/find?ma_ho_so=CNTT-01-0001').status_code == 409
    response = client.get('/api/applicants/by-code/CNTT-01-0001?khoa=27&dot=1')
    assert response.status_code == 200
    assert response.json()['applicant']['ma_so_hv'] == '1234567802'


def test_assignment_rejects_missing_intake_and_unknown_major(client):
    login(client)
    for kwargs in ({'major':'Ngành chưa có'}, {'khoa':''}, {'dot':''}):
        response = create(client,'1234567801', **kwargs)
        assert response.status_code == 422, response.text
    with SessionLocal() as db:
        assert db.query(ReceiptSequence).count() == 0


def test_counter_seeds_history_and_grows_beyond_four_digits():
    with SessionLocal.begin() as db:
        db.add(Applicant(ma_so_hv='1234567801', ma_ho_so='CNTT-01-9999', khoa='26',dot='1'))
    with SessionLocal.begin() as db:
        assert next_major_receipt(db, 'CNTT', '26', '1') == 'CNTT-01-10000'
        assert next_major_receipt(db, 'CNTT', '26', '2') == 'CNTT-02-0001'


def test_old_format_import_kept_and_new_format_requires_matching_intake(client):
    login(client)
    response = create(client, '1234567801', ma_ho_so='CNTT-0088', auto_assign_ma_ho_so=False)
    assert response.status_code == 201
    assert response.json()['ma_ho_so'] == 'CNTT-0088'
    assert create(client, '1234567802', dot='01').json()['ma_ho_so'] == 'CNTT-01-0089'
    assert create(client, '1234567803').json()['ma_ho_so'] == 'CNTT-01-0090'
    response = create(client, '1234567804', ma_ho_so='CNTT-02-0091', auto_assign_ma_ho_so=False)
    assert response.status_code == 422
    assert create(client, '1234567805').json()['ma_ho_so'] == 'CNTT-01-0091'
