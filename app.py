import os
from flask import Flask, render_template, redirect, url_for, flash, request, session
from models import db, User, Product, Cart, Order, OrderItem
from forms import RegisterForm, LoginForm, CheckoutForm, ProductEditForm
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# ---- APP SETUP ----
app = Flask(__name__)
db_url = os.environ.get("postgresql://ecommerce_gauc_user:YpBiKGumVCTr5VWHRRcfX13dqMbprymE@dpg-d710lqvfte5s73ce5fkg-a/ecommerce_gauc")

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



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
        hashed_pw = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
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
            login_user(user)
            flash("Logged in successfully!", "success")
            next_page = request.args.get('next')  # redirect back if came from protected page
            return redirect(next_page or url_for("home"))
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
    # If item already in cart, increment quantity
    cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
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
    if current_user.username != 'radhika26':
        flash("Admin access required.", "danger")
        return redirect(url_for("home"))
    products = Product.query.all()
    return render_template("admin_dashboard.html", products=products)

# ---- ADMIN: EDIT PRODUCT ----
@app.route("/admin/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    if current_user.username != 'radhika26':
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

# ---- DB INIT + SEED ----
with app.app_context():
    db.create_all()
    seed_products()

if __name__ == "__main__":
    app.run(debug=True)
