import os
import click
from flask import Flask, render_template, redirect, url_for, flash, request, session
from models import db, User, Product, Cart, Order, OrderItem
from forms import RegisterForm, LoginForm, CheckoutForm, ProductEditForm
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from supabase import create_client
except ImportError:
    create_client = None

# ---- APP SETUP ----
def load_local_env():
    """Load variables from a local .env file when python-dotenv is unavailable."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


if load_dotenv:
    load_dotenv()
else:
    load_local_env()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

ADMIN_EMAILS = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "vishwarajharod31@gmail.com").split(",")
    if email.strip()
}


def build_supabase_db_url():
    raw_db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if raw_db_url:
        return raw_db_url.replace("[YOUR-PASSWORD]", quote_plus(os.getenv("SUPABASE_DB_PASSWORD", "")))

    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    db_user = os.getenv("SUPABASE_DB_USER", "postgres")
    db_name = os.getenv("SUPABASE_DB_NAME", "postgres")
    db_host = os.getenv("SUPABASE_DB_HOST")
    db_port = os.getenv("SUPABASE_DB_PORT", "5432")

    if project_ref and db_password:
        resolved_host = db_host or f"db.{project_ref}.supabase.co"
        encoded_password = quote_plus(db_password)
        return f"postgresql://{db_user}:{encoded_password}@{resolved_host}:{db_port}/{db_name}"

    return raw_db_url


db_url = build_supabase_db_url()

if not db_url:
    raise RuntimeError(
        "Supabase database is required. Set DATABASE_URL or SUPABASE_DB_URL in ecommerce/.env."
    )

if "supabase.co" not in db_url and "pooler.supabase.com" not in db_url:
    raise RuntimeError(
        "DATABASE_URL does not look like a Supabase Postgres connection string."
    )

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


def get_supabase_client():
    """Return a Supabase client when URL and key are configured."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not create_client:
        return None
    if not supabase_url or not supabase_key:
        return None

    return create_client(supabase_url, supabase_key)


app.extensions["supabase"] = {"client": get_supabase_client()}


def sync_admin_status(user):
    """Keep configured admin emails in sync with the database flag."""
    if not user:
        return False

    should_be_admin = user.email.lower() in ADMIN_EMAILS
    if user.is_admin != should_be_admin:
        user.is_admin = should_be_admin
        db.session.commit()
        return True

    return False


def initialize_database():
    """Create tables, backfill admin column, and seed starter products."""
    db.create_all()
    inspector = inspect(db.engine)
    user_columns = {column["name"] for column in inspector.get_columns("user")}

    if "is_admin" not in user_columns:
        with db.engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE \"user\" ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT false"
            ))
            conn.commit()
    seed_products()




# ---- LOGIN MANAGER SETUP ----
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # redirect to /login if not authenticated
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---- SEED PRODUCTS ----
def seed_products():
    """Add 6 sample products to the database on first run."""
    if Product.query.count() == 0:
        products = [
            Product(name="Apple AirPods Pro 3",
                    description="Premium noise-cancelling wireless headphones with 30-hour battery life and foldable design.",
                    price=2399.00, image_url="https://vsprod.vijaysales.com/media/catalog/product/2/4/245237.jpg?optimize=medium&fit=bounds&height=500&width=500", stock=15),
            Product(name="Smart Watch",
                    description="Feature-rich smartwatch with health tracking, heart rate monitor, and instant notifications.",
                    price=3999.00, image_url="https://picsum.photos/seed/smartwatch/400/300", stock=10),
            Product(name="Laptop Backpack",
                    description="Waterproof 30L laptop backpack with dedicated laptop compartment and USB charging port.",
                    price=1299.00, image_url="https://picsum.photos/seed/backpack/400/300", stock=20),
            Product(name="Mechanical Keyboard",
                    description="Full RGB mechanical keyboard with tactile switches, anti-ghosting and aluminum frame.",
                    price=1899.00, image_url="https://picsum.photos/seed/keyboard/400/300", stock=8),
            Product(name="Portable Speaker",
                    description="360-degree surround sound portable Bluetooth speaker, IPX7 waterproof, 12-hour playtime.",
                    price=1599.00, image_url="https://picsum.photos/seed/speaker/400/300", stock=12),
            Product(name="Webcam HD 1080p",
                    description="Full HD 1080p webcam with built-in stereo microphone, wide-angle lens, plug and play.",
                    price=9659.00, image_url="https://picsum.photos/seed/webcam/400/300", stock=25),
        ]
        db.session.add_all(products)
        db.session.commit()

# ---- HOME — Product Listing ----
@app.route("/")
def home():
    products = Product.query.all()
    return render_template("index.html", products=products)

# ---- PRODUCT DETAIL ----
@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("product.html", product=product)

# ---- REGISTER ----
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter(
            (User.username == form.username.data) | (User.email == form.email.data)
        ).first()
        if existing_user:
            flash("Username or email already exists. Please use a different one.", "warning")
            return render_template("register.html", form=form)

        hashed_pw = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_pw,
            is_admin=form.email.data.lower() in ADMIN_EMAILS
        )
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Username or email already exists. Please use a different one.", "warning")
            return render_template("register.html", form=form)
        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)

# ---- LOGIN ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            sync_admin_status(user)
            login_user(user)
            flash("Logged in successfully!", "success")
            next_page = request.args.get('next')  # redirect back if came from protected page
            if next_page:
                return redirect(next_page)
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html", form=form)

# ---- LOGOUT ----
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

# ---- ADD TO CART ----
@app.route("/cart/add/<int:product_id>")
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    if product.stock < 1:
        flash(f'"{product.name}" is out of stock.', "warning")
        return redirect(request.referrer or url_for("home"))

    # If item already in cart, increment quantity
    cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item and cart_item.quantity >= product.stock:
        flash(f'Only {product.stock} unit(s) of "{product.name}" are available.', "warning")
        return redirect(request.referrer or url_for("home"))
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = Cart(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(cart_item)
    db.session.commit()
    flash(f'"{product.name}" added to cart!', "success")
    return redirect(request.referrer or url_for("home"))

# ---- VIEW CART ----
@app.route("/cart")
@login_required
def view_cart():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total)

# ---- UPDATE CART QUANTITY ----
@app.route("/cart/update/<int:cart_id>", methods=["POST"])
@login_required
def update_cart(cart_id):
    cart_item = Cart.query.get_or_404(cart_id)
    if cart_item.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("view_cart"))
    quantity = int(request.form.get("quantity", 1))
    if quantity < 1:
        db.session.delete(cart_item)  # remove if qty is 0
    else:
        if quantity > cart_item.product.stock:
            flash(f"Only {cart_item.product.stock} unit(s) are available for {cart_item.product.name}.", "warning")
            return redirect(url_for("view_cart"))
        cart_item.quantity = quantity
    db.session.commit()
    return redirect(url_for("view_cart"))

# ---- REMOVE FROM CART ----
@app.route("/cart/remove/<int:cart_id>")
@login_required
def remove_from_cart(cart_id):
    cart_item = Cart.query.get_or_404(cart_id)
    if cart_item.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("view_cart"))
    db.session.delete(cart_item)
    db.session.commit()
    flash("Item removed from cart.", "info")
    return redirect(url_for("view_cart"))

# ---- CHECKOUT — Collect Shipping Address ----
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("view_cart"))
    form = CheckoutForm()
    if form.validate_on_submit():
        # Store shipping address in session to use on payment page
        session['shipping_address'] = (
            f"{form.full_name.data}, {form.address.data}, "
            f"{form.city.data} - {form.pincode.data}, Ph: {form.phone.data}"
        )
        return redirect(url_for("payment"))
    return render_template("checkout.html", form=form)

# ---- PAYMENT — Cash on Delivery ----
@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("view_cart"))

    shipping_address = session.get('shipping_address')
    if not shipping_address:
        flash("Please fill in your shipping details first.", "warning")
        return redirect(url_for("checkout"))

    total = sum(item.product.price * item.quantity for item in cart_items)

    if request.method == "POST":
        for item in cart_items:
            if item.quantity > item.product.stock:
                flash(f"{item.product.name} does not have enough stock for this order.", "warning")
                return redirect(url_for("view_cart"))

        order = Order(
            user_id=current_user.id,
            total_price=total,
            shipping_address=shipping_address,
            status="Cash on Delivery",
            created_at=datetime.utcnow()
        )
        db.session.add(order)
        db.session.flush()

        for item in cart_items:
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.product.price
            ))
            item.product.stock -= item.quantity

        Cart.query.filter_by(user_id=current_user.id).delete()
        session.pop('shipping_address', None)
        db.session.commit()

        flash("Order placed successfully! Pay on delivery.", "success")
        return redirect(url_for("order_confirmation", order_id=order.id))

    return render_template("payment.html", total=total, cart_items=cart_items)

# ---- ORDER CONFIRMATION ----
@app.route("/order/confirmation/<int:order_id>")
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    # Ensure the order belongs to the logged-in user
    if order.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("home"))
    return render_template("order_confirmation.html", order=order)

# ---- ADMIN: DASHBOARD ----
@app.route("/admin")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Admin access required.", "danger")
        return redirect(url_for("home"))
    products = Product.query.all()
    low_stock_products = [product for product in products if 0 < product.stock <= 5]
    in_stock_count = sum(1 for product in products if product.stock > 0)
    out_of_stock_count = sum(1 for product in products if product.stock == 0)
    total_units = sum(product.stock for product in products)
    return render_template(
        "admin_dashboard.html",
        products=products,
        low_stock_products=low_stock_products,
        in_stock_count=in_stock_count,
        out_of_stock_count=out_of_stock_count,
        total_units=total_units,
    )

# ---- ADMIN: ADD PRODUCT ----
@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def add_product():
    if not current_user.is_admin:
        flash("Admin access required.", "danger")
        return redirect(url_for("home"))
    form = ProductEditForm()
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            image_url=form.image_url.data,
            stock=form.stock.data
        )
        db.session.add(product)
        db.session.commit()
        flash(f'"{product.name}" added successfully!', "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("add_product.html", form=form)

# ---- ADMIN: EDIT PRODUCT ----
@app.route("/admin/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    if not current_user.is_admin:
        flash("Admin access required.", "danger")
        return redirect(url_for("home"))
    product = Product.query.get_or_404(product_id)
    form = ProductEditForm(obj=product)
    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.image_url = form.image_url.data
        product.stock = form.stock.data
        db.session.commit()
        flash(f'"{product.name}" updated successfully!', "success")
        return redirect(url_for("home"))
    return render_template("edit_product.html", form=form, product=product)

# ---- CLI: PROMOTE USER TO ADMIN ----
@app.cli.command("set-admin")
@click.argument("username")
def set_admin(username):
    """Grant admin privileges to a user by username."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            click.echo(f"User '{username}' not found.")
            return
        user.is_admin = True
        db.session.commit()
        click.echo(f"'{username}' is now an admin.")


@app.cli.command("init-db")
def init_db_command():
    """Create tables and seed starter data."""
    with app.app_context():
        initialize_database()
        click.echo("Database initialized.")

# ---- DB INIT + SEED ----
if __name__ == "__main__":
    with app.app_context():
        initialize_database()
    app.run(debug=True)
