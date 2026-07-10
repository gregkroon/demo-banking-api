"""
Tests for the demo banking API.
"""
import json
import datetime
import pytest
import jwt as pyjwt
from app.main import app, ACCOUNTS, TRANSACTIONS, SECRET_KEY


@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory state before each test."""
    ACCOUNTS.clear()
    ACCOUNTS.update({
        "ACC001": {"owner": "alice", "balance": 10000.00, "currency": "AUD"},
        "ACC002": {"owner": "bob",   "balance": 5000.00,  "currency": "AUD"},
        "ACC003": {"owner": "carol", "balance": 25000.00, "currency": "AUD"},
    })
    TRANSACTIONS.clear()
    yield


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "testuser", "password": "testpass"}),
        content_type="application/json",
    )
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_login_success(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "alice", "password": "secret"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_missing_fields(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "alice"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_no_token_rejected(client):
    resp = client.get("/accounts")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def test_list_accounts(client, auth_headers):
    resp = client.get("/accounts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 3


def test_get_account(client, auth_headers):
    resp = client.get("/accounts/ACC001", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["owner"] == "alice"
    assert data["balance"] == 10000.00


def test_get_account_not_found(client, auth_headers):
    resp = client.get("/accounts/INVALID", headers=auth_headers)
    assert resp.status_code == 404


def test_get_balance(client, auth_headers):
    resp = client.get("/accounts/ACC001/balance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["balance"] == 10000.00
    assert data["currency"] == "AUD"


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

def test_transfer_success(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": 1000}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["amount"] == 1000
    assert ACCOUNTS["ACC001"]["balance"] == 9000.00
    assert ACCOUNTS["ACC002"]["balance"] == 6000.00


def test_transfer_insufficient_funds(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC002", "to_account": "ACC001", "amount": 99999}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_transfer_invalid_account(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"from_account": "NONE", "to_account": "ACC001", "amount": 100}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_transfer_negative_amount(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": -500}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def test_list_transactions_empty(client, auth_headers):
    resp = client.get("/transactions", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 0


def test_list_transactions_after_transfer(client, auth_headers):
    client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": 500}),
        content_type="application/json",
        headers=auth_headers,
    )
    resp = client.get("/transactions", headers=auth_headers)
    assert resp.get_json()["count"] == 1


# ---------------------------------------------------------------------------
# Auth token error cases (require_auth decorator)
# ---------------------------------------------------------------------------

def test_expired_token_rejected(client):
    payload = {
        "sub": "testuser",
        "iat": datetime.datetime.utcnow() - datetime.timedelta(hours=10),
        "exp": datetime.datetime.utcnow() - datetime.timedelta(hours=2),
    }
    expired_token = pyjwt.encode(payload, SECRET_KEY, algorithm="HS256")
    resp = client.get("/accounts", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Token expired"


def test_invalid_token_rejected(client):
    resp = client.get("/accounts", headers={"Authorization": "Bearer this.is.not.a.valid.jwt"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid token"


def test_wrong_signature_token_rejected(client):
    payload = {
        "sub": "testuser",
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }
    bad_token = pyjwt.encode(payload, "wrong-secret-key", algorithm="HS256")
    resp = client.get("/accounts", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid token"


# ---------------------------------------------------------------------------
# Balance endpoint — missing account
# ---------------------------------------------------------------------------

def test_get_balance_not_found(client, auth_headers):
    resp = client.get("/accounts/NONEXISTENT/balance", headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.get_json()["error"].lower()


# ---------------------------------------------------------------------------
# Transfer — invalid destination account
# ---------------------------------------------------------------------------

def test_transfer_invalid_destination(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "INVALID_DST", "amount": 100}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert "INVALID_DST" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Transfer — missing required fields
# ---------------------------------------------------------------------------

def test_transfer_missing_from_account(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"to_account": "ACC002", "amount": 100}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_transfer_zero_amount(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": 0}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Login — edge cases
# ---------------------------------------------------------------------------

def test_login_empty_password(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "alice", "password": ""}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_login_empty_username(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "", "password": "secret"}),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_login_returns_expires_in(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"username": "alice", "password": "secret"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["expires_in"] == 28800


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

def test_health_returns_version(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# Account details
# ---------------------------------------------------------------------------

def test_get_account_returns_currency(client, auth_headers):
    resp = client.get("/accounts/ACC003", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["owner"] == "carol"
    assert data["currency"] == "AUD"
    assert data["balance"] == 25000.00


def test_transfer_records_initiator(client, auth_headers):
    resp = client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": 100}),
        content_type="application/json",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["initiated_by"] == "testuser"
    assert data["currency"] == "AUD"
    assert "tx_id" in data
    assert "timestamp" in data


def test_transfer_sequential_tx_ids(client, auth_headers):
    for i in range(3):
        client.post(
            "/transfers",
            data=json.dumps({"from_account": "ACC003", "to_account": "ACC002", "amount": 10}),
            content_type="application/json",
            headers=auth_headers,
        )
    assert TRANSACTIONS[0]["tx_id"] == "TX000001"
    assert TRANSACTIONS[1]["tx_id"] == "TX000002"
    assert TRANSACTIONS[2]["tx_id"] == "TX000003"


def test_get_balance_returns_as_of(client, auth_headers):
    resp = client.get("/accounts/ACC002/balance", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["account_id"] == "ACC002"
    assert "as_of" in data
    assert data["as_of"].endswith("Z")
