from app.db.session import SessionLocal
from app.models.applicant import Applicant
from app.models.audit import AuditLog
from conftest import login, csrf


def test_bulk_shared_fields_preserve_names_codes_and_unselected_data(client):
    login(client)
    with SessionLocal.begin() as db:
        db.add(Applicant(ma_so_hv='1234567891',ho_ten='Tên chỉ có dạng đầy đủ',ma_ho_so='HS-CU-0100',khoa='26',dot='1'))
    response=client.post('/api/applicants/batch-update',headers=csrf(client),json={'items':[
        {'ma_so_hv':key,'khoa':'35','dot':'12','nganh_nhap_hoc':'QLTNMT'} for key in ['1234567890','1234567891']]})
    assert response.status_code == 200
    assert response.json()['updated'] == 2
    with SessionLocal() as db:
        a=db.get(Applicant,'1234567891')
        assert a.ho_ten == 'Tên chỉ có dạng đầy đủ'
        assert a.ma_ho_so == 'HS-CU-0100'
        assert a.khoa == '35' and a.dot == '12'
        assert a.nganh_nhap_hoc == 'Quản lý tài nguyên môi trường'
        assert db.get(Applicant,'1234567890').email_hoc_vien == 'an@example.com'
        assert db.query(AuditLog).filter_by(action='BATCH_UPDATE').count() == 2


def test_new_major_outside_suggested_intake_saves_and_noop_bulk_update_is_not_logged(client):
    login(client)
    response=client.post('/api/applicants',headers=csrf(client),json={'ma_so_hv':'1234567891',
        'ho_ten':'Dữ liệu thử','ngay_nhan_hs':'2026-10-02','nganh_nhap_hoc':'QLTNMT','khoa':'35','dot':'12','auto_assign_ma_ho_so':True})
    assert response.status_code == 201
    assert response.json()['ma_ho_so'] == 'QLTNMT-12-0001'
    response=client.post('/api/applicants/batch-update',headers=csrf(client),json={'items':[{'ma_so_hv':'1234567891','khoa':'35'}]})
    assert response.json()['skipped'] == 1
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action='BATCH_UPDATE').count() == 0
