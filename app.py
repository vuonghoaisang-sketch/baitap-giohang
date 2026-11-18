import os
import sqlite3
from datetime import timezone
from pathlib import Path
from secrets import token_hex
from zoneinfo import ZoneInfo

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

from catalog import name_key
from models import PAYMENTS, TRANSITIONS, db


@event.listens_for(Engine, "connect")
def enable_foreign_keys(connection, record):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.create_function("casefold", 1, name_key, deterministic=True)


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI="sqlite:///bookstore.sqlite",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=3 * 1024 * 1024,
        UPLOAD_FOLDER=Path(app.instance_path) / "covers",
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.config.update(config or {})
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        key_path = Path(app.instance_path) / "secret.key"
        try:
            with key_path.open("x", encoding="ascii") as key_file:
                key_file.write(token_hex(32))
        except FileExistsError:
            pass
        app.config["SECRET_KEY"] = key_path.read_text(encoding="ascii").strip()

    db.init_app(app)
    Migrate(app, db)
    CSRFProtect(app)

    from shop import shop
    from admin import admin
    from seed import SAMPLE_BOOKS, seed
    sample_covers = {name_key(row[0]): f"covers/sample-{index}.png"
                     for index, row in enumerate(SAMPLE_BOOKS, 1)}
    app.register_blueprint(shop)
    app.register_blueprint(admin)
    app.cli.add_command(seed)

    @app.template_filter("vnd")
    def vnd(value):
        return f"{value:,}".replace(",", ".") + " đ"

    @app.template_filter("local_time")
    def local_time(value):
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%d/%m/%Y %H:%M")

    @app.context_processor
    def shared_context():
        return dict(cart_count=sum(session.get("cart", {}).values()), payments=PAYMENTS,
                    statuses=TRANSITIONS, sample_covers=sample_covers)

    @app.errorhandler(CSRFError)
    def invalid_csrf(error):
        return render_template("error.html", message="Phiên biểu mẫu không hợp lệ. Hãy tải lại trang và thử lại."), 400

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="Không tìm thấy trang."), 404

    @app.errorhandler(413)
    def large_file(error):
        flash("Ảnh tối đa 2 MB.", "danger")
        return redirect(request.path if request.endpoint == "admin.book_form" else url_for("shop.books"))

    return app
