from flask import Flask, render_template, request, redirect, session
import sqlite3
import re
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")

# -------------------------
# DATABASE PATH
# -------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

# -------------------------
# NORMALIZE FUNCTION
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
# INIT DATABASE
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

    # Products
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO products(name, price) VALUES(?,?)",
            [
                ("Running Shoes Pro", 2500), ("Casual Sneakers", 1800),
                ("Sports Trainers", 3000), ("Formal Leather Shoes", 3500),
                ("Nike Air Max", 6000), ("Adidas Ultraboost", 8000),
                ("Puma Street Shoes", 2200), ("Reebok Classic", 2700),
                ("Campus Sneakers", 1500), ("Woodland Boots", 4500),

                ("Gaming Laptop RTX 3050", 70000), ("Gaming Laptop RTX 4060", 95000),
                ("Office Laptop i5", 50000), ("Office Laptop i7", 65000),
                ("MacBook Air M1", 85000), ("MacBook Pro M2", 120000),
                ("HP Pavilion Laptop", 55000), ("Dell Inspiron Laptop", 52000),
                ("Lenovo ThinkPad", 60000), ("Asus ROG Strix", 110000),

                ("Wireless Headphones", 4000), ("Bluetooth Headphones", 2500),
                ("Sony WH-1000XM4", 20000), ("JBL Tune 510BT", 3000),
                ("Boat Rockerz 450", 1500), ("Noise Cancelling Headphones", 7000),
                ("Gaming Headset RGB", 3500), ("Over Ear Headphones", 2800),
                ("In-Ear Earbuds", 1200), ("Apple AirPods", 15000),

                ("Men Casual Shirt", 1200), ("Women Stylish Shirt", 1500),
                ("Men T-Shirt", 800), ("Women Kurti", 1800),
                ("Denim Jeans", 2000), ("Winter Jacket", 3500),
                ("Unisex Hoodie", 2200), ("Formal Shirt", 1700),
                ("Track Pants", 1400), ("Summer Dress", 1600)
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
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    confirm = request.form.get("confirm", "").strip()

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
    except Exception as e:
        return f"❌ Registration Error: {e}"

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

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
        return redirect("/products")

    return "❌ Invalid credentials"

# -------------------------
# PRODUCTS
# -------------------------
@app.route("/products")
def products_page():
    if "user" not in session:
        return redirect("/login")

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
def add_to_cart(id):
    session.setdefault("cart", []).append(id)
    session.modified = True
    return redirect("/products")

@app.route("/cart")
def view_cart():
    products = get_products()
    cart_ids = session.get("cart", [])
    cart_items = [p for p in products if p["id"] in cart_ids]
    total = sum(p["price"] for p in cart_items)
    return render_template("cart.html", cart=cart_items, total=total)

@app.route("/remove/<int:id>")
def remove_from_cart(id):
    if "cart" in session and id in session["cart"]:
        session["cart"].remove(id)
        session.modified = True
    return redirect("/cart")

# -------------------------
# VOICE ADD (FIXED)
# -------------------------
@app.route('/voice-add')
def voice_add():

    query = request.args.get('q', '')
    query = normalize(query)

    if not query:
        return redirect('/products')

    products = get_products()
    found_product = None

    # 🔥 direct match
    for p in products:
        if query in normalize(p["name"]):
            found_product = p
            break

    # 🔥 category match
    if not found_product:
        category, keywords = detect_category(query)

        for p in products:
            if any(word in normalize(p["name"]) for word in keywords):
                found_product = p
                break

    # 🛒 add to cart
    if found_product:
        session.setdefault("cart", []).append(found_product["id"])
        session.modified = True

    return redirect('/cart')



@app.route('/voice-remove')
def voice_remove():

    query = request.args.get('q', '')
    query = normalize(query)

    if not query:
        return redirect('/cart')

    products = get_products()
    cart_ids = session.get("cart", [])

    for p in products:
        if p["id"] in cart_ids and query in normalize(p["name"]):
            session["cart"].remove(p["id"])
            session.modified = True
            break

    return redirect('/cart')

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