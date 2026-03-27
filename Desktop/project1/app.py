from datetime import datetime
import os

from functools import wraps
from bson.objectid import ObjectId
from flask import Flask, redirect, render_template, request, session, url_for
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
bcrypt = Bcrypt(app)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("Missing FLASK_SECRET_KEY. Add it to your .env file.")
if not MONGO_URI:
    raise RuntimeError("Missing MONGO_URI. Add it to your .env file.")
if not MONGO_DB:
    raise RuntimeError("Missing MONGO_DB. Add it to your .env file.")

client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=5000)

try:
    client.admin.command("ping")
    print("MongoDB connected")
except Exception as error:
    print("MongoDB connection error:", error)

db = client[os.getenv("MONGO_DB")]
products_collection = db["products"]
users_collection = db["users"]
carts_collection = db["carts"]
swaps_collection = db["swaps"]

VALID_CONDITIONS = {"New", "Good", "Used"}


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if user is not None:
            # Backward-compatible defaults for older user documents / manual admin creation.
            if not user.get("username") and user.get("name"):
                user["username"] = user["name"]
            if not user.get("name") and user.get("username"):
                user["name"] = user["username"]
            if not user.get("role"):
                user["role"] = "user"
        return user
    except Exception:
        return None


def is_logged_in():
    return get_current_user() is not None


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("login"))

        role = user.get("role") or session.get("role") or "user"
        session["role"] = role  # keep session consistent with DB
        if role != "admin":
            # Users should not be able to access admin routes.
            return redirect(url_for("index"))

        return view_func(*args, **kwargs)

    return wrapper


def get_or_create_cart(user_id):
    cart = carts_collection.find_one({"user_id": user_id})
    if cart:
        return cart
    new_cart = {"user_id": user_id, "items": [], "created_at": datetime.utcnow()}
    carts_collection.insert_one(new_cart)
    return carts_collection.find_one({"user_id": user_id})


def build_product_query(user, subject, semester, branch):
    query = {}
    if user:
        query["seller_college"] = (user.get("college") or "").strip()

    if subject:
        query["subject"] = subject
    if semester:
        query["semester"] = semester
    if branch:
        query["branch"] = branch
    return query


def demand_score(product):
    return int(product.get("views", 0)) + (2 * int(product.get("add_to_cart_count", 0)))


@app.route("/")
def index():
    user = get_current_user()
    subject = (request.args.get("subject") or "").strip()
    semester = (request.args.get("semester") or "").strip()
    branch = (request.args.get("branch") or "").strip()

    query = build_product_query(user, subject, semester, branch)
    products = list(products_collection.find(query).sort("created_at", -1))
    for product in products:
        product["is_high_demand"] = demand_score(product) >= 6

    filter_base = {}
    if user:
        filter_base["seller_college"] = (user.get("college") or "").strip()
    subjects = sorted(v for v in products_collection.distinct("subject", filter_base) if v)
    semesters = sorted(v for v in products_collection.distinct("semester", filter_base) if v)
    branches = sorted(v for v in products_collection.distinct("branch", filter_base) if v)

    return render_template(
        "index.html",
        products=products,
        user=user,
        subjects=subjects,
        semesters=semesters,
        branches=branches,
        selected={"subject": subject, "semester": semester, "branch": branch},
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", error=None)

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    college = (request.form.get("college") or "").strip()

    if not name or not email or not password or not college:
        return render_template("signup.html", error="All fields are required."), 400

    existing_user = users_collection.find_one({"email": email})
    if existing_user:
        return render_template("signup.html", error="Email already registered."), 400

    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    result = users_collection.insert_one(
        {
            # Store beginner-friendly username as "name" from the form.
            "username": name,
            "name": name,
            "email": email,
            "college": college,
            "password": hashed_password,
            "role": "user",
            "created_at": datetime.utcnow(),
        }
    )
    user_id = str(result.inserted_id)
    session["user_id"] = user_id
    session["role"] = "user"
    get_or_create_cart(user_id)
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()

    user = users_collection.find_one({"email": email})
    if not user or not bcrypt.check_password_hash(user["password"], password):
        return render_template("login.html", error="Invalid email or password."), 400

    session["user_id"] = str(user["_id"])
    session["role"] = user.get("role") or "user"
    get_or_create_cart(str(user["_id"]))

    if session["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

 
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    user = get_current_user()
    # Simple admin stats for learning/testing.
    total_users = users_collection.count_documents({})
    total_products = products_collection.count_documents({})
    total_carts = carts_collection.count_documents({})
    return render_template(
        "admin_dashboard.html",
        user=user,
        total_users=total_users,
        total_products=total_products,
        total_carts=total_carts,
    )


@app.route("/add", methods=["GET"])
def add_form():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("add.html", error=None)


@app.route("/add", methods=["POST"])
def add_product():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    price_raw = (request.form.get("price") or "").strip()
    subject = (request.form.get("subject") or "").strip()
    semester = (request.form.get("semester") or "").strip()
    branch = (request.form.get("branch") or "").strip()
    condition = (request.form.get("condition") or "").strip()

    error = None
    try:
        price = float(price_raw)
        if price < 0:
            raise ValueError("price must be >= 0")
    except ValueError:
        error = "Please enter a valid non-negative price."

    if not error and not name:
        error = "Product name is required."
    if not error and (not subject or not semester or not branch):
        error = "Subject, semester and branch are required."
    if not error and condition not in VALID_CONDITIONS:
        error = "Condition must be New, Good or Used."

    if error:
        return render_template("add.html", error=error), 400

    products_collection.insert_one(
        {
            "name": name,
            "price": price,
            "description": description,
            "subject": subject,
            "semester": semester,
            "branch": branch,
            "condition": condition,
            "seller_id": str(user["_id"]),
            "seller_name": user.get("name", ""),
            "seller_college": user.get("college", ""),
            "views": 0,
            "add_to_cart_count": 0,
            "created_at": datetime.utcnow(),
        }
    )
    return redirect(url_for("index"))


@app.route("/product/<product_id>")
def product_detail(product_id):
    user = get_current_user()
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
    except Exception:
        return redirect(url_for("index"))

    if not product:
        return redirect(url_for("index"))

    if user:
        user_college = (user.get("college") or "").strip()
        if (product.get("seller_college") or "").strip() != user_college:
            return redirect(url_for("index"))

    products_collection.update_one({"_id": product["_id"]}, {"$inc": {"views": 1}})
    product["views"] = int(product.get("views", 0)) + 1
    product["is_high_demand"] = demand_score(product) >= 6
    return render_template("product.html", product=product, user=user)


@app.route("/add_to_cart/<product_id>", methods=["POST"])
def add_to_cart(product_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
    except Exception:
        return redirect(url_for("index"))

    if not product:
        return redirect(url_for("index"))

    user_college = (user.get("college") or "").strip()
    if (product.get("seller_college") or "").strip() != user_college:
        return redirect(url_for("index"))

    user_id = str(user["_id"])
    cart = get_or_create_cart(user_id)
    items = cart.get("items", [])
    product_id_str = str(product["_id"])

    found = False
    for item in items:
        if item.get("product_id") == product_id_str:
            item["quantity"] = item.get("quantity", 1) + 1
            found = True
            break

    if not found:
        items.append(
            {
                "product_id": product_id_str,
                "name": product.get("name", "Unknown Product"),
                "price": float(product.get("price", 0)),
                "quantity": 1,
            }
        )

    carts_collection.update_one(
        {"user_id": user_id},
        {"$set": {"items": items, "updated_at": datetime.utcnow()}},
    )
    products_collection.update_one({"_id": product["_id"]}, {"$inc": {"add_to_cart_count": 1}})
    return redirect(url_for("view_cart"))


@app.route("/swap/request/<product_id>", methods=["GET", "POST"])
def request_swap(product_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    try:
        wanted_product = products_collection.find_one({"_id": ObjectId(product_id)})
    except Exception:
        return redirect(url_for("index"))
    if not wanted_product:
        return redirect(url_for("index"))

    user_id = str(user["_id"])
    if wanted_product.get("seller_id") == user_id:
        return redirect(url_for("index"))

    own_products = list(products_collection.find({"seller_id": user_id}).sort("created_at", -1))

    if request.method == "GET":
        return render_template(
            "swap_request.html",
            wanted_product=wanted_product,
            own_products=own_products,
            error=None,
            user=user,
        )

    offered_product_id = (request.form.get("offered_product_id") or "").strip()
    note = (request.form.get("note") or "").strip()

    try:
        offered_product = products_collection.find_one({"_id": ObjectId(offered_product_id)})
    except Exception:
        offered_product = None

    if not offered_product or offered_product.get("seller_id") != user_id:
        return render_template(
            "swap_request.html",
            wanted_product=wanted_product,
            own_products=own_products,
            error="Select one of your own products to offer.",
            user=user,
        ), 400

    existing_pending = swaps_collection.find_one(
        {
            "wanted_product_id": str(wanted_product["_id"]),
            "offered_product_id": str(offered_product["_id"]),
            "requester_id": user_id,
            "status": "pending",
        }
    )
    if existing_pending:
        return redirect(url_for("swaps", message="Swap request already pending."))

    swaps_collection.insert_one(
        {
            "wanted_product_id": str(wanted_product["_id"]),
            "wanted_product_name": wanted_product.get("name", ""),
            "owner_id": wanted_product.get("seller_id", ""),
            "owner_name": wanted_product.get("seller_name", ""),
            "requester_id": user_id,
            "requester_name": user.get("name", ""),
            "offered_product_id": str(offered_product["_id"]),
            "offered_product_name": offered_product.get("name", ""),
            "status": "pending",
            "note": note,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )
    return redirect(url_for("swaps", message="Swap request sent."))


@app.route("/swaps")
def swaps():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    user_id = str(user["_id"])
    incoming_swaps = list(swaps_collection.find({"owner_id": user_id}).sort("created_at", -1))
    outgoing_swaps = list(swaps_collection.find({"requester_id": user_id}).sort("created_at", -1))
    message = (request.args.get("message") or "").strip()
    return render_template(
        "swaps.html",
        incoming_swaps=incoming_swaps,
        outgoing_swaps=outgoing_swaps,
        message=message,
        user=user,
    )


@app.route("/swap/respond/<swap_id>/<action>", methods=["POST"])
def respond_swap(swap_id, action):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if action not in {"accept", "reject"}:
        return redirect(url_for("swaps"))

    try:
        swap = swaps_collection.find_one({"_id": ObjectId(swap_id)})
    except Exception:
        return redirect(url_for("swaps"))

    if not swap:
        return redirect(url_for("swaps"))

    user_id = str(user["_id"])
    if swap.get("owner_id") != user_id:
        return redirect(url_for("swaps"))

    if swap.get("status") != "pending":
        return redirect(url_for("swaps", message="This request was already processed."))

    new_status = "accepted" if action == "accept" else "rejected"
    swaps_collection.update_one(
        {"_id": swap["_id"]},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}},
    )
    return redirect(url_for("swaps", message=f"Swap request {new_status}."))


@app.route("/cart")
def view_cart():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    cart = get_or_create_cart(str(user["_id"]))
    items = cart.get("items", [])
    total = sum(item.get("price", 0) * item.get("quantity", 0) for item in items)
    return render_template("cart.html", items=items, total=total, user=user)


@app.route("/checkout")
def checkout():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    cart = get_or_create_cart(str(user["_id"]))
    items = cart.get("items", [])
    total = sum(item.get("price", 0) * item.get("quantity", 0) for item in items)
    return render_template("payment.html", items=items, total=total, success=False, user=user)


@app.route("/pay", methods=["POST"])
def pay():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    user_id = str(user["_id"])
    carts_collection.update_one(
        {"user_id": user_id},
        {"$set": {"items": [], "updated_at": datetime.utcnow()}},
    )
    return render_template("payment.html", items=[], total=0, success=True, user=user)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)

