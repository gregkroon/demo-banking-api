"""
Tests for the demo banking API.
"""
import json
import pytest
from app.main import app, ACCOUNTS, TRANSACTIONS


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
# Account Transactions
# ---------------------------------------------------------------------------

def test_get_account_transactions_not_found(client, auth_headers):
    resp = client.get("/accounts/INVALID/transactions", headers=auth_headers)
    assert resp.status_code == 404


def test_get_account_transactions_empty(client, auth_headers):
    resp = client.get("/accounts/ACC001/transactions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["account_id"] == "ACC001"
    assert data["count"] == 0
    assert data["transactions"] == []


def test_get_account_transactions_as_sender(client, auth_headers):
    # Create transfer from ACC001 to ACC002
    client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": 1000}),
        content_type="application/json",
        headers=auth_headers,
    )
    resp = client.get("/accounts/ACC001/transactions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["transactions"][0]["from"] == "ACC001"
    assert data["transactions"][0]["to"] == "ACC002"
    assert data["transactions"][0]["amount"] == 1000


def test_get_account_transactions_as_receiver(client, auth_headers):
    # Create transfer from ACC001 to ACC002
    client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": 1000}),
        content_type="application/json",
        headers=auth_headers,
    )
    resp = client.get("/accounts/ACC002/transactions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["transactions"][0]["from"] == "ACC001"
    assert data["transactions"][0]["to"] == "ACC002"


def test_get_account_transactions_multiple(client, auth_headers):
    # Create multiple transfers involving ACC001
    client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC001", "to_account": "ACC002", "amount": 500}),
        content_type="application/json",
        headers=auth_headers,
    )
    client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC003", "to_account": "ACC001", "amount": 300}),
        content_type="application/json",
        headers=auth_headers,
    )
    client.post(
        "/transfers",
        data=json.dumps({"from_account": "ACC002", "to_account": "ACC003", "amount": 200}),
        content_type="application/json",
        headers=auth_headers,
    )

    # ACC001 should have 2 transactions (sender in first, receiver in second)
    resp = client.get("/accounts/ACC001/transactions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 2

    # ACC003 should have 2 transactions (sender in second, receiver in third)
    resp = client.get("/accounts/ACC003/transactions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 2
