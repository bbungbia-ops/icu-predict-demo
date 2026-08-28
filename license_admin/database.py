"""License persistence for local SQLite demos and deployed PostgreSQL."""

from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import UTC, datetime, timedelta

from models.database_compat import connect_database, is_postgres_database

from werkzeug.security import generate_password_hash


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def get_connection(database_path: str):
    """Open the shared PostgreSQL store online or a local SQLite file in demo."""
    if not is_postgres_database(database_path):
        from pathlib import Path

        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return connect_database(database_path)


def init_db(database_path: str, admin_username: str, admin_password: str) -> None:
    connection = get_connection(database_path)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS license_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            plan_code TEXT NOT NULL,
            organization_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_email TEXT,
            customer_organization_code TEXT,
            status TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            activated_at TEXT,
            expires_at TEXT,
            validity_days INTEGER NOT NULL,
            max_devices INTEGER NOT NULL DEFAULT 1,
            notes TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE NOT NULL,
            license_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL,
            transfer_content TEXT UNIQUE NOT NULL,
            payment_status TEXT NOT NULL,
            bank_transaction_id TEXT,
            payer_name TEXT,
            paid_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (license_id) REFERENCES license_keys(id)
        )
        """
    )
    license_columns = {row["name"] for row in cursor.execute("PRAGMA table_info(license_keys)").fetchall()}
    if "customer_organization_code" not in license_columns:
        cursor.execute("ALTER TABLE license_keys ADD COLUMN customer_organization_code TEXT")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_license_keys_customer_organization "
        "ON license_keys(customer_organization_code)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_event_id TEXT UNIQUE,
            received_at TEXT NOT NULL,
            signature_valid INTEGER NOT NULL,
            processing_status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            message TEXT
        )
        """
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_bank_transaction "
        "ON orders(bank_transaction_id) WHERE bank_transaction_id IS NOT NULL"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS license_validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id INTEGER,
            checked_at TEXT NOT NULL,
            client_id TEXT,
            app_version TEXT,
            result TEXT NOT NULL,
            FOREIGN KEY (license_id) REFERENCES license_keys(id)
        )
        """
    )
    existing = cursor.execute("SELECT id FROM admin_users WHERE username = ?", (admin_username,)).fetchone()
    if not existing:
        cursor.execute(
            "INSERT INTO admin_users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (admin_username, generate_password_hash(admin_password), utc_now()),
        )
    connection.commit()
    connection.close()


def make_license_key() -> str:
    chunks = [secrets.token_hex(3).upper() for _ in range(4)]
    return "ICU-" + "-".join(chunks)


def make_order_code() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"ORD-{stamp}-{secrets.token_hex(3).upper()}"


def make_transfer_content(order_code: str, customer_username: str | None = None) -> str:
    """Create a readable, unique payment reference for a single invoice."""
    suffix = order_code.rsplit("-", 1)[-1]
    if not customer_username:
        return f"ICUP-{suffix}"
    ascii_username = unicodedata.normalize("NFKD", customer_username).encode("ascii", "ignore").decode()
    username_token = re.sub(r"[^A-Za-z0-9]", "", ascii_username).upper()
    if not username_token:
        return f"ICUP-{suffix}"
    return f"THANHTOAN {username_token[:32]} {suffix}"


def create_order(
    database_path: str,
    *,
    plan_code: str,
    organization_name: str,
    contact_name: str,
    contact_email: str,
    amount_vnd: int,
    validity_days: int,
    max_devices: int,
    notes: str,
    customer_organization_code: str | None = None,
    customer_username: str | None = None,
) -> int:
    connection = get_connection(database_path)
    cursor = connection.cursor()
    license_key = make_license_key()
    for _ in range(5):
        if not cursor.execute("SELECT 1 FROM license_keys WHERE license_key = ?", (license_key,)).fetchone():
            break
        license_key = make_license_key()
    else:
        connection.close()
        raise RuntimeError("Không thể tạo license key duy nhất. Vui lòng thử lại.")

    created_at = utc_now()
    cursor.execute(
        """
        INSERT INTO license_keys
        (license_key, plan_code, organization_name, contact_name, contact_email,
         customer_organization_code, status, issued_at, validity_days, max_devices, notes)
        VALUES (?, ?, ?, ?, ?, ?, 'pending_payment', ?, ?, ?, ?)
        """,
        (
            license_key,
            plan_code,
            organization_name,
            contact_name,
            contact_email,
            customer_organization_code,
            created_at,
            validity_days,
            max_devices,
            notes,
        ),
    )
    license_id = cursor.lastrowid
    order_code = make_order_code()
    transfer_content = make_transfer_content(order_code, customer_username)
    cursor.execute(
        """
        INSERT INTO orders
        (order_code, license_id, amount_vnd, transfer_content, payment_status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
        """,
        (order_code, license_id, amount_vnd, transfer_content, created_at),
    )
    order_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return order_id


def expire_due_licenses(connection) -> None:
    today = datetime.now(UTC).date().isoformat()
    connection.execute(
        """
        UPDATE license_keys
        SET status = 'expired'
        WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at < ?
        """,
        (today,),
    )
    connection.commit()


def get_order(connection, order_id: int):
    return connection.execute(
        """
        SELECT o.*, l.license_key, l.plan_code, l.organization_name, l.contact_name,
               l.contact_email, l.customer_organization_code, l.status AS license_status,
               l.activated_at, l.expires_at, l.validity_days, l.max_devices, l.notes
        FROM orders o JOIN license_keys l ON l.id = o.license_id
        WHERE o.id = ?
        """,
        (order_id,),
    ).fetchone()


def activate_order(
    connection,
    *,
    order_id: int,
    transaction_id: str,
    payer_name: str | None,
) -> None:
    order = get_order(connection, order_id)
    if not order:
        raise ValueError("Không tìm thấy đơn hàng.")
    if order["payment_status"] == "paid":
        return
    activated_at = utc_now()
    expiry = (datetime.now(UTC).date() + timedelta(days=order["validity_days"])).isoformat()
    connection.execute(
        """
        UPDATE orders
        SET payment_status = 'paid', bank_transaction_id = ?, payer_name = ?, paid_at = ?
        WHERE id = ?
        """,
        (transaction_id, payer_name, activated_at, order_id),
    )
    connection.execute(
        """
        UPDATE license_keys
        SET status = 'active', activated_at = ?, expires_at = ?
        WHERE id = ?
        """,
        (activated_at, expiry, order["license_id"]),
    )
    connection.commit()


def validate_license(connection, license_key: str, client_id: str | None, app_version: str | None) -> dict:
    expire_due_licenses(connection)
    license_row = connection.execute("SELECT * FROM license_keys WHERE license_key = ?", (license_key,)).fetchone()
    if not license_row:
        connection.execute(
            "INSERT INTO license_validations (license_id, checked_at, client_id, app_version, result) VALUES (NULL, ?, ?, ?, 'not_found')",
            (utc_now(), client_id, app_version),
        )
        connection.commit()
        return {"valid": False, "reason": "not_found"}

    is_valid = license_row["status"] == "active"
    result = "valid" if is_valid else license_row["status"]
    connection.execute(
        "INSERT INTO license_validations (license_id, checked_at, client_id, app_version, result) VALUES (?, ?, ?, ?, ?)",
        (license_row["id"], utc_now(), client_id, app_version, result),
    )
    connection.commit()
    return {
        "valid": is_valid,
        "reason": result,
        "plan_code": license_row["plan_code"],
        "expires_at": license_row["expires_at"],
        "max_devices": license_row["max_devices"],
    }
