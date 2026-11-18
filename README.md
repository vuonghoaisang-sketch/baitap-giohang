# Nhà sách Sông Hương

Bài tập tổng hợp Chương 5–6 môn Phần mềm mã nguồn mở của thầy Nguyễn Dũng. Đề và hình mẫu nằm trong [docs/baitap.pdf](docs/baitap.pdf).

Dự án dùng Python, Flask, Jinja2, Bootstrap, Flask-WTF, Flask-SQLAlchemy, Flask-Migrate và SQLite. CSS Bootstrap và sáu ảnh bìa minh hoạ được phục vụ từ thư mục `static/`, nên giao diện chạy được khi máy mất kết nối mạng.

## Chạy trên Windows PowerShell

Cài Python 3.10 trở lên. Mở PowerShell tại thư mục có `app.py` và chạy lần lượt. Có thể dùng trực tiếp Python trong môi trường ảo mà không cần kích hoạt môi trường.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 -m flask --app app db upgrade
.\.venv\Scripts\python.exe -X utf8 -m flask --app app seed
.\.venv\Scripts\python.exe -X utf8 -m flask --app app run
```

Mở [trang bán hàng](http://127.0.0.1:5000/books) hoặc [trang quản trị](http://127.0.0.1:5000/admin). Dùng Ctrl+C để dừng máy chủ. Dự án phục vụ bài tập trên máy cá nhân. **Không công khai `/admin` khi chưa có xác thực và phân quyền.**

## Migration và dữ liệu mẫu

- Migration ban đầu có trong `migrations/`. `db upgrade` áp dụng các migration còn thiếu vào `instance/bookstore.sqlite`.
- Sau khi sửa mô hình, chạy hai lệnh bên dưới. Kiểm tra nội dung migration được tạo trước khi chạy lệnh thứ hai.
- `seed` chỉ thêm các danh mục và đầu sách mẫu còn thiếu theo tên. Có sáu đầu sách gồm *Cơ sở dữ liệu* hết hàng và *Clean Code* còn 5 cuốn. Danh mục *Thiết kế* chưa có sách.
- Ảnh tải lên được lưu trong `instance/covers/`. Ứng dụng tự tạo khoá ngẫu nhiên trong `instance/secret.key` hoặc dùng biến môi trường `SECRET_KEY` nếu có. Git bỏ qua thư mục `instance/` và `.venv/`.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m flask --app app db migrate -m "Mo ta thay doi"
.\.venv\Scripts\python.exe -X utf8 -m flask --app app db upgrade
```

## Các màn hình

| Địa chỉ | Chức năng |
| --- | --- |
| `/books`, `/books/<id>` | Tìm kiếm, lọc danh mục, xem chi tiết và thêm sách |
| `/cart`, `/checkout` | Cập nhật giỏ, xem giá mới nhất, nhập thông tin giao hàng và xác nhận |
| `/orders/<id>` | Xem đơn bằng mã ngẫu nhiên trong URL. Giữ liên kết riêng vì liên kết hiển thị thông tin giao hàng |
| `/admin` | Tổng quan, đơn mới và tồn kho thấp |
| `/admin/books`, `/admin/books/new`, `/admin/books/<id>/edit` | Lọc, phân trang, thêm, sửa và xoá sách |
| `/admin/categories` | Quản lý danh mục và theo dõi số sách |
| `/admin/orders`, `/admin/orders/<id>` | Tìm đơn, xem chi tiết, cập nhật trạng thái và xem lịch sử |

## Kịch bản demo

1. Mở `/books`, lọc danh mục **Lập trình**. Thêm hai cuốn **Lập trình Python cơ bản**. Badge hiển thị 2 cuốn và giỏ có một dòng.
2. Mở giỏ và chọn **Đặt hàng**. Hai cuốn có tạm tính 190.000 đ, phí giao 20.000 đ và tổng 210.000 đ. Thêm một cuốn **Giáo trình Flask** để thử miễn phí giao hàng.
3. Nhập thông tin mẫu và chọn tiền mặt hoặc chuyển khoản. Phương thức được ghi vào đơn để xử lý thủ công. Sau khi xác nhận, trang thành công hiển thị đơn và giỏ được làm trống.
4. Mở **Quản trị → Đơn hàng**, chọn đơn vừa tạo và xem dòng sách, đơn giá lúc mua và lịch sử. Chuyển từ **Chờ xác nhận** qua **Đang giao** rồi **Hoàn tất**. Tổng quan tính doanh thu theo thời điểm hoàn tất trong tháng, theo giờ Việt Nam.
5. Tạo một đơn khác và thử **Huỷ đơn** từ trạng thái **Chờ xác nhận** hoặc **Đang giao**. Kiểm tra tồn kho tăng lại đúng số cuốn đã mua. **Hoàn tất** và **Đã huỷ** là trạng thái cuối.
6. Trong **Sách**, thử sửa giá hoặc thay bìa. Đơn cũ giữ giá lúc đặt. Trong **Danh mục**, bấm tên danh mục để mở danh sách sách đã lọc.

## Kiểm thử và mã nguồn

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 -m flask --app app db check
```

Kiểm thử tự tạo một SQLite riêng và áp dụng migration cho mỗi ca. Bộ test kiểm tra giỏ, CSRF, xác thực biểu mẫu, phí giao, checkout và trừ kho, gửi lại checkout, chặn xoá, ảnh bìa, bộ lọc, trạng thái đơn, hoàn kho và doanh thu.

- `app.py` cấu hình Flask, SQLite, migration và CSRF.
- `models.py` định nghĩa các bảng. `forms.py` định nghĩa biểu mẫu và quy tắc kiểm tra.
- `shop.py` xử lý bán hàng. `admin.py` xử lý quản trị. `catalog.py` chứa bộ lọc dùng chung.
- `seed.py` khai báo dữ liệu mẫu. `templates/` và `static/` chứa giao diện.
