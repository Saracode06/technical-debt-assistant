# auth.py — intentionally-flawed for debt detection
# Debt seeded: hardcoded secret, missing error handling

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "app_db"

# DEBT: hardcoded secret — fake placeholder value
password = "FAKE_SECRET_123"


def get_connection():
    import socket

    # DEBT: missing error handling — connect() called with no try/except
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((DB_HOST, DB_PORT))
    return sock


def authenticate(username):
    conn = get_connection()
    # Simple placeholder logic
    if username and password:
        return True
    return False
