import click
from flask.cli import with_appcontext

from catalog import name_key
from models import Book, Category, db

SAMPLE_BOOKS = [
    ("Lập trình Python cơ bản", "Nguyễn Văn A", "Lập trình", 95000, 30, "NXB Đại học Huế", 2024,
     "Nhập môn Python qua biến, hàm, cấu trúc dữ liệu và các bài tập thực hành."),
    ("Giáo trình Flask", "Miguel Grinberg", "Lập trình", 120000, 20, "O’Reilly Media", 2018,
     "Xây dựng ứng dụng web với Flask, từ định tuyến đến biểu mẫu và cơ sở dữ liệu."),
    ("Cơ sở dữ liệu", "Trần Văn B", "Cơ sở dữ liệu", 85000, 0, "", None,
     "Giới thiệu mô hình quan hệ, thiết kế bảng và truy vấn SQL."),
    ("Pro Git", "Scott Chacon", "Công cụ", 150000, 15, "Apress", 2014,
     "Tìm hiểu cách quản lý phiên bản, làm việc với nhánh và phối hợp qua Git."),
    ("Mạng máy tính", "Lê Văn C", "Mạng", 110000, 12, "", None,
     "Trình bày các giao thức và nguyên lý truyền dữ liệu trong mạng máy tính."),
    ("Clean Code", "Robert C. Martin", "Kỹ năng lập trình", 180000, 5, "Prentice Hall", 2008,
     "Các ví dụ về cách đặt tên, tổ chức hàm và cải thiện khả năng đọc mã nguồn."),
]


@click.command("seed")
@with_appcontext
def seed():
    """Thêm danh mục và sách mẫu còn thiếu."""
    categories = {}
    for name in dict.fromkeys([row[2] for row in SAMPLE_BOOKS] + ["Thiết kế"]):
        category = db.session.scalar(db.select(Category).where(Category.name_key == name_key(name)))
        if category is None:
            category = Category(name=name, name_key=name_key(name))
            db.session.add(category)
        categories[name] = category
    count = 0
    for name, author, category, price, stock, publisher, year, description in SAMPLE_BOOKS:
        if db.session.scalar(db.select(Book.id).where(Book.name_key == name_key(name))) is None:
            db.session.add(Book(name=name, name_key=name_key(name), author=author,
                                category=categories[category], price=price, stock=stock,
                                publisher=publisher, year=year, description=description))
            count += 1
    db.session.commit()
    click.echo(f"Đã thêm {count} đầu sách mẫu.")
