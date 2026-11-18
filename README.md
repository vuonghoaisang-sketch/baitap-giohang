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
