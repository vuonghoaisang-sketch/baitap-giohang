from pathlib import Path
from secrets import token_urlsafe

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from catalog import book_filters, categories
from forms import CheckoutForm
from models import Book, Order, OrderHistory, OrderItem, PENDING, db

shop = Blueprint("shop", __name__)


@shop.get("/")
def index():
    return redirect(url_for(".books"))


@shop.get("/covers/<filename>")
def cover(filename):
    return send_from_directory(Path(current_app.config["UPLOAD_FOLDER"]), filename)


@shop.get("/books")
def books():
    query, filters = book_filters()
    books = db.session.scalars(query.order_by(Book.id)).all()
    return render_template("books.html", books=books, categories=categories(), filters=filters)


@shop.get("/books/<int:book_id>")
def book_detail(book_id):
    book = db.get_or_404(Book, book_id)
    in_cart = session.get("cart", {}).get(str(book_id), 0)
    return render_template("book_detail.html", book=book, in_cart=in_cart)


@shop.post("/books/<int:book_id>/add")
def add_book(book_id):
    book = db.get_or_404(Book, book_id)
    cart = session.get("cart", {})
    key = str(book.id)
    quantity = request.form.get("quantity", type=int)
    if quantity is None or not 1 <= quantity <= book.stock - cart.get(key, 0):
        flash(f"Số lượng thêm không hợp lệ theo tồn kho của «{book.name}».", "danger")
    else:
        cart[key] = cart.get(key, 0) + quantity
        session["cart"] = cart
        session["checkout_token"] = token_urlsafe()
        flash(f"Đã thêm {quantity} × {book.name} vào giỏ hàng.", "success")
    if request.form.get("source") == "detail":
        return redirect(url_for(".book_detail", book_id=book.id))
    return redirect(url_for(".books", q=request.form.get("q", ""),
                            category=request.form.get("category", type=int)))


def cart_lines(cart):
    if not cart:
        return []
    books = db.session.scalars(db.select(Book).where(Book.id.in_(map(int, cart)))).all()
    by_id = {str(book.id): book for book in books}
    return [(by_id.get(key), quantity, key) for key, quantity in cart.items()]


@shop.get("/cart")
def show_cart():
    lines = cart_lines(session.get("cart", {}))
    subtotal = sum(book.price * quantity for book, quantity, _ in lines if book)
    return render_template("cart.html", lines=lines, subtotal=subtotal)


@shop.post("/cart")
def change_cart():
    cart = session.get("cart", {})
    action = request.form.get("action")
    key = request.form.get("book_id", "")
    if action == "clear":
        cart = {}
    elif key not in cart or action not in {"plus", "minus", "remove"}:
        flash("Thao tác giỏ hàng không hợp lệ.", "danger")
        return redirect(url_for(".show_cart"))
    elif action == "remove" or (action == "minus" and cart[key] == 1):
        del cart[key]
    elif action == "minus":
        cart[key] -= 1
    else:
        book = db.session.get(Book, int(key))
        if book is None or cart[key] >= book.stock:
            flash("Không thể tăng số lượng theo tồn kho hiện tại.", "danger")
            return redirect(url_for(".show_cart"))
        cart[key] += 1
    session["cart"] = cart
    session["checkout_token"] = token_urlsafe()
    flash("Đã cập nhật giỏ hàng.", "success")
    return redirect(url_for(".show_cart"))


def shipping_fee(subtotal):
    return 0 if subtotal >= 200_000 else 20_000


@shop.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Giỏ hàng trống.", "warning")
        return redirect(url_for(".show_cart"))
    form = CheckoutForm()
    submitted = form.validate_on_submit()
    token = session.get("checkout_token")
    if request.method == "POST" and (not token or request.form.get("checkout_token") != token):
        flash("Giỏ hàng đã thay đổi. Hãy kiểm tra lại đơn hàng.", "warning")
        return redirect(url_for(".checkout"))
    if not token:
        token = session["checkout_token"] = token_urlsafe()

    try:
        if submitted:
            # Khóa ghi SQLite trước khi đọc giá và tồn kho để xử lý các đơn đồng thời.
            db.session.execute(text("BEGIN IMMEDIATE"))
            existing = db.session.scalar(db.select(Order.id).where(Order.view_token == token))
            if existing is not None:
                db.session.rollback()
                session.pop("cart", None)
                session.pop("checkout_token", None)
                return redirect(url_for(".order_success", token=token))
        lines = cart_lines(cart)
        for book, quantity, key in lines:
            if book is None or (submitted and quantity > book.stock):
                db.session.rollback()
                name = book.name if book else f"Sách #{key}"
                flash(f"Không đủ hàng cho «{name}». Hãy điều chỉnh giỏ hàng.", "danger")
                return redirect(url_for(".show_cart"))

        subtotal = sum(book.price * quantity for book, quantity, _ in lines)
        fee = shipping_fee(subtotal)
        if submitted:
            order = Order(**{field: getattr(form, field).data for field in
                             ("name", "phone", "email", "address", "note", "payment")},
                          view_token=token, shipping_fee=fee, total=subtotal + fee)
            order.history.append(OrderHistory(status=PENDING))
            for book, quantity, _ in lines:
                order.items.append(OrderItem(book_id=book.id, book_name=book.name,
                                             quantity=quantity, unit_price=book.price))
                book.stock -= quantity
            db.session.add(order)
            db.session.commit()
            session.pop("cart", None)
            session.pop("checkout_token", None)
            return redirect(url_for(".order_success", token=token))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Không thể xử lý đơn hàng")
        flash("Chưa thể lưu đơn hàng. Vui lòng thử lại.", "danger")
        return redirect(url_for(".show_cart"))

    return render_template("checkout.html", form=form, lines=lines, subtotal=subtotal, fee=fee,
                           checkout_token=token)


@shop.get("/orders/<token>")
def order_success(token):
    order = db.first_or_404(db.select(Order).where(Order.view_token == token))
    return render_template("order_success.html", order=order), 200, {
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
    }
