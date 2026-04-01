from flask import Flask, render_template, request, redirect, session
import sqlite3
import re
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

# -------------------------
# 🔐 LOGIN REQUIRED DECORATOR
# -------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

# -------------------------
# NORMALIZE
# -------------------------
def normalize(text):
    if not text:
        return ""
    text = text.lower()
    text = text.replace("-", " ")
    text = text.replace("tshirt", "t shirt")
    text = text.replace("tea shirt", "t shirt")
    text = text.replace("tee shirt", "t shirt")
    text = text.replace("mens", "men")
    text = text.replace("womens", "women")
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

# -------------------------
# CATEGORY DETECTION
# -------------------------
def detect_category(query):
    query = normalize(query)

    categories = {
        "shoes": ["shoe", "shoes", "sneakers", "boots"],
        "laptops": ["laptop", "macbook", "thinkpad"],
        "headphones": ["headphone", "earbuds", "airpods", "headset"],
        "clothing": ["shirt", "t shirt", "jeans", "hoodie", "dress", "kurti"]
    }

    for cat, words in categories.items():
        for word in words:
            if word in query:
                return cat, words

    return None, []

# -------------------------
# INIT DB
# -------------------------
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price INTEGER
    )
    """)

    # Admin
    cursor.execute("SELECT * FROM users WHERE email=?", ("admin@gmail.com",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users(name,email,password) VALUES(?,?,?)",
            ("Admin", "admin@gmail.com", "admin123")
        )

    # Products (only once)
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO products(name, price) VALUES(?,?)",
            [
                ("Running Shoes Pro", 2500), ("Casual Sneakers", 1800),
                ("Nike Air Max", 6000), ("Adidas Ultraboost", 8000),
                ("Gaming Laptop RTX 3050", 70000), ("MacBook Air M1", 85000),
                ("Sony Headphones", 20000), ("Boat Rockerz", 1500),
                ("Men T-Shirt", 800), ("Women Kurti", 1800)
            ]
        )

    conn.commit()
    conn.close()

init_db()

# -------------------------
# GET PRODUCTS
# -------------------------
def get_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    data = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "price": r[2]} for r in data]

# -------------------------
# AUTH
# -------------------------
@app.route("/")
def register_page():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name")
    email = request.form.get("email").lower()
    password = request.form.get("password")
    confirm = request.form.get("confirm")

    if email == "admin@gmail.com":
        return "❌ Cannot register as admin"

    if password != confirm:
        return "❌ Passwords do not match"

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users(name,email,password) VALUES(?,?,?)",
            (name, email, password)
        )
        conn.commit()
        conn.close()
        return redirect("/login")
    except:
        return "❌ Email already exists"

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email").lower()
    password = request.form.get("password")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, password)
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        session["user"] = email
        session["voice_msg"] = "Login successful. Welcome to voice shopping"
        return redirect("/products")

    return "❌ Invalid credentials"

# -------------------------
# PRODUCTS
# -------------------------
@app.route("/products")
@login_required
def products_page():
    products = get_products()
    query = request.args.get("q", "")

    if query:
        query = normalize(query)
        category, keywords = detect_category(query)

        if keywords:
            products = [
                p for p in products
                if any(word in normalize(p["name"]) for word in keywords)
            ]
        else:
            products = [
                p for p in products
                if query in normalize(p["name"])
            ]

    return render_template("products.html", products=products)

# -------------------------
# CART
# -------------------------
@app.route("/add/<int:id>")
@login_required
def add_to_cart(id):
    session.setdefault("cart", []).append(id)
    session["voice_msg"] = "Product added to cart"
    session.modified = True
    return redirect("/products")

@app.route("/cart")
@login_required
def view_cart():
    products = get_products()
    cart_ids = session.get("cart", [])
    cart_items = [p for p in products if p["id"] in cart_ids]
    total = sum(p["price"] for p in cart_items)
    return render_template("cart.html", cart=cart_items, total=total)

@app.route("/remove/<int:id>")
@login_required
def remove_from_cart(id):
    if "cart" in session and id in session["cart"]:
        session["cart"].remove(id)
        session["voice_msg"] = "Product removed from cart"
        session.modified = True
    return redirect("/cart")

# -------------------------
# VOICE ADD
# -------------------------
@app.route('/voice-add')
@login_required
def voice_add():

    query = normalize(request.args.get('q', ''))
    if not query:
        return redirect('/products')

    products = get_products()
    found = None

    for p in products:
        if query in normalize(p["name"]):
            found = p
            break

    if not found:
        _, keywords = detect_category(query)
        for p in products:
            if any(word in normalize(p["name"]) for word in keywords):
                found = p
                break

    if found:
        session.setdefault("cart", []).append(found["id"])
        session["voice_msg"] = f"{found['name']} added to cart"
        session.modified = True
    else:
        session["voice_msg"] = "Product not found"

    return redirect('/cart')

# -------------------------
# VOICE REMOVE
# -------------------------
@app.route('/voice-remove')
@login_required
def voice_remove():

    query = normalize(request.args.get('q', ''))
    products = get_products()
    cart_ids = session.get("cart", [])

    for p in products:
        if p["id"] in cart_ids and query in normalize(p["name"]):
            session["cart"].remove(p["id"])
            session["voice_msg"] = f"{p['name']} removed"
            session.modified = True
            break

    return redirect('/cart')

# -------------------------
# 👨‍💼 ADMIN PANEL
# -------------------------
@app.route("/admin")
@login_required
def admin():

    if session["user"] != "admin@gmail.com":
        return "❌ Access Denied"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, email FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    conn.close()

    return render_template("admin.html", users=users, products=products)

# -------------------------
# LOGOUT
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)