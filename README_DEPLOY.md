# Chạy và triển khai Admission Management System

Hệ thống dùng Python 3.12, FastAPI, MySQL và một tiến trình worker riêng để gửi email. Hosting phải chạy được Python lâu dài hoặc Docker; gói hosting chỉ hỗ trợ PHP không chạy được cấu hình này.

## Chạy trên Windows

1. Sao lưu cơ sở dữ liệu và thư mục biên nhận trước lần nâng cấp đầu tiên.
2. Cài Python 3.12 và MySQL. Mở thư mục dự án, cấu hình `.env` cho môi trường phát triển:

```dotenv
ENVIRONMENT=development
DATABASE_URL=mysql+pymysql://ams:MAT_KHAU_DA_URL_ENCODE@127.0.0.1:3306/Admission_Management_System?charset=utf8mb4
COOKIE_SECURE=false
AUTO_CREATE_TABLES=true
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_ENABLED=false
```

Giữ nguyên các secret hiện có khi nâng cấp dữ liệu. `DATABASE_URL` hiện được ưu tiên thực sự; không còn ngầm dùng tài khoản root nếu URL không hoạt động. Cấu hình hiện tại trên máy đã báo MySQL 1524 (`mysql_native_password` không được nạp). Cần tạo tài khoản phù hợp với phiên bản MySQL và sửa URL trước khi chạy. Với MySQL 8.4, dùng tài khoản `caching_sha2_password`, cấp quyền trên riêng database của ứng dụng. Không thay đổi tài khoản đang dùng cho phần mềm khác. Mật khẩu trong URL phải được URL encode.

3. Chạy `run_server.bat`, chọn Local. Script kiểm tra thư viện, chạy migration và khởi động web cùng worker. Mở http://127.0.0.1:8000. Chế độ LAN cần nhập đúng địa chỉ IPv4; chỉ dùng trong mạng tin cậy khi chưa cấu hình HTTPS.
4. Nếu chưa có Admin, mở PowerShell tại thư mục dự án:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_admin
```

CLI hỏi mật khẩu tối thiểu 12 ký tự và yêu cầu đổi ở lần đăng nhập đầu. Không có API công khai tạo Admin hay mật khẩu mặc định.

## Triển khai Docker trên VPS Linux

Chuẩn bị domain trỏ về VPS, Docker Compose, Nginx và chứng chỉ HTTPS. Không sao chép `.venv` từ Windows lên Linux.

```bash
cp .env.example .env
cp .env.database.example .env.database
```

Điền thông tin thật trong hai file. Nếu dùng MySQL trong Compose, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` phải khớp `DATABASE_URL`, hostname là `db`. Đặt mật khẩu root riêng trong `.env.database`. Nếu dùng MySQL ngoài, sửa hostname trong URL và bỏ `--profile database` khỏi các lệnh.

Tạo ba secret khác nhau bằng cách chạy lệnh sau ba lần rồi điền lần lượt `SESSION_SECRET`, `AUDIT_HMAC_SECRET`, `DELETE_KEY_SECRET`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Đặt `ALLOWED_HOSTS` là domain thật, `ALLOWED_ORIGINS=https://domain-that`, `COOKIE_SECURE=true`, `AUTO_CREATE_TABLES=false`, `ENVIRONMENT=production`. Không đặt wildcard. Nếu đã có dữ liệu, giữ `AUDIT_HMAC_SECRET`, `DELETE_KEY_SECRET` và `PASSWORD_PEPPER` cũ; đổi pepper sẽ làm mật khẩu cũ không xác thực được. Đổi session secret sẽ đăng xuất các phiên hiện tại. Thông tin từng được đưa vào Git cần được xử lý riêng và đổi các mật khẩu dịch vụ đã lộ.

```bash
docker compose --profile database build
docker compose --profile database up -d db
docker compose --profile database run --rm web alembic upgrade head
docker compose --profile database run --rm web python -m scripts.create_admin
docker compose --profile database up -d web worker
docker compose ps
docker compose logs --tail=100 web worker
```

Đợi MySQL healthy trước migration. Nếu đang dùng database cũ, sao lưu trước rồi mới migration. Migration từ chối khi mã hồ sơ bị trùng trong cùng khóa/đợt; xử lý dữ liệu trùng rồi chạy lại. DDL MySQL không rollback hoàn toàn: nếu nâng cấp thất bại, kiểm tra trạng thái và khôi phục từ bản sao lưu khi cần. Không chạy downgrade để xóa bảng.

Chỉnh `deploy/nginx.conf` theo domain và đường dẫn chứng chỉ, dùng `nginx -t` trước khi reload. Nginx chuyển HTTPS đến `127.0.0.1:8000`; không mở port 8000 hoặc 3306 ra Internet. Cấu hình tin cậy proxy hiện dành cho Nginx trên cùng máy với port Docker chỉ bind loopback; nếu đổi kiến trúc proxy phải giới hạn lại `FORWARDED_ALLOW_IPS`.

Biên nhận nằm trong volume `receipts`, database nằm trong volume `mysql_data`; cần giữ cả hai. Khi chuyển từ bản cũ, chép các PDF đang dùng từ `assets/receipts` vào `/app/var/receipts` trong volume trước khi mở dịch vụ. Nếu `RECEIPTS_DIR` cũ khác, chuyển từ đường dẫn đó. Chạy tác vụ chép bằng tài khoản phù hợp rồi đảm bảo UID 10001 đọc/ghi được; không công khai thư mục này qua Nginx. File PDF chỉ được tải qua route đã xác thực.

## Email và vận hành

Mặc định email tắt. Khi bật, cấu hình SMTP_USER, SMTP_PASS, SMTP_FROM và EMAIL_ENABLED=true. Cổng 465 dùng SSL=true/STARTTLS=false; cổng 587 thường dùng SSL=false/STARTTLS=true. Khởi động lại cả web và worker sau khi thay đổi `.env`.

API gửi email trả HTTP 202 và job_id: đây là xác nhận xếp hàng. Trạng thái `sent` chỉ được ghi sau khi SMTP chấp nhận; không bảo đảm người nhận đã đọc hay thư không bị đưa vào spam. Có thể tra `/api/applicants/email-jobs/{job_id}` bằng phiên đăng nhập của người gửi hoặc Admin. Worker tự thử lại lỗi kết nối an toàn, tối đa theo EMAIL_MAX_ATTEMPTS. Trạng thái `uncertain` cần đối chiếu mailbox/log trước khi gửi lại để tránh thư trùng. Hồ sơ đã xóa trước khi xử lý sẽ được hủy email đang chờ. Kiểm tra gửi thử bằng tài khoản và địa chỉ được phép trước khi dùng thật.

`/api/health` kiểm tra tiến trình; `/api/ready` kiểm tra database. Theo dõi cả worker và các job pending/retry/failed/uncertain. Hai web worker và một email worker có thể dùng tối đa khoảng 30 kết nối với pool mặc định 5+5 mỗi tiến trình; chọn pool và số worker theo RAM, CPU và giới hạn MySQL. Báo cáo giới hạn 1.000 hồ sơ/lượt, email 100 hồ sơ/lượt; chia theo khóa/đợt thay vì tăng giới hạn không kiểm soát.

## Sao lưu và khôi phục

Máy chạy công cụ sao lưu cần Python cùng thư viện ứng dụng và `mysqldump` phù hợp phiên bản MySQL trên PATH; image web hiện không chứa mysqldump. URL database phải truy cập được từ máy sao lưu (hostname `db` chỉ hoạt động trong mạng Compose).

```bash
python -m scripts.backup --output backups
```

Lệnh tạo database.sql, receipts.tar.gz và manifest SHA-256. Sao lưu lúc ngừng thay đổi hồ sơ/gửi email nếu cần SQL và file khớp hoàn toàn. Đặt lịch sao lưu ngoài ứng dụng, lưu bản mã hóa ở máy khác và thử phục hồi định kỳ trên database thử nghiệm. `.env` cần bản sao riêng được bảo vệ; công cụ không đưa secret vào archive.

Khi khôi phục: dừng web/worker, kiểm tra SHA-256 theo manifest, nạp database.sql bằng client mysql vào database đã chọn, giải nén receipts.tar.gz vào thư mục staging rồi chuyển vào volume biên nhận và chỉnh quyền UID 10001. Kiểm tra URL/secret, chạy migration nếu phiên bản code mới hơn, khởi động lại dịch vụ, kiểm tra đăng nhập/PDF/hàng đợi. Không dùng `docker compose down -v` trên hệ thống có dữ liệu.

Dọn các PDF nháp mồ côi bằng dry-run trước:

```bash
python -m scripts.maintenance --days 30
python -m scripts.maintenance --days 30 --apply
```

Công cụ giữ file đang được email job tham chiếu và các file cũ không mang tên UUID; nhật ký không tự bị xóa.

## Kiểm tra trước khi mở cho người dùng

```bash
python -m pip install -r requirements-dev.txt
python -m scripts.run_checks
python -m scripts.web_checks --node node
```

Các kiểm thử dùng database SQLite riêng và giả lập SMTP. `scripts/mysql_checks.py` chỉ chạy với MySQL localhost, tạo database tên ngẫu nhiên rồi tự xóa; không sử dụng database vận hành để thử. Các script biến đổi mã nguồn một lần đã được loại bỏ.

Kết quả kiểm tra tại máy phát triển: kiểm thử chức năng/bảo mật/giao dịch/migration/PDF/Excel, cú pháp JavaScript, migration MySQL và tranh chấp cấp mã/email đạt. Audit thư viện theo requirements.lock ngày 02/10/2026 không phát hiện lỗ hổng đã biết. Chưa xác minh build Docker, Nginx/chứng chỉ trên host thật, tải thực tế hay SMTP thật; kiểm tra các mục này trên staging trước khi mở dịch vụ. Bản khóa thư viện dùng phiên bản chính xác; cập nhật cần chạy lại kiểm thử và audit.
