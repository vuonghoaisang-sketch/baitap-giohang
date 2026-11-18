from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from PIL import Image
from sqlalchemy import String, cast, func, or_, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from catalog import book_filters, categories, name_key
from forms import BookForm, CategoryForm
from models import Book, CANCELLED, COMPLETE, Category, Order, OrderHistory, OrderItem, PENDING, TRANSITIONS, db, utc_now

admin = Blueprint("admin", __name__, url_prefix="/admin")


def pending_count():
    return db.session.scalar(db.select(func.count(Order.id)).where(Order.status == PENDING))


@admin.context_processor
def sidebar():
    return {"pending_count": pending_count()}


@admin.get("")
def dashboard():
    local_zone = ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(local_zone)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    start, end = (value.astimezone(timezone.utc).replace(tzinfo=None) for value in (start, end))
    revenue = db.session.scalar(db.select(func.coalesce(func.sum(Order.total), 0)).where(
        Order.status == COMPLETE, Order.completed_at >= start, Order.completed_at < end
    ))
    book_count = db.session.scalar(db.select(func.count(Book.id)))
    low_count = db.session.scalar(db.select(func.count(Book.id)).where(Book.stock <= 5))
    low_books = db.session.scalars(db.select(Book).where(Book.stock <= 5).order_by(Book.stock, Book.id)).all()
    recent = db.session.scalars(db.select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(5)).all()
    return render_template("admin/dashboard.html", book_count=book_count, revenue=revenue,
                           low_count=low_count, low_books=low_books, recent=recent, month=now.month)


@admin.get("/books")
def books():
    query, filters = book_filters()
    filters["stock"] = request.args.get("stock", "")
    conditions = {"available": Book.stock > 0, "low": Book.stock.between(1, 5), "out": Book.stock == 0}
    if filters["stock"] in conditions:
        query = query.where(conditions[filters["stock"]])
    page = db.paginate(query.order_by(Book.id.desc()), per_page=5)
    used = set(db.session.scalars(db.select(OrderItem.book_id).where(
        OrderItem.book_id.in_([book.id for book in page.items])
    )))
    return render_template("admin/books.html", page=page, categories=categories(), filters=filters, used=used)


def remove_cover(filename):
    if not filename or Path(filename).name != filename:
        return
    try:
        (Path(current_app.config["UPLOAD_FOLDER"]) / filename).unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Không thể dọn ảnh bìa %s", filename, exc_info=True)


def save_cover(upload):
    extensions = {"JPEG": {".jpg", ".jpeg"}, "PNG": {".png"}, "WEBP": {".webp"}}
    suffix = Path(upload.filename).suffix.lower()
    with Image.open(upload.stream, formats=list(extensions)) as cover:
        if suffix not in extensions[cover.format]:
            raise ValueError("Phần mở rộng không khớp nội dung ảnh.")
        cover.verify()
    upload.stream.seek(0)
    # Nạp pixel để phát hiện ảnh hỏng và lưu lại ảnh, loại bỏ dữ liệu thừa.
    with Image.open(upload.stream, formats=list(extensions)) as cover:
        pixels = cover.convert("RGB" if cover.format == "JPEG" else "RGBA")
        filename = uuid4().hex + suffix
        folder = Path(current_app.config["UPLOAD_FOLDER"])
        folder.mkdir(parents=True, exist_ok=True)
        try:
            pixels.save(folder / filename, format=cover.format)
        except OSError:
            remove_cover(filename)
            raise
    return filename


@admin.route("/books/new", methods=["GET", "POST"])
@admin.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def book_form(book_id=None):
    try:
        if request.method == "POST":
            db.session.execute(text("BEGIN IMMEDIATE"))
    except SQLAlchemyError:
        db.session.rollback()
        flash("Cơ sở dữ liệu đang bận. Vui lòng thử lại.", "danger")
        return redirect(url_for(".books"))

    book = db.get_or_404(Book, book_id) if book_id is not None else None
    form = BookForm(obj=book)
    form.category_id.choices = [(category.id, category.name) for category in categories()]
    if form.validate_on_submit():
        key = name_key(form.name.data)
        duplicate = db.session.scalar(db.select(Book.id).where(Book.name_key == key, Book.id != book_id))
        if duplicate is not None:
            form.name.errors.append("Tên sách đã tồn tại.")
        else:
            new_cover = None
            if form.image.raw_data:
                try:
                    new_cover = save_cover(form.image.data)
                except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
                    form.image.errors.append("Không thể lưu ảnh. Hãy chọn tệp JPG, PNG hoặc WEBP hợp lệ.")
            if not form.image.errors:
                if book is None:
                    book = Book()
                    db.session.add(book)
                old_cover = book.image
                for field in ("name", "author", "publisher", "year", "category_id", "price", "stock", "description"):
                    setattr(book, field, getattr(form, field).data)
                book.name_key = key
                if new_cover:
                    book.image = new_cover
                try:
                    db.session.commit()
                except SQLAlchemyError:
                    db.session.rollback()
                    remove_cover(new_cover)
                    flash("Không thể lưu sách. Vui lòng thử lại.", "danger")
                    return redirect(url_for(".books"))
                if new_cover:
                    remove_cover(old_cover)
                flash("Đã lưu sách.", "success")
                return redirect(url_for(".books"))
    return render_template("admin/book_form.html", form=form, book=book)


@admin.post("/books/<int:book_id>/delete")
def delete_book(book_id):
    book = db.get_or_404(Book, book_id)
    if db.session.scalar(db.select(OrderItem.id).where(OrderItem.book_id == book_id).limit(1)) is not None:
        flash("Không thể xoá sách đã có trong đơn hàng.", "danger")
    else:
        filename = book.image
        try:
            db.session.delete(book)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Không thể xoá sách đã có trong đơn hàng.", "danger")
        else:
            remove_cover(filename)
            flash("Đã xoá sách.", "success")
    return redirect(url_for(".books"))


@admin.route("/categories", methods=["GET", "POST"])
@admin.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
def category_list(category_id=None):
    category = db.get_or_404(Category, category_id) if category_id is not None else None
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        key = name_key(form.name.data)
        if db.session.scalar(db.select(Category.id).where(Category.name_key == key, Category.id != category_id)) is not None:
            form.name.errors.append("Tên danh mục đã tồn tại.")
        else:
            target = category or Category()
            target.name = form.name.data
            target.name_key = key
            target.description = form.description.data
            db.session.add(target)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                form.name.errors.append("Tên danh mục đã tồn tại.")
            else:
                flash("Đã lưu danh mục.", "success")
                return redirect(url_for(".category_list"))
    rows = db.session.execute(db.select(Category, func.count(Book.id))
                              .outerjoin(Book).group_by(Category.id).order_by(Category.name)).all()
    return render_template("admin/categories.html", rows=rows, form=form, category=category)


def category_book_count(category_id):
    return db.session.scalar(db.select(func.count(Book.id)).where(Book.category_id == category_id))


@admin.post("/categories/<int:category_id>/delete")
def delete_category(category_id):
    category = db.get_or_404(Category, category_id)
    count = category_book_count(category_id)
    if not count:
        try:
            db.session.delete(category)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            count = category_book_count(category_id)
        else:
            flash("Đã xoá danh mục.", "success")
            return redirect(url_for(".category_list"))
    flash(f"Không thể xoá danh mục vì còn {count} đầu sách.", "danger")
    return redirect(url_for(".category_list"))


@admin.get("/orders")
def orders():
    counts = dict(db.session.execute(db.select(Order.status, func.count(Order.id)).group_by(Order.status)).all())
    filters = {"status": request.args.get("status", ""), "q": request.args.get("q", "").strip()}
    query = db.select(Order)
    if filters["status"] in TRANSITIONS:
        query = query.where(Order.status == filters["status"])
    else:
        filters["status"] = ""
    if filters["q"]:
        term = filters["q"]
        query = query.where(or_(
            cast(Order.id, String).contains(term.lstrip("#"), autoescape=True) if term.lstrip("#") else db.false(),
            func.casefold(Order.name).contains(name_key(term), autoescape=True),
            Order.phone.contains(term, autoescape=True),
        ))
    matching = query.subquery()
    total = db.session.scalar(db.select(func.coalesce(func.sum(matching.c.total), 0)))
    page = db.paginate(query.order_by(Order.created_at.desc(), Order.id.desc()), per_page=10)
    return render_template("admin/orders.html", counts=counts, page=page, filters=filters, total=total)


@admin.get("/orders/<int:order_id>")
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    return render_template("admin/order_detail.html", order=order, transitions=TRANSITIONS[order.status])


@admin.post("/orders/<int:order_id>/status")
def change_status(order_id):
    target = request.form.get("status")
    try:
        # Đọc trạng thái sau khi lấy khóa ghi, để hai yêu cầu huỷ không thể cùng hoàn kho.
        db.session.execute(text("BEGIN IMMEDIATE"))
        order = db.get_or_404(Order, order_id)
        if target not in TRANSITIONS[order.status]:
            db.session.rollback()
            flash("Chuyển trạng thái không hợp lệ.", "danger")
        else:
            now = utc_now()
            if target == CANCELLED:
                for item in order.items:
                    book = db.session.get(Book, item.book_id)
                    book.stock += item.quantity
            if target == COMPLETE:
                order.completed_at = now
            order.status = target
            order.history.append(OrderHistory(status=target, changed_at=now))
            db.session.commit()
            flash(f"Đã cập nhật đơn #{order_id} sang «{target}».", "success")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Không thể cập nhật đơn")
        flash("Không thể cập nhật đơn. Vui lòng thử lại.", "danger")
    return redirect(url_for(".order_detail", order_id=order_id))
