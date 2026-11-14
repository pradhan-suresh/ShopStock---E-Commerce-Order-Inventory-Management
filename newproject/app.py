
from datetime import datetime
import os

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# -----------------------------------
# APPLICATION CONFIGURATION
# -----------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-key-change-before-deployment"
)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" +
    os.path.join(BASE_DIR, "ecommerce.db").replace("\\", "/")
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# -----------------------------------
# DATABASE MODELS
# -----------------------------------

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

    orders = db.relationship(
        "Order",
        back_populates="product"
    )


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    quantity = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Placed"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    product = db.relationship(
        "Product",
        back_populates="orders"
    )


# -----------------------------------
# DASHBOARD
# -----------------------------------

@app.route("/")
def dashboard():
    total_products = Product.query.count()
    total_orders = Order.query.count()

    total_stock = (
        db.session.query(func.sum(Product.stock)).scalar() or 0
    )

    total_revenue = (
        db.session.query(func.sum(Order.total_amount))
        .filter(Order.status != "Cancelled")
        .scalar() or 0
    )

    low_stock_products = (
        Product.query
        .filter(Product.stock <= 5)
        .order_by(Product.stock.asc())
        .all()
    )

    recent_orders = (
        Order.query
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_orders=total_orders,
        total_stock=total_stock,
        total_revenue=total_revenue,
        low_stock_products=low_stock_products,
        recent_orders=recent_orders
    )


# -----------------------------------
# PRODUCT MANAGEMENT
# -----------------------------------

@app.route("/products")
def products():
    all_products = (
        Product.query
        .order_by(Product.id.desc())
        .all()
    )

    return render_template(
        "products.html",
        products=all_products
    )


@app.route("/products/add", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        try:
            price = float(request.form.get("price", ""))
            stock = int(request.form.get("stock", ""))
        except (ValueError, TypeError):
            flash(
                "Enter a valid price and stock quantity.",
                "error"
            )
            return redirect(url_for("add_product"))

        if not name or not category:
            flash(
                "Product name and category are required.",
                "error"
            )

        elif not (0 < price < float("inf")) or stock < 0:
            flash(
                "Price must be positive and stock cannot be negative.",
                "error"
            )

        else:
            product = Product(
                name=name,
                category=category,
                price=round(price, 2),
                stock=stock
            )

            try:
                db.session.add(product)
                db.session.commit()
                flash(
                    "Product added successfully.",
                    "success"
                )
                return redirect(url_for("products"))
            except Exception:
                db.session.rollback()
                flash("Unable to save the product.", "error")

    return render_template("add_product.html")


@app.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        flash("Product not found.", "error")

    elif Order.query.filter_by(product_id=product_id).first():
        flash(
            "Products with order history cannot be deleted.",
            "error"
        )

    else:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully.", "success")

    return redirect(url_for("products"))


# -----------------------------------
# ORDER MANAGEMENT
# -----------------------------------

@app.route("/orders")
def orders():
    all_orders = (
        Order.query
        .order_by(Order.created_at.desc())
        .all()
    )

    return render_template(
        "orders.html",
        orders=all_orders
    )


@app.route("/orders/create", methods=["GET", "POST"])
def create_order():
    available_products = (
        Product.query
        .filter(Product.stock > 0)
        .order_by(Product.name)
        .all()
    )

    if request.method == "POST":
        customer_name = request.form.get(
            "customer_name", ""
        ).strip()

        try:
            product_id = int(request.form.get("product_id", ""))
            quantity = int(request.form.get("quantity", ""))
        except (ValueError, TypeError):
            flash(
                "Select a product and enter a valid quantity.",
                "error"
            )
            return redirect(url_for("create_order"))

        product = db.session.get(Product, product_id)

        if not customer_name:
            flash("Customer name is required.", "error")

        elif product is None:
            flash("Select a valid product.", "error")

        elif quantity <= 0:
            flash("Quantity must be at least 1.", "error")

        elif product.stock < quantity:
            flash(
                f"Only {product.stock} units are available.",
                "error"
            )

        else:
            try:
                product.stock -= quantity

                order = Order(
                    customer_name=customer_name,
                    product=product,
                    quantity=quantity,
                    total_amount=round(
                        product.price * quantity, 2
                    ),
                    status="Placed"
                )

                db.session.add(order)
                db.session.commit()

                flash(
                    f"Order #{order.id} placed successfully.",
                    "success"
                )
                return redirect(url_for("orders"))

            except Exception:
                db.session.rollback()
                flash("Unable to create the order.", "error")

    return render_template(
        "create_order.html",
        products=available_products
    )


@app.route("/orders/cancel/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    order = db.session.get(Order, order_id)

    if order is None:
        flash("Order not found.", "error")

    elif order.status == "Cancelled":
        flash("This order is already cancelled.", "error")

    elif order.status == "Delivered":
        flash(
            "Delivered orders cannot be cancelled.",
            "error"
        )

    else:
        try:
            order.product.stock += order.quantity
            order.status = "Cancelled"
            db.session.commit()

            flash(
                "Order cancelled. Stock has been restored.",
                "success"
            )
        except Exception:
            db.session.rollback()
            flash("Unable to cancel the order.", "error")

    return redirect(url_for("orders"))


@app.route("/orders/status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    order = db.session.get(Order, order_id)
    new_status = request.form.get("status", "")

    if order is None:
        flash("Order not found.", "error")

    elif order.status in ["Cancelled", "Delivered"]:
        flash(
            "This order can no longer be updated.",
            "error"
        )

    elif new_status not in [
        "Processing", "Shipped", "Delivered"
    ]:
        flash("Invalid order status.", "error")

    else:
        order.status = new_status
        db.session.commit()
        flash("Order status updated.", "success")

    return redirect(url_for("orders"))


# -----------------------------------
# SAMPLE DATA
# -----------------------------------

def add_sample_data():
    # Add sample products only if the database is empty.
    if Product.query.count() == 0:
        sample_products = [
            Product(
                name="Wireless Mouse",
                category="Electronics",
                price=599.00,
                stock=25
            ),
            Product(
                name="Mechanical Keyboard",
                category="Electronics",
                price=1499.00,
                stock=12
            ),
            Product(
                name="USB Cable",
                category="Accessories",
                price=199.00,
                stock=4
            ),
            Product(
                name="Laptop Stand",
                category="Accessories",
                price=899.00,
                stock=3
            ),
            Product(
                name="Headphones",
                category="Electronics",
                price=1299.00,
                stock=18
            )
        ]

        db.session.add_all(sample_products)
        db.session.commit()

    # Add sample orders only if there are no existing orders.
    if Order.query.count() == 0:
        mouse = Product.query.filter_by(
            name="Wireless Mouse"
        ).first()

        keyboard = Product.query.filter_by(
            name="Mechanical Keyboard"
        ).first()

        if mouse and keyboard:
            sample_orders = [
                Order(
                    customer_name="Rahul Sharma",
                    product=mouse,
                    quantity=2,
                    total_amount=round(mouse.price * 2, 2),
                    status="Placed"
                ),
                Order(
                    customer_name="Priya Reddy",
                    product=keyboard,
                    quantity=1,
                    total_amount=round(keyboard.price, 2),
                    status="Delivered"
                )
            ]

            db.session.add_all(sample_orders)
            db.session.commit()


# -----------------------------------
# APPLICATION STARTUP
# -----------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        add_sample_data()

    app.run(debug=True)
