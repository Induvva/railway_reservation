from datetime import date, timedelta

import pytest

from app import app, bookings, init_db, seat_inventory, validate_booking


app.config["TESTING"] = True


@pytest.fixture(autouse=True)
def isolate_data(tmp_path):
    bookings.clear()
    seat_inventory.clear()
    app.config["DATABASE"] = str(tmp_path / "railway-test.db")
    init_db()


def create_account(client):
    return client.post("/register", data={
        "name": "Test User",
        "email": "test@example.com",
        "password": "test-password-123",
        "phone": "1234567890",
        "city": "Hyderabad",
    })


def test_validate_booking_rejects_invalid_values():
    form = {
        "name": "John Doe",
        "age": "30",
        "gender": "Male",
        "phone": "1234567890",
        "email": "john@example.com",
        "source": "Hyderabad",
        "destination": "Hyderabad",
        "journey_date": (date.today() - timedelta(days=1)).isoformat(),
        "train_class": "2A",
        "passengers": "2",
    }

    errors = validate_booking(form)
    assert any("cannot be the same" in error.lower() for error in errors)
    assert any("past" in error.lower() for error in errors)


def test_book_and_cancel_booking():
    client = app.test_client()
    create_account(client)
    payload = {
        "name": "Alice Smith",
        "age": "28",
        "gender": "Female",
        "phone": "9876543210",
        "email": "alice@example.com",
        "source": "Hyderabad",
        "destination": "Bengaluru",
        "journey_date": (date.today() + timedelta(days=5)).isoformat(),
        "train_class": "3A",
        "passengers": "2",
    }

    response = client.post("/book", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert b"Booking" in response.data or b"PNR" in response.data

    booking = bookings[0]
    inventory_key = (booking["train_no"], booking["journey_date"], booking["train_class"])
    assert seat_inventory[inventory_key] == 18
    cancel_response = client.post(f"/bookings/{booking['pnr']}/cancel")
    assert cancel_response.status_code == 302
    assert bookings[0]["status"] == "CANCELLED"
    assert seat_inventory[inventory_key] == 20


def test_bookings_page_supports_filters():
    client = app.test_client()
    create_account(client)
    payload = {
        "name": "Bob Singh",
        "age": "40",
        "gender": "Male",
        "phone": "9988776655",
        "email": "bob@example.com",
        "source": "Delhi",
        "destination": "Mumbai",
        "journey_date": (date.today() + timedelta(days=3)).isoformat(),
        "train_class": "SL",
        "passengers": "1",
    }
    client.post("/book", data=payload)

    response = client.get("/bookings?status=CONFIRMED&search=Bob")
    assert response.status_code == 200
    assert b"Bob Singh" in response.data


def test_portal_pages_and_fare_enquiry():
    client = app.test_client()

    home = client.get("/")
    assert home.status_code == 200
    assert b"Railway Reservation System" in home.data

    trains = client.get("/view-trains")
    assert trains.status_code == 200
    assert b"Swarna Jayanti Express" in trains.data

    fare = client.get("/fare-enquiry?source=Hyderabad&destination=Delhi&class=2A")
    assert fare.status_code == 200
    assert b"1850" in fare.data

    profile = client.get("/profile")
    assert profile.status_code == 302
    create_account(client)
    profile = client.get("/profile")
    assert profile.status_code == 200
    assert b"Profile" in profile.data

    logout = client.get("/logout")
    assert logout.status_code == 302


def test_registration_login_and_protected_routes():
    client = app.test_client()
    assert client.get("/bookings").status_code == 302
    create_account(client)
    client.get("/logout")

    login = client.post("/login", data={
        "email": "test@example.com",
        "password": "test-password-123",
    })
    assert login.status_code == 302
    assert client.get("/profile").status_code == 200

    invalid_login = client.post("/login", data={
        "email": "test@example.com",
        "password": "wrong-password",
    })
    assert b"incorrect" in invalid_login.data


def test_registered_account_survives_database_reinitialization():
    client = app.test_client()
    create_account(client)
    client.get("/logout")

    init_db()
    login = client.post("/login", data={
        "email": "test@example.com",
        "password": "test-password-123",
    })
    assert login.status_code == 302
    assert client.get("/profile").status_code == 200


def test_pnr_status_is_limited_to_signed_in_owner():
    owner = app.test_client()
    create_account(owner)
    payload = {
        "name": "Passenger One",
        "age": "30",
        "gender": "Other",
        "phone": "1234567890",
        "email": "passenger@example.com",
        "source": "Hyderabad",
        "destination": "Bengaluru",
        "journey_date": (date.today() + timedelta(days=4)).isoformat(),
        "train_class": "SL",
        "passengers": "1",
    }
    owner.post("/book", data=payload)
    pnr = bookings[0]["pnr"]
    assert b"CONFIRMED" in owner.get(f"/pnr-status?pnr={pnr}").data

    other_user = app.test_client()
    other_user.post("/register", data={
        "name": "Another User",
        "email": "another@example.com",
        "password": "another-password-123",
    })
    response = other_user.get(f"/pnr-status?pnr={pnr}")
    assert b"No booking was found" in response.data
