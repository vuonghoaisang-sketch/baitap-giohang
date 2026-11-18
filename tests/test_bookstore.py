import io
import re
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from flask_migrate import upgrade
from PIL import Image

from app import create_app
from models import Book, CANCELLED, COMPLETE, Category, Order, OrderHistory, PENDING, SHIPPING, db, utc_now
from shop import shipping_fee


class BookstoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{Path(self.temp.name) / 'test.sqlite'}",
            "UPLOAD_FOLDER": Path(self.temp.name) / "covers",
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            self.addCleanup(db.engine.dispose)
            upgrade()
        result = self.app.test_cli_runner().invoke(args=["seed"])
        self.assertEqual(result.exit_code, 0, result.output)

    def post(self, url, data, origin="/books", follow=True):
        response = self.client.get(origin)
        self.assertEqual(response.status_code, 200)
        pattern = rb'name="csrf_token"[^>]+value="([^"]+)"'
        match = re.search(pattern, response.data) or re.search(pattern, self.client.get("/books").data)
        csrf = match[1].decode()
        return self.client.post(url, data={"csrf_token": csrf, **data}, follow_redirects=follow)

    def add(self, book=1, quantity=1, **data):
        return self.post(f"/books/{book}/add", {"quantity": quantity, **data}, follow=False)

    def session_cart(self):
        with self.client.session_transaction() as session:
            return session.get("cart", {})

    def checkout(self, follow=False, **data):
        with self.client.session_transaction() as session:
            token = session.get("checkout_token")
        payload = dict(name="Nguyễn Văn An", phone="0912345678", email="", address="12 Lê Lợi, Huế",
                       payment="cash", checkout_token=token)
        payload.update(data)
        return self.post("/checkout", payload, origin="/checkout", follow=follow)

    def order_count(self):
        with self.app.app_context():
            return db.session.scalar(db.select(db.func.count(Order.id)))

    def stock(self, book_id=1):
        with self.app.app_context():
            return db.session.get(Book, book_id).stock

    def change(self, new_status, order=1):
        return self.post(f"/admin/orders/{order}/status", {"status": new_status},
                         origin=f"/admin/orders/{order}")

    def test_add_twice_and_preserve_filters(self):
        self.add()
        response = self.add(q="Python", category=1)
        self.assertIn("q=Python", response.location)
        self.assertIn("category=1", response.location)
        self.assertEqual(self.session_cart(), {"1": 2})
        self.assertIn('cart-badge">2', self.client.get("/books").text)

    def test_empty_cart(self):
        response = self.client.get("/checkout", follow_redirects=True)
        self.assertEqual(response.request.path, "/cart")
        self.assertIn("Giỏ hàng trống", response.text)
        self.assertNotIn('href="/checkout"', response.text)

    def test_reject_overstock_and_out_of_stock(self):
        self.add(quantity=29)
        self.add(quantity=2)
        self.add(book=3)
        self.assertEqual(self.session_cart(), {"1": 29})
        self.add()
        response = self.post("/cart", {"action": "plus", "book_id": "1"})
        self.assertIn("Không thể tăng", response.text)
        self.assertEqual(self.session_cart(), {"1": 30})
        self.assertIn("disabled", self.client.get("/books/3").text)

    def test_cart_changes_and_live_price(self):
        self.add(quantity=2)
        with self.app.app_context():
            db.session.get(Book, 1).price = 123_000
            db.session.commit()
        self.assertIn("246.000 đ", self.client.get("/cart").text)
        self.post("/cart", {"action": "minus", "book_id": "1"})
        self.assertEqual(self.session_cart(), {"1": 1})
        self.post("/cart", {"action": "minus", "book_id": "1"})
        self.assertEqual(self.session_cart(), {})
        self.add()
        self.add(book=2)
        self.post("/cart", {"action": "remove", "book_id": "1"})
        self.assertEqual(self.session_cart(), {"2": 1})
        self.post("/cart", {"action": "clear"})
        self.assertEqual(self.session_cart(), {})

    def test_checkout_validation(self):
        self.add()
        with self.client.session_transaction() as session:
            token = session["checkout_token"]
        response = self.post("/checkout", dict(name=" ", phone="123", email="sai", address=" ",
                                                 payment="x", checkout_token=token), origin="/checkout")
        self.assertEqual(response.status_code, 200)
        self.assertIn("10 chữ số bắt đầu bằng 0", response.text)
        self.assertIn("Email không hợp lệ", response.text)
        self.assertEqual(self.order_count(), 0)
        self.assertEqual(self.session_cart(), {"1": 1})

    def test_shipping_threshold(self):
        self.assertEqual(shipping_fee(199_999), 20_000)
        self.assertEqual(shipping_fee(200_000), 0)
        self.add(book=1, quantity=2)
        self.assertIn("210.000 đ", self.client.get("/checkout").text)
        self.add(book=2)
        self.assertIn("310.000 đ", self.client.get("/checkout").text)

    def test_checkout_creates_order_and_snapshots_price(self):
        self.add(quantity=2)
        with self.client.session_transaction() as session:
            token = session["checkout_token"]
        cookie = self.client.get_cookie("session").value
        response = self.checkout()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.startswith("/orders/"))
        self.assertNotEqual(response.location, "/orders/1")
        self.assertIn("Đặt hàng thành công", self.client.get(response.location).text)
        self.assertEqual(self.client.get("/orders/1").status_code, 404)
        self.assertEqual(self.session_cart(), {})
        self.assertEqual(self.stock(), 28)
        with self.app.app_context():
            order = db.session.get(Order, 1)
            self.assertEqual((order.status, order.shipping_fee, order.total), (PENDING, 20_000, 210_000))
            self.assertEqual((order.items[0].quantity, order.items[0].unit_price), (2, 95_000))
            self.assertEqual([entry.status for entry in order.history], [PENDING])
            db.session.get(Book, 1).price = 100_000
            db.session.commit()
        self.assertIn("95.000 đ", self.client.get("/admin/orders/1").text)
        self.client.set_cookie("session", cookie)
        with self.client.session_transaction() as session:
            self.assertEqual(session["checkout_token"], token)
        self.assertEqual(self.checkout().location, response.location)
        self.assertEqual((self.order_count(), self.stock()), (1, 28))

    def test_shortage_rolls_back_entire_checkout(self):
        self.add()
        self.add(book=2, quantity=2)
        with self.app.app_context():
            db.session.get(Book, 2).stock = 1
            db.session.commit()
        result = self.checkout(follow=True)
        self.assertEqual(result.request.path, "/cart")
        self.assertIn("Không đủ hàng cho «Giáo trình Flask»", result.text)
        self.assertEqual((self.order_count(), self.stock(), self.stock(2)), (0, 30, 1))
        self.assertEqual(self.session_cart(), {"1": 1, "2": 2})

    def test_protected_deletions(self):
        self.add()
        self.checkout()
        response = self.post("/admin/books/1/delete", {}, origin="/admin/books")
        self.assertIn("Không thể xoá sách đã có trong đơn hàng", response.text)
        response = self.post("/admin/categories/1/delete", {}, origin="/admin/categories")
        self.assertIn("còn 2 đầu sách", response.text)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Book, 1))
            self.assertIsNotNone(db.session.get(Category, 1))

    def test_status_transitions_and_revenue(self):
        self.add()
        self.checkout()
        self.assertIn("không hợp lệ", self.change(COMPLETE).text)
        self.assertIn("0 đ", self.client.get("/admin").text)
        self.assertIn("Đã cập nhật", self.change(SHIPPING).text)
        self.assertIn("Đã cập nhật", self.change(COMPLETE).text)
        self.assertIn("không hợp lệ", self.change(CANCELLED).text)
        self.assertEqual(self.stock(), 29)
        dashboard = self.client.get("/admin")
        self.assertRegex(dashboard.text, r"Doanh thu tháng [0-9]+</div><strong[^>]+>115\.000 đ")
        with self.app.app_context():
            order = db.session.get(Order, 1)
            order.completed_at = utc_now() - timedelta(days=45)
            db.session.commit()
        self.assertRegex(self.client.get("/admin").text, r"Doanh thu tháng [0-9]+</div><strong[^>]+>0 đ")

    def test_cancel_restocks_once(self):
        self.add(quantity=4)
        self.checkout()
        self.change(SHIPPING)
        self.assertIn("Đã cập nhật", self.change(CANCELLED).text)
        self.assertEqual(self.stock(), 30)
        self.assertIn("không hợp lệ", self.change(CANCELLED).text)
        self.assertEqual(self.stock(), 30)
        with self.app.app_context():
            self.assertEqual(db.session.scalars(db.select(OrderHistory.status).order_by(OrderHistory.id)).all(),
                             [PENDING, SHIPPING, CANCELLED])

    def test_csrf_and_not_found(self):
        self.assertEqual(self.client.post("/books/1/add", data={"quantity": 1}).status_code, 400)
        self.assertEqual(self.client.get("/admin/books/1/delete").status_code, 405)
        self.assertEqual(self.client.get("/books/99999").status_code, 404)
        self.assertEqual(self.session_cart(), {})

    def test_upload_valid_content_and_replace_cover(self):
        data = dict(name="Sách bổ sung", author="Tác giả", category_id=1, price=1000, stock=0)
        fol = self.app.config["UPLOAD_FOLDER"]
        bad_upload = (io.BytesIO(b"not a png"), "fake.png")
        result = self.post("/admin/books/new", dict(data, image=bad_upload), origin="/admin/books/new")
        self.assertIn("Không thể lưu ảnh", result.text)
        for path, name in [("/admin/books/new", "first.png"), ("/admin/books/7/edit", "new.png")]:
            output = io.BytesIO()
            Image.new("RGB", (4, 4)).save(output, "PNG")
            output.seek(0)
            self.assertIn("Đã lưu sách", self.post(path, dict(data, image=(output, name)), origin=path).text)
            files = list(fol.iterdir())
            self.assertEqual(len(files), 1)
            self.assertNotEqual(files[0].name, name)
            with self.client.get("/covers/" + files[0].name) as response:
                self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(Book, 7).stock, 0)
        kept_cover = next(fol.iterdir())
        result = self.post("/admin/books/7/edit", dict(data, price=2000), origin="/admin/books/7/edit")
        self.assertIn("Đã lưu sách", result.text)
        self.assertEqual(list(fol.iterdir()), [kept_cover])
        with self.app.app_context():
            self.assertEqual(db.session.get(Book, 7).image, kept_cover.name)

    def test_case_insensitive_duplicates_and_search(self):
        result = self.post("/admin/books/new", dict(name="CƠ SỞ DỮ LIỆU", author="A", category_id=1,
                                                     price=1500, stock=0), origin="/admin/books/new")
        self.assertIn("Tên sách đã tồn tại", result.text)
        result = self.post("/admin/categories", {"name": "LẬP TRÌNH"}, origin="/admin/categories")
        self.assertIn("Tên danh mục đã tồn tại", result.text)
        result = self.client.get("/books", query_string={"q": "NGUYỄN VĂN A"})
        self.assertIn("Lập trình Python cơ bản", result.text)
        self.assertNotIn("Giáo trình Flask", result.text)

    def test_pagination_and_order_filter_totals(self):
        with self.app.app_context():
            for i in range(11):
                db.session.add(Order(name="Nguyễn Demo", phone="0912345678", email="", address="Huế",
                                     note="", payment="cash", shipping_fee=0, total=11000, status=PENDING))
            db.session.add(Order(name="Khách khác", phone="0912345678", email="", address="Huế",
                                 note="", payment="cash", shipping_fee=0, total=99000, status=CANCELLED))
            db.session.commit()
        result = self.client.get("/admin/orders", query_string={"q": "NGUYỄN", "status": PENDING, "page": 2})
        self.assertIn("11 đơn · Tổng giá trị", result.text)
        self.assertIn("121.000 đ", result.text)
        self.assertIn('page=1&amp;status=', result.text)
        self.assertIn("Chờ xác nhận (11)", result.text)
        self.assertEqual(result.text.count('stretched-link'), 1)
        result = self.client.get("/admin/books", query_string={"page": 2, "stock": ""})
        self.assertIn("Hiển thị 6–6 / 6", result.text)
        self.assertEqual(self.client.get("/admin/categories").status_code, 200)
