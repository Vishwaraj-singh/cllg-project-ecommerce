from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange

# ---- REGISTER FORM ----
class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=20)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField("Register")

# ---- LOGIN FORM ----
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# ---- CHECKOUT FORM ----
class CheckoutForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired()])
    address = StringField("Address", validators=[DataRequired()])
    city = StringField("City", validators=[DataRequired()])
    pincode = StringField("Pincode", validators=[DataRequired(), Length(min=6, max=6)])
    phone = StringField("Phone Number", validators=[DataRequired(), Length(min=10, max=10)])
    submit = SubmitField("Continue to Payment")

# ---- PRODUCT EDIT FORM (Admin) ----
class ProductEditForm(FlaskForm):
    name = StringField("Product Name", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[DataRequired()])
    price = FloatField("Price (₹)", validators=[DataRequired(), NumberRange(min=0)])
    image_url = StringField("Image URL", validators=[DataRequired()])
    stock = IntegerField("Stock", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Save Changes")
