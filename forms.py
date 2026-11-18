from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileSize
from wtforms import IntegerField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, InputRequired, Length, NumberRange, Optional, Regexp, ValidationError

from models import PAYMENTS


def trimmed(value):
    return value.strip() if value else ""


def text_field(field, label, limit, required=False, extra=()):
    validators = [DataRequired(message="Vui lòng nhập thông tin này.") if required else Optional()]
    return field(label, filters=[trimmed], validators=[
        *validators, Length(max=limit, message=f"Tối đa {limit} ký tự."), *extra
    ])


class CheckoutForm(FlaskForm):
    name = text_field(StringField, "Họ tên", 120, True)
    phone = text_field(StringField, "Số điện thoại", 10, True, [
        Regexp(r"0[0-9]{9}\Z", message="Nhập 10 chữ số bắt đầu bằng 0.")
    ])
    email = text_field(StringField, "Email", 254, extra=[Email(message="Email không hợp lệ.")])
    address = text_field(TextAreaField, "Địa chỉ giao hàng", 300, True)
    note = text_field(TextAreaField, "Ghi chú", 1000)
    payment = RadioField("Thanh toán", choices=list(PAYMENTS.items()), default="cash",
                         validators=[InputRequired(message="Chọn phương thức thanh toán.")])


def current_year(form, field):
    if field.data is not None and not 1900 <= field.data <= date.today().year:
        raise ValidationError("Năm xuất bản phải từ 1900 đến năm hiện tại.")


class BookForm(FlaskForm):
    name = text_field(StringField, "Tên sách", 160, True)
    author = text_field(StringField, "Tác giả", 160, True)
    publisher = text_field(StringField, "Nhà xuất bản", 160)
    category_id = SelectField("Danh mục", coerce=int)
    year = IntegerField("Năm xuất bản", validators=[Optional(), current_year])
    price = IntegerField("Giá (đồng)", validators=[
        InputRequired(), NumberRange(min=1000, max=2_000_000_000, message="Giá từ 1.000 đến 2.000.000.000 đ.")
    ])
    stock = IntegerField("Tồn kho", validators=[
        InputRequired(), NumberRange(min=0, max=2_000_000_000, message="Tồn kho từ 0 đến 2.000.000.000.")
    ])
    description = text_field(TextAreaField, "Mô tả", 5000)
    image = FileField("Ảnh bìa", validators=[
        FileAllowed(["jpg", "jpeg", "png", "webp"], "Chỉ nhận JPG, PNG hoặc WEBP."),
        FileSize(max_size=2 * 1024 * 1024, message="Ảnh tối đa 2 MB."),
    ])


class CategoryForm(FlaskForm):
    name = text_field(StringField, "Tên danh mục", 120, True)
    description = text_field(TextAreaField, "Mô tả", 1000)
