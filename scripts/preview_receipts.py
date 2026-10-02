"""Render synthetic print examples without connecting to the database."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import sys
import subprocess

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from app.services.pdf_service import render_single_pdf, render_folder_cover_pdf

output = root / 'output/pdf'
output.mkdir(parents=True, exist_ok=True)
preview = root / 'var/print-preview'
preview.mkdir(parents=True, exist_ok=True)
applicant = SimpleNamespace(ma_so_hv='0123456789', ma_ho_so='CNTT-01-0001', ho_dem='Nguyễn Văn', ten='Minh',
    ho_ten='Nguyễn Văn Minh', full_name='Nguyễn Văn Minh', ngay_nhan_hs=date(2026,10,2),
    ngay_sinh=date(1998,4,15), khoa='26', dot='1', gioi_tinh='Nam', dan_toc='Kinh',
    nganh_nhap_hoc='Công nghệ thông tin', so_dt='0901234567', email_hoc_vien='minh@example.com',
    nguoi_nhan_ky_ten='Nguyễn Thị Nhân Viên', da_tn_truoc_do='Cao đẳng', ghi_chu='Dữ liệu minh họa để kiểm tra mẫu in.')
items = [SimpleNamespace(code=code, display_name=name, order_no=index) for index,(code,name) in enumerate([
    ('so_yeu_ly_lich','Sơ yếu lý lịch'), ('bang_tot_nghiep_cao_dang','Bằng tốt nghiệp Cao đẳng'),
    ('bang_diem_cao_dang','Bảng điểm Cao đẳng'), ('can_cuoc_cong_dan','Căn cước công dân')])]
documents = [SimpleNamespace(code=item.code, display_name=item.display_name, so_luong=quantity) for item,quantity in zip(items,[1,3,5,2])]
for name, renderer in [('bien_nhan_mau',render_single_pdf),('bia_ho_so_mau',render_folder_cover_pdf)]:
    path = output / (name + '.pdf')
    path.write_bytes(renderer(applicant, items, documents))
    subprocess.run([r'C:\Users\ASUS\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe',
        '-r','110','-png',str(path),str(preview/name)], check=True)
print('Synthetic PDF previews rendered in output/pdf and var/print-preview')
