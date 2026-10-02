# Import học viên và hồ sơ đã lưu trữ

## Hồ sơ cũ có giấy tờ đã nộp

1. Mở **Import học viên** và bật **Import hồ sơ đã lưu trữ**.
2. Bấm **Tải mẫu có ví dụ**. Mẫu lấy danh mục giấy tờ hiện tại, có sheet Template và HuongDan.
3. Nhập mỗi học viên một dòng. Giữ mã số HV, mã hồ sơ và số điện thoại ở dạng Text để giữ các số 0 đầu.
4. Điền số lượng đã nhận vào từng cột `SL - Tên giấy tờ [mã]`: số nguyên từ 0 đến 1000. Ô trống hoặc 0 là chưa nộp. Cột không ghép trong màn hình import cũng được tính là chưa nộp; kiểm tra các cột trước khi lưu.
5. Điền mã hồ sơ cũ, ngày nhận và người nhận hồ sơ nếu có. Ngày hỗ trợ dd/MM/yyyy, yyyy-MM-dd và ô ngày Excel. Ngày/người nhận trống lấy giá trị mặc định trên màn hình. Chế độ lưu trữ giữ nguyên mã hồ sơ; để trống để cấp sau.
6. Chọn file, kiểm tra ghép cột tự động và bấm **Xem trước**. Màn hình hiển thị tối đa 50 dòng đã chuyển đổi, gồm số lượng từng giấy tờ; chưa ghi database.
7. Bấm **Bắt đầu import**. Lỗi từng dòng được hiển thị riêng; các dòng hợp lệ vẫn được lưu. Học viên đã tồn tại hoặc mã hồ sơ trùng trong cùng khóa/đợt sẽ báo lỗi, không ghi đè. Có thể dừng import và xuất báo cáo kết quả/lỗi.
8. Bấm **In A4 / In A5** tại dòng thành công, hoặc vào Danh sách học viên để chọn/in biên nhận. Biên nhận tự chuyển trang khi danh mục dài. Số lượng đã nhận được giữ nguyên, không chia sang hồ sơ miễn môn. Xuất Excel dùng một sheet Hồ sơ; In bìa hồ sơ giữ nguyên mẫu in bưu điện cũ. Biên nhận A4 có hai liên giống nhau cho học viên và Viện; chỉ bỏ phần Hồ sơ xét miễn.

Lưu đúng ngày tiếp nhận cũ và người nhận cũ không thay đổi người thực hiện trong nhật ký: nhật ký ghi tài khoản thực sự import. Hồ sơ được lưu ở trạng thái saved, không tự đánh dấu đã in hoặc đã gửi email.

Danh mục lấy từ phiên bản checklist đang dùng khi tải mẫu/import. Nếu giấy tờ cũ chưa có trong danh mục, Admin cần thêm giấy tờ trước rồi tải lại mẫu. Nếu quản trị viên đổi danh mục giữa lúc chuẩn bị file và import, kiểm tra/ghép lại các cột. Không nhập file scan/PDF bằng tính năng này.

## Chỉ nhập thông tin học viên

Không bật chế độ lưu trữ. Không nhập tình trạng giấy tờ, ngày nhận lấy từ màn hình, người nhận lấy tài khoản hiện tại. Mã hồ sơ trong Excel được giữ đầy đủ, gồm cả phần viết tắt ngành; để trống để cấp khi tiếp nhận hồ sơ.

## Mã hồ sơ theo ngành, khóa và đợt

Mã gồm viết tắt ngành, đợt (hai chữ số) và STT (tối thiểu bốn chữ số). Mã mới có dạng `CNTT-01-0001`. STT tăng riêng theo từng ngành trong từng khóa/đợt và bắt đầu lại từ 0001 khi đổi khóa hoặc đợt. Ví dụ: CNTT, khóa 26, đợt 1 cấp CNTT-01-0001 rồi CNTT-01-0002; CNTT, khóa 26, đợt 2 bắt đầu CNTT-02-0001. Ngành NNA trong cùng khóa/đợt bắt đầu NNA-01-0001.

Chọn đủ ngành, khóa và đợt khi tiếp nhận. Mã xem trước chỉ là dự kiến; hệ thống cấp mã chính thức khi lưu và xử lý các lượt lưu đồng thời. Mã đã cấp được giữ cố định khi sửa hồ sơ. Không tự đổi mã hồ sơ cũ.

Import mã theo mẫu mới sẽ cập nhật bộ đếm của đúng ngành/khóa/đợt: import CNTT-01-0088 thì mã tiếp theo là CNTT-01-0089. Mã đã cấp cho hồ sơ bị xóa không được cấp lại. Khi tra cứu một mã xuất hiện ở nhiều khóa/đợt, chọn thêm khóa/đợt hoặc dùng mã số học viên.

Danh mục 22 ngành sử dụng đúng bảng viết tắt đã thống nhất, bao gồm Quản trị khách sạn **QTKH**, Bất động sản **BĐS**, Quản trị Dịch vụ Du lịch và Lữ Hành **QTDVDL** và Quản lý tài nguyên môi trường **QLTNMT**.

Các ô chọn có thể gõ tìm theo tên hoặc mã. Khóa và đợt cho phép nhập số ngoài gợi ý; danh sách gợi ý đợt là 1–10, không phải giới hạn dữ liệu được lưu.

## In và nhật ký

Mở bản in để xem PDF, bấm In hoặc dùng nút máy in trong PDF. Sau khi giấy đã in thành công, bấm **Xác nhận đã in thành công** để ghi nhật ký và đánh dấu hồ sơ đã in. Đóng cửa sổ hoặc hủy in không ghi nhật ký in. Máy chủ không tự biết trạng thái máy in; nút xác nhận do người dùng thực hiện. Một bản xem in chỉ được xác nhận một lần, phiên xác nhận hết hạn sau hai giờ; mở lại bản in để ghi nhận lần in mới.

Nhật ký không còn ghi lượt xem hồ sơ thành công hoặc các dòng trùng từ nút in/xuất. In nhiều hồ sơ ghi một dòng gồm danh sách mã số học viên và số lượng. Lịch sử sửa/xóa, gửi email và nhật ký cũ được giữ.

## Sửa và xóa nhiều hồ sơ

Trong Danh sách hồ sơ, đánh dấu từng dòng hoặc **Chọn tất cả trên trang**, rồi bấm **Sửa các hồ sơ đã chọn** hoặc **Xóa các hồ sơ đã chọn**. Tối đa 100 hồ sơ trên trang. Sửa nhiều chỉ thay các trường đã đánh dấu trong hộp thoại; bỏ đánh dấu để giữ dữ liệu hiện tại. Xóa nhiều yêu cầu lý do và dùng xóa tạm, có thể khôi phục từ nhật ký. Các dòng không thực hiện được sẽ có thông báo riêng; không tự báo thành công cho dòng lỗi.

Sau khi cập nhật hệ thống, tải lại trang bằng Ctrl+F5. Thay đổi này không cần migration và không tự sửa các hồ sơ đã có trong database.
