
from flask import Flask, request, redirect, url_for, session
from pathlib import Path
from collections import deque
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "smart-canteen-demo-key"

BASE = Path(__file__).resolve().parent

USER_FILE = BASE / "users.json"
ORDER_FILE = BASE / "orders.json"
PAYMENT_FILE = BASE / "payments.json"
FEEDBACK_FILE = BASE / "feedback.json"
MENU_FILE = BASE / "menu.json"

DEFAULT_MENU = [
    {"id": 1, "name": "Veg Sandwich", "price": 40},
    {"id": 2, "name": "Masala Dosa", "price": 50},
    {"id": 3, "name": "Veg Fried Rice", "price": 70},
    {"id": 4, "name": "Lemon Juice", "price": 25},
    {"id": 5, "name": "Tea", "price": 15}
]

# STACK: stores the latest staff status changes.
action_stack = []


# ---------------- DATA FUNCTIONS ----------------

def read_data(file_name):
    if not file_name.exists():
        return []

    try:
        return json.loads(file_name.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_data(file_name, data):
    file_name.write_text(
        json.dumps(data, indent=4),
        encoding="utf-8"
    )


def load_menu():
    if not MENU_FILE.exists():
        save_data(MENU_FILE, DEFAULT_MENU)

    return read_data(MENU_FILE)


def save_menu(menu):
    save_data(MENU_FILE, menu)


def load_users():
    return read_data(USER_FILE)


def save_users(users):
    save_data(USER_FILE, users)


def load_orders():
    return read_data(ORDER_FILE)


def save_orders(orders):
    save_data(ORDER_FILE, orders)


def load_payments():
    return read_data(PAYMENT_FILE)


def load_feedback():
    return read_data(FEEDBACK_FILE)


def build_queue(orders):
    waiting = [
        order for order in orders
        if order["status"] == "Waiting"
    ]

    waiting.sort(key=lambda order: order["id"])

    return deque(order["id"] for order in waiting)


def money(amount):
    return "₹" + str(amount)


# ---------------- NAVIGATION ----------------

def navigation():

    role = session.get("role")

    if role == "student":
        return """
        <header>
            <h2>🍽 Smart Canteen</h2>
            <nav>
                <a href="/home.html">Home</a>
                <a href="/menu.html">Food Menu</a>
                <a href="/place_order.html">Place Order</a>
                <a href="/track_order.html">Track Order</a>
                <a href="/order_history.html">Order History</a>
                <a href="/student_profile.html">Profile</a>
                <a href="/payment_history.html">Payments</a>
                <a href="/canteen_feedback.html">Feedback</a>
                <a href="/logout">Logout</a>
            </nav>
        </header>
        """

    elif role == "supervisor":
        return """
        <header>
            <h2>🍽 Smart Canteen</h2>
            <nav>
                <a href="/staff_dashboard.html">Staff Dashboard</a>
                <a href="/menu.html">Manage Food Menu</a>
                <a href="/logout">Logout</a>
            </nav>
        </header>
        """

    return ""


def page(file_name, content=""):

    path = BASE / "templates" / file_name
    html = path.read_text(encoding="utf-8")

    html = html.replace("<!-- PAGE_CONTENT -->", content)
    html = html.replace("<!-- NAVIGATION -->", navigation())

    return html


# ---------------- LOGIN AND REGISTRATION ----------------

SUPERVISOR_USERNAME = "admin"
SUPERVISOR_PASSWORD = "admin123"


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login.html")
def login():

    if session.get("role") == "student":
        return redirect(url_for("home"))

    if session.get("role") == "supervisor":
        return redirect(url_for("staff_dashboard"))

    return page("login.html")


@app.route("/register.html")
def register():
    return page("register.html")


@app.route("/register_student", methods=["POST"])
def register_student():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password:
        return page(
            "register.html",
            "<p class='message'>Please fill in all the fields.</p>"
        )

    if password != confirm_password:
        return page(
            "register.html",
            "<p class='message'>Passwords do not match.</p>"
        )

    if len(password) < 6:
        return page(
            "register.html",
            "<p class='message'>Password must contain at least 6 characters.</p>"
        )

    users = load_users()

    for user in users:
        if user["email"] == email:
            return page(
                "register.html",
                "<p class='message'>This email is already registered. Please login.</p>"
            )

    users.append({
        "name": name,
        "email": email,
        "password": generate_password_hash(password)
    })

    save_users(users)

    return page(
        "login.html",
        "<p class='message'>Registration successful! Please login with your new account.</p>"
    )


@app.route("/student_login", methods=["POST"])
def student_login():

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    users = load_users()

    for user in users:

        if user["email"] == email:
            if check_password_hash(user["password"], password):

                session.clear()
                session["role"] = "student"
                session["student_email"] = email
                session["student_name"] = user["name"]

                return redirect(url_for("home"))

    return page(
        "login.html",
        "<p class='message'>Invalid email or password. Please try again.</p>"
    )


@app.route("/supervisor_login", methods=["POST"])
def supervisor_login():

    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if username == SUPERVISOR_USERNAME and password == SUPERVISOR_PASSWORD:

        session.clear()
        session["role"] = "supervisor"

        return redirect(url_for("staff_dashboard"))

    return page(
        "login.html",
        "<p class='message'>Invalid supervisor username or password.</p>"
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ---------------- LOGIN PROTECTION ----------------

@app.before_request
def check_login():

    public_pages = [
        "/",
        "/login.html",
        "/register.html",
        "/register_student",
        "/student_login",
        "/supervisor_login",
        "/logout"
    ]

    if request.path in public_pages or request.path.startswith("/static/"):
        return

    role = session.get("role")

    if not role:
        return redirect(url_for("login"))

    if role == "student":

        if (
            request.path == "/staff_dashboard.html"
            or request.path.startswith("/update_status/")
            or request.path in ["/add_food"]
            or request.path.startswith("/delete_food/")
        ):
            return redirect(url_for("home"))

    if role == "supervisor":

        student_pages = [
            "/home.html",
            "/add_to_cart",
            "/place_order.html",
            "/confirm_order",
            "/payment.html",
            "/make_payment",
            "/payment_success.html",
            "/order_confirmation.html",
            "/track_order.html",
            "/order_history.html",
            "/student_profile.html",
            "/payment_history.html",
            "/canteen_feedback.html"
        ]

        if request.path in student_pages:
            return redirect(url_for("staff_dashboard"))


# ---------------- HOME PAGE ----------------

@app.route("/home.html")
def home():
    return page("home.html")


# ---------------- FOOD MENU ----------------

@app.route("/menu.html")
def menu():

    menu_items = load_menu()

    # SUPERVISOR MENU MANAGEMENT

    if session.get("role") == "supervisor":

        cards = ""

        for food in menu_items:

            cards += f"""
            <article class="card">

                <h2>{food['name']}</h2>

                <p>Price: {money(food['price'])}</p>

                <form action="/delete_food/{food['id']}"
                      method="post">

                    <button type="submit"
                            onclick="return confirm('Delete this food item?')">
                        Delete Food
                    </button>

                </form>

            </article>
            """

        if not cards:
            cards = "<p>No food items available.</p>"

        content = f"""
        <h1>Manage Food Menu</h1>

        <p>Add new food items to the student menu.</p>

        <section class="card">

            <h2>Add New Food</h2>

            <form action="/add_food" method="post">

                <label>Food Name
                    <input type="text"
                           name="food_name"
                           placeholder="Enter food name"
                           required>
                </label>

                <label>Food Price
                    <input type="number"
                           name="food_price"
                           placeholder="Enter price"
                           min="1"
                           required>
                </label>

                <button type="submit">Add Food Item</button>

            </form>

        </section>

        <h2>Existing Food Items</h2>

        <div class="grid">
            {cards}
        </div>
        """

        return page("menu.html", content)

    # STUDENT FOOD MENU

    cards = ""

    for food in menu_items:

        cards += f"""
        <article class="card">

            <h2>{food['name']}</h2>

            <p>Price: {money(food['price'])}</p>

            <label>Quantity
                <input type="number"
                       name="qty_{food['id']}"
                       value="0"
                       min="0"
                       max="50">
            </label>

        </article>
        """

    content = f"""
    <h1>Food Menu</h1>

    <p>Select the food items and enter the required quantity.</p>

    <form action="/add_to_cart" method="post">

        <div class="grid">
            {cards}
        </div>

        <button type="submit">Add Selected Items</button>

    </form>
    """

    return page("menu.html", content)


# ADD NEW FOOD - SUPERVISOR ONLY

@app.route("/add_food", methods=["POST"])
def add_food():

    if session.get("role") != "supervisor":
        return redirect(url_for("login"))

    name = request.form.get("food_name", "").strip()

    try:
        price = int(request.form.get("food_price", "0"))
    except ValueError:
        price = 0

    if not name or price <= 0:
        return redirect(url_for("menu"))

    menu_items = load_menu()

    next_id = max(
        [food["id"] for food in menu_items],
        default=0
    ) + 1

    menu_items.append({
        "id": next_id,
        "name": name,
        "price": price
    })

    save_menu(menu_items)

    return redirect(url_for("menu"))


# DELETE FOOD - SUPERVISOR ONLY

@app.route("/delete_food/<int:food_id>", methods=["POST"])
def delete_food(food_id):

    if session.get("role") != "supervisor":
        return redirect(url_for("login"))

    menu_items = load_menu()

    menu_items = [
        food for food in menu_items
        if food["id"] != food_id
    ]

    save_menu(menu_items)

    return redirect(url_for("menu"))


# ADD SELECTED FOOD TO CART - STUDENTS

@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():

    cart = session.get("cart", {})
    menu_items = load_menu()

    for food in menu_items:

        try:
            quantity = int(
                request.form.get(f"qty_{food['id']}", "0")
            )
        except ValueError:
            quantity = 0

        if 1 <= quantity <= 50:
            cart[str(food["id"])] = (
                cart.get(str(food["id"]), 0) + quantity
            )

    session["cart"] = cart

    return redirect(url_for("place_order"))


# ---------------- PLACE ORDER ----------------

@app.route("/place_order.html")
def place_order():

    cart = session.get("cart", {})
    rows = ""
    total = 0

    for food in load_menu():

        quantity = cart.get(str(food["id"]), 0)

        if quantity:
            subtotal = food["price"] * quantity
            total += subtotal

            rows += f"""
            <tr>
                <td>{food['name']}</td>
                <td>{quantity}</td>
                <td>{money(subtotal)}</td>
            </tr>
            """

    if not rows:
        rows = """
        <tr>
            <td colspan="3">
                Your cart is empty. Please select food from the menu.
            </td>
        </tr>
        """

    content = f"""
    <h1>Place Your Order</h1>

    <section class="card">
        <h2>Order Summary</h2>

        <table>
            <tr>
                <th>Food</th>
                <th>Quantity</th>
                <th>Amount</th>
            </tr>
            {rows}
        </table>

        <h2>Total: {money(total)}</h2>

        <form action="/confirm_order" method="post">
            <label>Your Name
                <input type="text"
                       name="customer_name"
                       value="{session.get('student_name', '')}"
                       placeholder="Enter your name"
                       required>
            </label>

            <button type="submit"
                    {'disabled' if total == 0 else ''}>
                Continue to Payment
            </button>
        </form>

        <a class="button secondary" href="/menu.html">
            Back to Food Menu
        </a>
    </section>
    """

    return page("place_order.html", content)


@app.route("/confirm_order", methods=["POST"])
def confirm_order():

    cart = session.get("cart", {})
    items = []
    total = 0

    for food in load_menu():

        quantity = cart.get(str(food["id"]), 0)

        if quantity:
            items.append({
                "id": food["id"],
                "name": food["name"],
                "price": food["price"],
                "quantity": quantity
            })

            total += food["price"] * quantity

    if not items:
        return redirect(url_for("menu"))

    orders = load_orders()

    next_id = max(
        [order["id"] for order in orders],
        default=1000
    ) + 1

    order = {
        "id": next_id,
        "customer_name": request.form.get(
            "customer_name",
            session.get("student_name", "Student")
        ),
        "student_email": session.get("student_email"),
        "items": items,
        "total": total,
        "status": "Awaiting Payment",
        "created_at": datetime.now().strftime(
            "%d-%m-%Y %I:%M %p"
        )
    }

    orders.append(order)
    save_orders(orders)

    session["pending_order_id"] = next_id

    return redirect(url_for("payment"))


# ---------------- PAYMENT ----------------

@app.route("/payment.html")
def payment():

    order_id = session.get("pending_order_id")
    orders = load_orders()

    order = next(
        (
            item for item in orders
            if item["id"] == order_id
            and item.get("student_email") == session.get("student_email")
        ),
        None
    )

    if not order:
        return redirect(url_for("menu"))

    content = f"""
    <h1>Complete Your Payment</h1>

    <section class="card payment-card">

        <h2>Order #{order['id']}</h2>

        <h2 class="payment-amount">
            Amount to Pay: {money(order['total'])}
        </h2>

        <p>Select your payment method and use the demo QR below.</p>

        <div class="qr-box">
            <h3>Canteen UPI QR Code</h3>

            <img src="/static/demo_qr.svg"
                 alt="Demo payment QR code"
                 class="demo-qr">

            <p class="qr-warning">
                Demo QR only - Cannot be scanned or used for payment.
            </p>
        </div>

        <form action="/make_payment" method="post">

            <label>Select Payment Method</label>

            <select name="method" required>
                <option value="">Choose payment method</option>
                <option value="UPI Demo">UPI</option>
                <option value="Card Demo">Debit/Credit Card</option>
                <option value="Cash at Counter">Cash at Counter</option>
            </select>

            <button type="submit">
                Confirm Demo Payment
            </button>

        </form>

    </section>
    """

    return page("payment.html", content)


@app.route("/make_payment", methods=["POST"])
def make_payment():

    order_id = session.get("pending_order_id")
    orders = load_orders()

    order = next(
        (
            item for item in orders
            if item["id"] == order_id
            and item.get("student_email") == session.get("student_email")
        ),
        None
    )

    if not order:
        return redirect(url_for("menu"))

    method = request.form.get("method", "Demo")
    payments = load_payments()

    payments.append({
        "payment_id": len(payments) + 1,
        "order_id": order_id,
        "student_email": session.get("student_email"),
        "amount": order["total"],
        "method": method,
        "status": "Successful (Demo)",
        "created_at": datetime.now().strftime(
            "%d-%m-%Y %I:%M %p"
        )
    })

    save_data(PAYMENT_FILE, payments)

    order["status"] = "Waiting"
    save_orders(orders)

    session["last_order_id"] = order_id
    session.pop("cart", None)
    session.pop("pending_order_id", None)

    return redirect(url_for("payment_success"))


# ---------------- PAYMENT SUCCESS ----------------

@app.route("/payment_success.html")
def payment_success():

    order_id = session.get("last_order_id")

    content = f"""
    <section class="card success-card">

        <div class="success-circle">
            &#10003;
        </div>

        <h1>Payment Successful!</h1>

        <p>Your payment has been completed successfully.</p>

        <h2>Order ID: #{order_id}</h2>

        <p>Your order is now added to the canteen queue.</p>

        <a class="button" href="/order_confirmation.html">
            View Order Confirmation
        </a>

        <a class="button secondary"
           href="/track_order.html?order_id={order_id}">
            Track Order
        </a>

    </section>
    """

    return page("payment_success.html", content)


# ---------------- ORDER CONFIRMATION ----------------

@app.route("/order_confirmation.html")
def order_confirmation():

    order_id = session.get("last_order_id")

    order = next(
        (
            item for item in load_orders()
            if item["id"] == order_id
            and item.get("student_email") == session.get("student_email")
        ),
        None
    )

    if not order:
        return redirect(url_for("home"))

    item_text = ", ".join(
        item["name"] + " x " + str(item["quantity"])
        for item in order["items"]
    )

    content = f"""
    <section class="card">

        <h1>Order Confirmation</h1>

        <h2>Order ID: #{order['id']}</h2>

        <p>Name: {order['customer_name']}</p>
        <p>Items: {item_text}</p>
        <p>Total: {money(order['total'])}</p>

        <p>
            Status:
            <span class="status">{order['status']}</span>
        </p>

        <a class="button"
           href="/track_order.html?order_id={order['id']}">
            Track My Order
        </a>

    </section>
    """

    return page("order_confirmation.html", content)


# ---------------- TRACK ORDER ----------------

@app.route("/track_order.html", methods=["GET", "POST"])
def track_order():

    order_id = (
        request.form.get("order_id")
        if request.method == "POST"
        else request.args.get("order_id", "")
    )

    content = """
    <h1>Track Your Order</h1>

    <section class="card">

        <form action="/track_order.html" method="post">

            <label>Order ID
                <input type="number"
                       name="order_id"
                       placeholder="Enter your Order ID"
                       required>
            </label>

            <button type="submit">Track Order</button>

        </form>
    """

    if order_id:

        order = next(
            (
                item for item in load_orders()
                if str(item["id"]) == str(order_id)
                and item.get("student_email") == session.get("student_email")
            ),
            None
        )

        if order:

            item_text = ", ".join(
                item["name"] + " x " + str(item["quantity"])
                for item in order["items"]
            )

            if order["status"] == "Ready":
                message = (
                    "🔔 Your order is ready to serve! "
                    "Please collect it from the canteen counter."
                )

            elif order["status"] == "Preparing":
                message = "Your food is being prepared. Please wait."

            elif order["status"] == "Completed":
                message = "Your order has been completed. Thank you!"

            else:
                message = "Your order is waiting in the queue."

            content += f"""
            <hr>

            <h2>Order #{order['id']}</h2>

            <p>Name: {order['customer_name']}</p>
            <p>Items: {item_text}</p>
            <p>Total: {money(order['total'])}</p>

            <p>
                Status:
                <span class="status">{order['status']}</span>
            </p>

            <p class="message">{message}</p>
            """

        else:
            content += """
            <p class="message">
                Order ID not found. Please check and try again.
            </p>
            """

    content += "</section>"

    return page("track_order.html", content)


# ---------------- STUDENT ORDER HISTORY ----------------

@app.route("/order_history.html")
def order_history():

    orders = load_orders()
    rows = ""

    student_email = session.get("student_email")

    for order in reversed(orders):

        if order.get("student_email") != student_email:
            continue

        items = ", ".join(
            item["name"] + " x " + str(item["quantity"])
            for item in order["items"]
        )

        rows += f"""
        <tr>
            <td>#{order['id']}</td>
            <td>{order['customer_name']}</td>
            <td>{items}</td>
            <td>{money(order['total'])}</td>
            <td>{order['status']}</td>
        </tr>
        """

    if not rows:
        rows = """
        <tr>
            <td colspan="5">No orders yet.</td>
        </tr>
        """

    content = f"""
    <h1>Order History</h1>

    <section class="card">

        <table>
            <tr>
                <th>Order ID</th>
                <th>Customer</th>
                <th>Items</th>
                <th>Total</th>
                <th>Status</th>
            </tr>

            {rows}
        </table>

    </section>
    """

    return page("order_history.html", content)


# ---------------- STAFF DASHBOARD ----------------

@app.route("/staff_dashboard.html")
def staff_dashboard():

    orders = load_orders()
    queue = build_queue(orders)

    positions = {
        order_id: i + 1
        for i, order_id in enumerate(queue)
    }

    cards = ""

    for order in reversed(orders):

        options = ""

        for status in ["Waiting", "Preparing", "Ready", "Completed"]:

            selected = (
                "selected"
                if status == order["status"]
                else ""
            )

            options += f"""
            <option value="{status}" {selected}>
                {status}
            </option>
            """

        items = ", ".join(
            item["name"] + " x " + str(item["quantity"])
            for item in order["items"]
        )

        cards += f"""
        <article class="card">

            <h2>Order #{order['id']}</h2>

            <p>Customer: {order['customer_name']}</p>
            <p>Items: {items}</p>
            <p>Total: {money(order['total'])}</p>

            <p>
                Queue Position:
                {positions.get(order['id'], '-')}
            </p>

            <p>
                Status:
                <span class="status">{order['status']}</span>
            </p>

            <form action="/update_status/{order['id']}"
                  method="post">

                <label>Update Status
                    <select name="status">
                        {options}
                    </select>
                </label>

                <button type="submit">Save Status</button>

            </form>

        </article>
        """

    if not cards:
        cards = '<div class="card">No orders yet.</div>'

    recent = "".join(
        f"<li>{action}</li>"
        for action in reversed(action_stack[-5:])
    ) or "<li>No recent actions.</li>"

    content = f"""
    <h1>Staff Dashboard</h1>

    {cards}

    <section class="card">
        <h2>Recent Status Actions</h2>
        <ul>{recent}</ul>
    </section>
    """

    return page("staff_dashboard.html", content)


# ---------------- UPDATE ORDER STATUS ----------------

@app.route("/update_status/<int:order_id>", methods=["POST"])
def update_status(order_id):

    status = request.form.get("status")

    allowed = [
        "Waiting",
        "Preparing",
        "Ready",
        "Completed"
    ]

    orders = load_orders()

    for order in orders:

        if order["id"] == order_id and status in allowed:

            old_status = order["status"]
            order["status"] = status

            action_stack.append(
                f"Order #{order_id}: {old_status} → {status}"
            )

            break

    save_orders(orders)

    return redirect(url_for("staff_dashboard"))


# ---------------- STUDENT PROFILE ----------------

@app.route("/student_profile.html", methods=["GET", "POST"])
def student_profile():

    if request.method == "POST":

        session["student_profile"] = {
            "name": request.form.get("name", ""),
            "roll_no": request.form.get("roll_no", ""),
            "department": request.form.get("department", ""),
            "email": request.form.get("email", "")
        }

    profile = session.get("student_profile", {})

    content = f"""
    <h1>Student Profile</h1>

    <section class="card">

        <form action="/student_profile.html" method="post">

            <label>Name
                <input type="text"
                       name="name"
                       value="{profile.get('name', session.get('student_name', ''))}"
                       required>
            </label>

            <label>Roll Number
                <input type="text"
                       name="roll_no"
                       value="{profile.get('roll_no', '')}">
            </label>

            <label>Department
                <input type="text"
                       name="department"
                       value="{profile.get('department', '')}">
            </label>

            <label>Email
                <input type="email"
                       name="email"
                       value="{profile.get('email', session.get('student_email', ''))}">
            </label>

            <button type="submit">Save Profile</button>

        </form>

        <p class="message">
            Profile details are stored for this browser session.
        </p>

    </section>
    """

    return page("student_profile.html", content)


# ---------------- STUDENT PAYMENT HISTORY ----------------

@app.route("/payment_history.html")
def payment_history():

    payments = load_payments()
    rows = ""

    student_email = session.get("student_email")

    for payment in reversed(payments):

        if payment.get("student_email") != student_email:
            continue

        rows += f"""
        <tr>
            <td>#{payment['payment_id']}</td>
            <td>#{payment['order_id']}</td>
            <td>{money(payment['amount'])}</td>
            <td>{payment['method']}</td>
            <td>{payment['status']}</td>
            <td>{payment['created_at']}</td>
        </tr>
        """

    if not rows:
        rows = """
        <tr>
            <td colspan="6">No payment records yet.</td>
        </tr>
        """

    content = f"""
    <h1>Payment History</h1>

    <section class="card">

        <table>
            <tr>
                <th>Payment ID</th>
                <th>Order ID</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Status</th>
                <th>Date</th>
            </tr>

            {rows}
        </table>

    </section>
    """

    return page("payment_history.html", content)


# ---------------- FEEDBACK ----------------

@app.route("/canteen_feedback.html", methods=["GET", "POST"])
def canteen_feedback():

    message = ""

    if request.method == "POST":

        feedback = load_feedback()

        feedback.append({
            "name": request.form.get("name", "Student"),
            "rating": request.form.get("rating", ""),
            "comments": request.form.get("comments", ""),
            "created_at": datetime.now().strftime(
                "%d-%m-%Y %I:%M %p"
            )
        })

        save_data(FEEDBACK_FILE, feedback)

        message = """
        <p class='message'>
            Thank you! Your feedback has been submitted.
        </p>
        """

    content = f"""
    <h1>Canteen Feedback</h1>

    <section class="card">

        <form action="/canteen_feedback.html" method="post">

            <label>Your Name
                <input type="text" name="name" required>
            </label>

            <label>Rating
                <select name="rating" required>
                    <option value="">Select rating</option>
                    <option>Excellent</option>
                    <option>Good</option>
                    <option>Average</option>
                    <option>Needs Improvement</option>
                </select>
            </label>

            <label>Your Comments
                <textarea name="comments"
                          rows="4"
                          placeholder="Write your feedback"></textarea>
            </label>

            <button type="submit">Submit Feedback</button>

        </form>

        {message}

    </section>
    """

    return page("canteen_feedback.html", content)


if __name__ == "__main__":
    app.run(debug=True)
