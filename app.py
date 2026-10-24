import os
import random
import secrets
import sqlite3
from contextlib import closing
from functools import wraps
from datetime import date

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["DATABASE"] = os.environ.get(
    "DATABASE_PATH", os.path.join(app.root_path, "railway.db")
)

# Bookings and seat counts are demo data; account records persist in SQLite.
bookings = []
seat_inventory = {}

STATIONS = [
    "Hyderabad", "Secunderabad", "Kacheguda", "Warangal", "Vijayawada",
    "Visakhapatnam", "Chennai", "Bengaluru", "Mumbai", "Delhi",
]
CLASS_FARE = {"SL": 300, "3A": 800, "2A": 1200, "1A": 2000}
DEFAULT_SEATS = {"SL": 40, "3A": 20, "2A": 10, "1A": 5}
VALID_GENDERS = ["Male", "Female", "Other"]
BOOKING_STATUSES = ["CONFIRMED", "CANCELLED", "COMPLETED"]


def get_db_connection():
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    database_path = app.config["DATABASE"]
    if database_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(database_path)), exist_ok=True)
    with closing(get_db_connection()) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    member_id TEXT NOT NULL UNIQUE,
                    phone TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                )
                """
            )


def get_user(email):
    if not email:
        return None
    with closing(get_db_connection()) as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()
    return dict(row) if row else None


def create_user(user):
    with closing(get_db_connection()) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO users (email, name, member_id, phone, city, status, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["email"], user["name"], user["member_id"], user["phone"],
                    user["city"], user["status"], user["password_hash"],
                ),
            )


init_db()

TRAINS = [
    {
        "train_no": "12724",
        "name": "Swarna Jayanti Express",
        "source": "Hyderabad",
        "destination": "Delhi",
        "departure": "08:30",
        "arrival": "18:15",
        "duration": "9h 45m",
        "classes": {"SL": 580, "3A": 1200, "2A": 1850, "1A": 3100},
    },
    {
        "train_no": "12603",
        "name": "Telangana Express",
        "source": "Hyderabad",
        "destination": "Bengaluru",
        "departure": "10:15",
        "arrival": "15:50",
        "duration": "5h 35m",
        "classes": {"SL": 420, "3A": 890, "2A": 1450, "1A": 2450},
    },
    {
        "train_no": "12144",
        "name": "Godavari Express",
        "source": "Vijayawada",
        "destination": "Chennai",
        "departure": "06:40",
        "arrival": "12:25",
        "duration": "5h 45m",
        "classes": {"SL": 450, "3A": 960, "2A": 1550, "1A": 2650},
    },
    {
        "train_no": "11019",
        "name": "Mumbai Mail",
        "source": "Hyderabad",
        "destination": "Mumbai",
        "departure": "21:10",
        "arrival": "08:00",
        "duration": "10h 50m",
        "classes": {"SL": 610, "3A": 1290, "2A": 2000, "1A": 3400},
    },
    {
        "train_no": "17235",
        "name": "Prashanti Express",
        "source": "Secunderabad",
        "destination": "Visakhapatnam",
        "departure": "18:20",
        "arrival": "06:50",
        "duration": "12h 30m",
        "classes": {"SL": 520, "3A": 1100, "2A": 1750, "1A": 2900},
    },
]


def find_booking(pnr):
    """Return a booking dictionary by PNR if present."""
    for booking in bookings:
        if booking["pnr"] == pnr:
            return booking
    return None


def get_train_by_number(train_no):
    for train in TRAINS:
        if train["train_no"] == train_no:
            return train
    return None


def get_available_trains(source, destination):
    if not source or not destination or source == destination:
        return []
    return [
        train for train in TRAINS
        if train["source"] == source and train["destination"] == destination
    ]


def get_seats_available(train_no, journey_date, train_class):
    key = (train_no, journey_date, train_class)
    return seat_inventory.setdefault(key, DEFAULT_SEATS[train_class])


def resolve_train_for_route(form):
    train_no = form.get("train_no", "")
    if train_no:
        train = get_train_by_number(train_no)
        if train:
            return train

    source = form.get("source", "")
    destination = form.get("destination", "")
    trains = get_available_trains(source, destination)
    if trains:
        return trains[0]

    if source and destination and source != destination:
        return {
            "train_no": f"GEN-{source[:3].upper()}{destination[:3].upper()}",
            "name": f"{source} to {destination} Service",
            "source": source,
            "destination": destination,
            "departure": "--:--",
            "arrival": "--:--",
            "duration": "On request",
            "classes": CLASS_FARE.copy(),
        }
    return None


def validate_booking(form):
    """Return a list of error messages (empty list means the data is valid)."""
    errors = []
    name = form.get("name", "").strip()
    age = form.get("age", "").strip()
    phone = form.get("phone", "").strip()
    email = form.get("email", "").strip()
    source = form.get("source", "")
    destination = form.get("destination", "")
    journey_date = form.get("journey_date", "")
    train_class = form.get("train_class", "")
    train_no = form.get("train_no", "")
    passengers = form.get("passengers", "").strip()
    gender = form.get("gender", "Other")

    if not name:
        errors.append("Passenger name is required.")
    elif len(name) < 2:
        errors.append("Passenger name must contain at least 2 characters.")

    if not age.isdigit() or not (1 <= int(age) <= 120):
        errors.append("Age must be a number between 1 and 120.")

    if not (phone.isdigit() and len(phone) == 10):
        errors.append("Phone number must be exactly 10 digits.")

    if "@" not in email or "." not in email:
        errors.append("Enter a valid email address.")

    if source not in STATIONS or destination not in STATIONS:
        errors.append("Select valid stations.")
    elif source == destination:
        errors.append("From and To stations cannot be the same.")

    if not journey_date:
        errors.append("Journey date is required.")
    else:
        try:
            journey_date_obj = date.fromisoformat(journey_date)
        except ValueError:
            errors.append("Journey date must be a valid date.")
        else:
            if journey_date_obj < date.today():
                errors.append("Journey date cannot be in the past.")

    if gender not in VALID_GENDERS:
        errors.append("Select a valid gender.")

    if train_no and not get_train_by_number(train_no):
        errors.append("Select a valid train.")
    elif not train_no and not resolve_train_for_route(form):
        errors.append("No train is available for the selected route.")

    if train_class not in CLASS_FARE:
        errors.append("Select a valid train class.")

    if not passengers.isdigit() or not (1 <= int(passengers) <= 6):
        errors.append("Number of passengers must be between 1 and 6.")

    return errors


def generate_pnr():
    return "".join(random.choices("0123456789", k=10))


def format_currency(value):
    return f"₹{value:,.0f}"


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if get_user(session.get("user_email")) is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


def safe_next_url(candidate):
    if candidate and candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    return url_for("index")


@app.route("/register", methods=["GET", "POST"])
def register():
    errors = []
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        city = request.form.get("city", "").strip()
        password = request.form.get("password", "")
        if not name:
            errors.append("Name is required.")
        if "@" not in email or "." not in email:
            errors.append("Enter a valid email address.")
        elif get_user(email):
            errors.append("An account with this email already exists.")
        if phone and (not phone.isdigit() or len(phone) != 10):
            errors.append("Phone number must be exactly 10 digits.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if not errors:
            create_user({
                "name": name,
                "member_id": f"IRCTC-{random.randint(10000, 99999)}",
                "email": email,
                "phone": phone,
                "city": city,
                "status": "Silver Member",
                "password_hash": generate_password_hash(password),
            })
            session.clear()
            session["user_email"] = email
            return redirect(url_for("index"))
    return render_template("register.html", errors=errors, form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    next_url = request.args.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_user(email)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_email"] = email
            return redirect(safe_next_url(request.form.get("next", "")))
        error = "Email or password is incorrect."
    return render_template("login.html", error=error, next_url=next_url)


@app.route("/")
@app.route("/home")
def index():
    source = request.args.get("source", "")
    destination = request.args.get("destination", "")
    journey_date = request.args.get("journey_date", "")

    available_trains = []
    if source and destination and source != destination:
        available_trains = get_available_trains(source, destination)

    return render_template(
        "index.html",
        stations=STATIONS,
        classes=CLASS_FARE,
        errors=[],
        form={
            "source": source,
            "destination": destination,
            "journey_date": journey_date,
        },
        today=date.today().isoformat(),
        genders=VALID_GENDERS,
        available_trains=available_trains,
        selected_train=request.args.get("train_no", ""),
    )


@app.route("/view-trains")
def view_trains():
    return render_template("view_trains.html", trains=TRAINS)


@app.route("/book-trains")
def book_trains():
    return render_template(
        "index.html",
        stations=STATIONS,
        classes=CLASS_FARE,
        errors=[],
        form={},
        today=date.today().isoformat(),
        genders=VALID_GENDERS,
        available_trains=[],
        selected_train="",
    )


@app.route("/fare-enquiry")
def fare_enquiry():
    source = request.args.get("source", "")
    destination = request.args.get("destination", "")
    class_name = request.args.get("class", "SL").upper()
    train = resolve_train_for_route({"source": source, "destination": destination})
    fare = "--"
    if train and class_name in train["classes"]:
        fare = train["classes"][class_name]

    return render_template(
        "fare_enquiry.html",
        stations=STATIONS,
        classes=CLASS_FARE,
        source=source,
        destination=destination,
        selected_class=class_name,
        fare=fare,
        train=train,
    )


@app.route("/profile")
@login_required
def profile():
    user = get_user(session["user_email"])
    profile_data = {key: value for key, value in user.items() if key != "password_hash"}
    return render_template("profile.html", profile=profile_data)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/book", methods=["POST"])
@login_required
def book():
    errors = validate_booking(request.form)
    if errors:
        return render_template(
            "index.html",
            stations=STATIONS,
            classes=CLASS_FARE,
            errors=errors,
            form=request.form,
            today=date.today().isoformat(),
            genders=VALID_GENDERS,
            available_trains=get_available_trains(request.form.get("source", ""), request.form.get("destination", "")),
            selected_train=request.form.get("train_no", ""),
        ), 400

    train = resolve_train_for_route(request.form)
    if train is None:
        return render_template(
            "index.html",
            stations=STATIONS,
            classes=CLASS_FARE,
            errors=["No train is available for the selected route."],
            form=request.form,
            today=date.today().isoformat(),
            genders=VALID_GENDERS,
            available_trains=[],
            selected_train="",
        ), 400

    passengers = int(request.form["passengers"])
    seats_left = get_seats_available(train["train_no"], request.form["journey_date"], request.form["train_class"])
    if passengers > seats_left:
        return render_template(
            "index.html",
            stations=STATIONS,
            classes=CLASS_FARE,
            errors=[f"Only {seats_left} seats are available in {request.form['train_class']} for this date."],
            form=request.form,
            today=date.today().isoformat(),
            genders=VALID_GENDERS,
            available_trains=get_available_trains(request.form.get("source", ""), request.form.get("destination", "")),
            selected_train=request.form.get("train_no", ""),
        ), 400
    ticket_fare = train["classes"][request.form["train_class"]] * passengers
    seat_inventory[(train["train_no"], request.form["journey_date"], request.form["train_class"])] = seats_left - passengers

    booking = {
        "pnr": generate_pnr(),
        "name": request.form["name"].strip(),
        "age": int(request.form["age"]),
        "gender": request.form.get("gender", "Other"),
        "phone": request.form["phone"].strip(),
        "email": request.form["email"].strip(),
        "source": request.form["source"],
        "destination": request.form["destination"],
        "journey_date": request.form["journey_date"],
        "train_no": train["train_no"],
        "train_name": train["name"],
        "train_class": request.form["train_class"],
        "passengers": passengers,
        "fare": ticket_fare,
        "status": "CONFIRMED",
        "owner_email": session["user_email"],
    }
    bookings.append(booking)
    return redirect(url_for("ticket", pnr=booking["pnr"]))


@app.route("/ticket/<pnr>")
@login_required
def ticket(pnr):
    booking = find_booking(pnr)
    if booking and booking.get("owner_email") == session["user_email"]:
        return render_template("ticket.html", b=booking, format_currency=format_currency)
    return "Ticket not found", 404


@app.route("/pnr-status", methods=["GET", "POST"])
@login_required
def pnr_status():
    pnr = request.values.get("pnr", "").strip()
    booking = find_booking(pnr) if pnr else None
    if booking and booking.get("owner_email") != session["user_email"]:
        booking = None
    return render_template("pnr_status.html", pnr=pnr, booking=booking)


@app.route("/bookings")
@login_required
def all_bookings():
    status_filter = request.args.get("status", "").strip().upper()
    search_term = request.args.get("search", "").strip().lower()

    user_bookings = [booking for booking in bookings if booking.get("owner_email") == session["user_email"]]
    filtered_bookings = list(user_bookings)
    if status_filter:
        filtered_bookings = [
            booking for booking in filtered_bookings if booking.get("status") == status_filter
        ]

    if search_term:
        filtered_bookings = [
            booking for booking in filtered_bookings
            if search_term in " ".join(
                [
                    booking.get("pnr", ""),
                    booking.get("name", ""),
                    booking.get("train_name", ""),
                    booking.get("phone", ""),
                    booking.get("source", ""),
                    booking.get("destination", ""),
                    booking.get("email", ""),
                ]
            ).lower()
        ]

    return render_template(
        "bookings.html",
        bookings=filtered_bookings,
        status_filter=status_filter,
        search_term=request.args.get("search", ""),
        total_bookings=len(user_bookings),
        total_confirmed=sum(1 for b in user_bookings if b.get("status") == "CONFIRMED"),
        total_cancelled=sum(1 for b in user_bookings if b.get("status") == "CANCELLED"),
        status_options=BOOKING_STATUSES,
    )


@app.route("/bookings/<pnr>/cancel", methods=["POST"])
@login_required
def cancel_booking(pnr):
    booking = find_booking(pnr)
    if booking is None or booking.get("owner_email") != session["user_email"]:
        return "Booking not found", 404

    if booking["status"] == "CONFIRMED":
        key = (booking["train_no"], booking["journey_date"], booking["train_class"])
        seat_inventory[key] = get_seats_available(*key) + booking["passengers"]
        booking["status"] = "CANCELLED"
    return redirect(url_for("all_bookings"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
