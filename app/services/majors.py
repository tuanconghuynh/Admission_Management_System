"""Official institute major names and receipt prefixes supplied by the owner."""
import re
import unicodedata

MAJORS = (
    ('Ngôn ngữ Anh', 'NNA'),
    ('Ngôn ngữ Trung Quốc', 'NNTQ'),
    ('Tâm lý học', 'TLH'),
    ('Quan hệ công chúng', 'QHCC'),
    ('Quản trị kinh doanh', 'QTKD'),
    ('Quản trị nhân lực', 'QTNL'),
    ('Marketing', 'MKT'),
    ('Digital Marketing', 'DGM'),
    ('Logistics và quản lý chuỗi cung ứng', 'LOG'),
    ('Luật', 'LUAT'),
    ('Luật kinh tế', 'LKT'),
    ('Công nghệ thông tin', 'CNTT'),
    ('Quản lý xây dựng', 'QLXD'),
    ('Kế toán', 'KT'),
    ('Tài chính – Ngân hàng', 'TCNH'),
    ('Quản trị khách sạn', 'QTKH'),
    ('Quản trị Dịch vụ Du lịch và Lữ Hành', 'QTDVDL'),
    ('Ngôn ngữ Nhật', 'NNN'),
    ('Ngôn ngữ Hàn Quốc', 'NNHQ'),
    ('Bất động sản', 'BĐS'),
    ('Công nghệ thực phẩm', 'CNTP'),
    ('Quản lý tài nguyên môi trường', 'QLTNMT'),
)


def normalize_major(value):
    value = unicodedata.normalize('NFD', str(value or '').casefold()).replace('đ', 'd')
    value = ''.join(character for character in value if not unicodedata.combining(character))
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


def resolve_major(value):
    key = normalize_major(value)
    for name, code in MAJORS:
        if key in (normalize_major(name), normalize_major(code)):
            return name, code
    return None
