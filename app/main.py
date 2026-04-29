"""
Demo Banking API — Harness + Claude Code showcase
Intentionally ships with vulnerable deps for STO demo purposes.
"""
from flask import Flask, request, jsonify
from functools import wraps
import jwt
import datetime
import os

app = Flask(__name__)
SECRET_KEY = os.environ.get("SECRET_KEY", "demo-secret-key-change-in-prod")

# ---------------------------------------------------------------------------
# In-memory "database" (demo only)
# ---------------------------------------------------------------------------
ACCOUNTS = {
    "ACC001": {"owner": "alice", "balance": 10000.00, "currency": "AUD"},
    "ACC002": {"owner": "bob",   "balance": 5000.00,  "currency": "AUD"},
    "ACC003": {"owner": "carol", "balance": 25000.00, "currency": "AUD"},
}

TRANSACTIONS = []

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def generate_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = payload["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "1.0.0"}), 200


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = data.get("username", "")
    password = data.get("password", "")
    # Demo: any non-empty creds succeed
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    token = generate_token(username)
    return jsonify({"token": token, "expires_in": 28800}), 200


@app.route("/accounts", methods=["GET"])
@require_auth
def list_accounts():
    return jsonify({"accounts": list(ACCOUNTS.keys()), "count": len(ACCOUNTS)}), 200


@app.route("/accounts/<account_id>", methods=["GET"])
@require_auth
def get_account(account_id):
    account = ACCOUNTS.get(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404
    return jsonify({"account_id": account_id, **account}), 200


@app.route("/accounts/<account_id>/balance", methods=["GET"])
@require_auth
def get_balance(account_id):
    account = ACCOUNTS.get(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404
    return jsonify({
        "account_id": account_id,
        "balance": account["balance"],
        "currency": account["currency"],
        "as_of": datetime.datetime.utcnow().isoformat() + "Z",
    }), 200


@app.route("/transfers", methods=["POST"])
@require_auth
def transfer():
    data = request.get_json(force=True)
    from_id = data.get("from_account")
    to_id   = data.get("to_account")
    amount  = data.get("amount", 0)

    if not from_id or not to_id or amount <= 0:
        return jsonify({"error": "from_account, to_account, and positive amount required"}), 400

    src = ACCOUNTS.get(from_id)
    dst = ACCOUNTS.get(to_id)

    if not src:
        return jsonify({"error": f"Source account {from_id} not found"}), 404
    if not dst:
        return jsonify({"error": f"Destination account {to_id} not found"}), 404
    if src["balance"] < amount:
        return jsonify({"error": "Insufficient funds"}), 422

    src["balance"] -= amount
    dst["balance"] += amount

    tx = {
        "tx_id": f"TX{len(TRANSACTIONS)+1:06d}",
        "from": from_id,
        "to":   to_id,
        "amount": amount,
        "currency": src["currency"],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "initiated_by": request.user,
    }
    TRANSACTIONS.append(tx)

    return jsonify(tx), 201


@app.route("/transactions", methods=["GET"])
@require_auth
def list_transactions():
    return jsonify({"transactions": TRANSACTIONS, "count": len(TRANSACTIONS)}), 200


@app.route("/accounts/<account_id>/transactions", methods=["GET"])
@require_auth
def get_account_transactions(account_id):
    account = ACCOUNTS.get(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    # Filter transactions where account is sender or receiver
    account_txs = [
        tx for tx in TRANSACTIONS
        if tx["from"] == account_id or tx["to"] == account_id
    ]

    return jsonify({
        "account_id": account_id,
        "transactions": account_txs,
        "count": len(account_txs)
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
