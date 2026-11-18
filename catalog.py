from unicodedata import normalize

from flask import request
from sqlalchemy import func, or_

from models import Book, Category, db


def name_key(value):
    return normalize("NFC", value).casefold()


def categories():
    return db.session.scalars(db.select(Category).order_by(Category.name)).all()


def book_filters():
    filters = {
        "q": request.args.get("q", "").strip(),
        "category": request.args.get("category", type=int),
    }
    query = db.select(Book)
    if filters["q"]:
        term = name_key(filters["q"])
        # SQLite lower() chỉ xử lý ASCII. Hàm casefold hỗ trợ tìm tên tác giả tiếng Việt.
        query = query.where(or_(
            Book.name_key.contains(term, autoescape=True),
            func.casefold(Book.author).contains(term, autoescape=True),
        ))
    if filters["category"]:
        query = query.where(Book.category_id == filters["category"])
    return query, filters
