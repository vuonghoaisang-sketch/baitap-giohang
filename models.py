from datetime import datetime, timezone
from secrets import token_urlsafe

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
PENDING = "Chờ xác nhận"
SHIPPING = "Đang giao"
COMPLETE = "Hoàn tất"
CANCELLED = "Đã huỷ"
TRANSITIONS = {
    PENDING: (SHIPPING, CANCELLED),
    SHIPPING: (COMPLETE, CANCELLED),
    COMPLETE: (),
    CANCELLED: (),
}
PAYMENTS = {"cash": "Tiền mặt khi nhận hàng", "transfer": "Chuyển khoản"}


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    name_key = db.Column(db.String(240), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False, default="")


class Book(db.Model):
    __table_args__ = (db.CheckConstraint("price >= 1000 AND stock >= 0", name="book_price_stock"),)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    name_key = db.Column(db.String(320), nullable=False, unique=True)
    author = db.Column(db.String(160), nullable=False)
    publisher = db.Column(db.String(160), nullable=False, default="")
    year = db.Column(db.Integer)
    category_id = db.Column(db.ForeignKey("category.id"), nullable=False, index=True)
    price = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    image = db.Column(db.String(100))
    category = db.relationship(Category)


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    view_token = db.Column(db.String(48), nullable=False, unique=True, default=token_urlsafe)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    note = db.Column(db.Text, nullable=False)
    payment = db.Column(db.String(12), nullable=False)
    shipping_fee = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, index=True, default=PENDING)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    completed_at = db.Column(db.DateTime)
    items = db.relationship("OrderItem", order_by="OrderItem.id", cascade="all, delete-orphan")
    history = db.relationship("OrderHistory", order_by="OrderHistory.id", cascade="all, delete-orphan")


class OrderItem(db.Model):
    __table_args__ = (db.CheckConstraint("quantity > 0 AND unit_price >= 1000", name="item_price_quantity"),)
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.ForeignKey("orders.id"), nullable=False, index=True)
    book_id = db.Column(db.ForeignKey("book.id"), nullable=False, index=True)
    book_name = db.Column(db.String(160), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)


class OrderHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.ForeignKey("orders.id"), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False)
    changed_at = db.Column(db.DateTime, nullable=False, default=utc_now)
