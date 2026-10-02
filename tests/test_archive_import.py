import io
import re
from datetime import date

from pypdf import PdfReader
from app.db.session import SessionLocal
from app.models.applicant import Applicant, ApplicantDoc
from app.models.audit import AuditLog
from app.models.checklist import ChecklistItem, ChecklistVersion
from conftest import csrf, login


def checklist():
    with SessionLocal.begin() as db:
        version = db.query(ChecklistVersion).one()
        for index, (code, name) in enumerate([
            ('so_yeu_ly_lich', 'Sơ yếu lý lịch'),
            ('can_cuoc_cong_dan', 'Căn cước công dân'),
            ('tai_lieu_bo_sung', 'Tài liệu bổ sung đã lưu'),
        ]):
            db.add(ChecklistItem(version_id=version.id, code=code, display_name=name, order_no=index))


def payload():
    return dict(import_archived=True, ma_so_hv='0123456789', ma_ho_so='HS-CU-2025-0088',
        ho_ten='Trần Thị Bình', ngay_nhan_hs='2025-09-15', nguoi_nhan_ky_ten='Nguyễn Văn Người Nhận',
        khoa='25', dot='1', checklist_version_name='v1', docs=[
            {'code': 'so_yeu_ly_lich', 'so_luong': 2},
            {'code': 'can_cuoc_cong_dan', 'so_luong': 0},
            {'code': 'tai_lieu_bo_sung', 'so_luong': 3},
        ])


def test_archive_import_preserves_history_and_prints_receipts(client):
    checklist()
    login(client)
    result = client.post('/applicants', headers=csrf(client), json=payload())
    assert result.status_code == 201, result.text
    with SessionLocal() as db:
        applicant = db.get(Applicant, '0123456789')
        assert applicant.ma_ho_so == 'HS-CU-2025-0088'
        assert applicant.ngay_nhan_hs == date(2025, 9, 15)
        assert applicant.nguoi_nhan_ky_ten == 'Nguyễn Văn Người Nhận'
        assert applicant.status == 'saved' and not applicant.printed
        documents = db.query(ApplicantDoc).filter_by(applicant_ma_so_hv=applicant.ma_so_hv).all()
        assert {document.code: document.so_luong for document in documents} == {
            'so_yeu_ly_lich': 2, 'can_cuoc_cong_dan': 0, 'tai_lieu_bo_sung': 3}
        assert next(document for document in documents if document.code == 'tai_lieu_bo_sung').display_name == 'Tài liệu bổ sung đã lưu'
        audit = db.query(AuditLog).filter_by(action='CREATE', target_id=applicant.ma_so_hv).one()
        assert audit.actor_name == 'Admin' and audit.new_values['import_archived'] is True
    for path in ('/applicants/0123456789/print', '/applicants/0123456789/print-a5'):
        response = client.get(path)
        assert response.status_code == 200, response.text
        text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
        assert 'Tài liệu bổ sung đã lưu' in text, (path, text)
        assert 'Trần Thị Bình' in text and 'Nguyễn Văn Người Nhận' in text
        assert re.search(r'Tài liệu bổ sung đã lưu\s+3', text) or re.search(r'3\s+Tài liệu bổ sung đã lưu', text)


def test_archive_rejects_unknown_duplicate_and_bad_quantities(client):
    checklist()
    login(client)
    for docs in ([], [{'code': 'not_in_checklist', 'so_luong': 1}],
        [{'code': 'so_yeu_ly_lich', 'so_luong': -1}], [{'code': 'so_yeu_ly_lich', 'so_luong': 1.5}],
        [{'code': 'so_yeu_ly_lich', 'so_luong': None}],
        [{'code': 'so_yeu_ly_lich', 'so_luong': 1}] * 2):
        data = payload()
        data['docs'] = docs
        assert client.post('/applicants', headers=csrf(client), json=data).status_code == 422
    with SessionLocal() as db:
        assert db.get(Applicant, '0123456789') is None


def test_archive_duplicate_does_not_overwrite(client):
    checklist()
    login(client)
    assert client.post('/applicants', headers=csrf(client), json=payload()).status_code == 201
    data = payload()
    data['docs'][0]['so_luong'] = 99
    assert client.post('/applicants', headers=csrf(client), json=data).status_code == 409
    data['ma_so_hv'] = '0123456788'
    assert client.post('/applicants', headers=csrf(client), json=data).status_code == 409
    with SessionLocal() as db:
        assert db.query(ApplicantDoc).filter_by(applicant_ma_so_hv='0123456789', code='so_yeu_ly_lich').one().so_luong == 2
        assert db.get(Applicant, '0123456788') is None


def test_normal_import_uses_current_actor(client):
    checklist()
    login(client)
    data = payload()
    data['import_archived'] = False
    assert client.post('/applicants', headers=csrf(client), json=data).status_code == 201
    with SessionLocal() as db:
        assert db.get(Applicant, '0123456789').nguoi_nhan_ky_ten == 'Admin'


def test_a5_keeps_all_documents_across_pages(client):
    with SessionLocal.begin() as db:
        version = db.query(ChecklistVersion).one()
        for index in range(48):
            db.add(ChecklistItem(version_id=version.id, code=f'custom_{index}', display_name=f'Tài liệu lưu trữ số {index:02}', order_no=index))
    login(client)
    data = payload()
    data['docs'] = [{'code': f'custom_{index}', 'so_luong': index} for index in range(48)]
    assert client.post('/applicants', headers=csrf(client), json=data).status_code == 201
    for suffix in ('print-a5', 'print'):
        response = client.get('/applicants/0123456789/' + suffix)
        assert response.status_code == 200
        reader = PdfReader(io.BytesIO(response.content))
        assert len(reader.pages) > 1
        text = '\n'.join(page.extract_text() for page in reader.pages)
        for index in range(1 if suffix == 'print' else 0, 48):
            assert f'Tài liệu lưu trữ số {index:02}' in text, text


def test_archive_import_permission(client):
    checklist()
    login(client, 'CongTacVien')
    assert client.post('/applicants', headers=csrf(client), json=payload()).status_code == 403
    with SessionLocal() as db:
        assert db.get(Applicant, '0123456789') is None
