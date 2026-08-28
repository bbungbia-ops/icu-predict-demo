"""Flask application for the ICU Predict license administration portal."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import unicodedata
from datetime import UTC, datetime
from functools import wraps

from flask import Blueprint, Flask, Response, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from license_admin.config import Config
from license_admin.database import (
    activate_order,
    create_order,
    expire_due_licenses,
    get_connection,
    get_order,
    init_db,
    utc_now,
    validate_license,
)
from license_admin.plans import PLAN_CATALOG, format_vnd, format_vnd_millions, payment_term_label


portal_bp = Blueprint("license_portal", __name__)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("license_portal.login"))
        return view(*args, **kwargs)

    return wrapped


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_form_csrf() -> bool:
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(expected and submitted and hmac.compare_digest(submitted, expected))


def verify_hmac(raw_body: bytes, supplied_signature: str | None, secret: str) -> bool:
    if not supplied_signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied_signature.strip())


def verify_sepay_signature(
    raw_body: bytes,
    supplied_signature: str | None,
    supplied_timestamp: str | None,
    secret: str,
    max_age_seconds: int,
) -> bool:
    """Verify SePay's HMAC-SHA256 signature and reject stale replays.

    SePay signs ``{unix_timestamp}.{raw_request_body}`` and prefixes the digest
    with ``sha256=``.  The raw body must be used exactly as received; parsing
    and serializing JSON before verification changes the signature.
    """
    if not secret or not supplied_signature or not supplied_timestamp:
        return False
    try:
        timestamp = int(supplied_timestamp)
    except (TypeError, ValueError):
        return False
    if timestamp <= 0 or abs(int(time.time()) - timestamp) > max_age_seconds:
        return False
    signed_payload = supplied_timestamp.strip().encode("ascii") + b"." + raw_body
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied_signature.strip())


def sepay_success_response() -> Response:
    """SePay treats only a 200/201 JSON response with success=true as delivered."""
    return Response('{"success": true}', status=200, mimetype="application/json")


def sepay_error_response(error: str, status_code: int) -> Response:
    return Response(
        json.dumps({"success": False, "error": error}, ensure_ascii=False),
        status=status_code,
        mimetype="application/json",
    )


def safe_sepay_payload(payload: dict) -> dict:
    """Keep enough audit data for reconciliation without retaining full bank text."""
    account_number = str(payload.get("accountNumber", "")).strip()
    return {
        "id": payload.get("id"),
        "gateway": payload.get("gateway"),
        "transactionDate": payload.get("transactionDate"),
        "accountNumberLast4": account_number[-4:] if account_number else None,
        "subAccount": payload.get("subAccount"),
        "code": payload.get("code"),
        "transferType": payload.get("transferType"),
        "transferAmount": payload.get("transferAmount"),
        "referenceCode": payload.get("referenceCode"),
    }


def normalize_transfer_text(value: str) -> str:
    """Normalize bank text while preserving the exact reference tokens."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", ascii_value).upper()


def find_pending_order_for_sepay(connection, payment_code: str, content: str):
    """Find an unpaid order through the SePay code, with a safe text fallback.

    A SePay payment code is preferred. The fallback handles bank descriptions
    that altered whitespace or punctuation while accepting only one candidate.
    """
    if payment_code:
        order = connection.execute(
            "SELECT * FROM orders WHERE transfer_content = ? AND payment_status = 'pending'",
            (payment_code,),
        ).fetchone()
        if order:
            return order
    normalized_content = normalize_transfer_text(content)
    if not normalized_content:
        return None
    matches = [
        order
        for order in connection.execute(
            "SELECT * FROM orders WHERE payment_status = 'pending'"
        ).fetchall()
        if normalize_transfer_text(order["transfer_content"]) in normalized_content
    ]
    return matches[0] if len(matches) == 1 else None


def plan_name(plan_code: str) -> str:
    return PLAN_CATALOG.get(plan_code, {}).get("name", plan_code)


def order_status_label(status: str) -> str:
    return {"pending": "Chờ thanh toán", "paid": "Đã thanh toán", "failed": "Thất bại"}.get(status, status)


def license_status_label(status: str) -> str:
    return {
        "pending_payment": "Chờ thanh toán",
        "active": "Đang hoạt động",
        "expired": "Đã hết hạn",
        "revoked": "Đã thu hồi",
    }.get(status, status)


@portal_bp.app_context_processor
def inject_helpers():
    return {
        "csrf_token": get_csrf_token,
        "plan_catalog": PLAN_CATALOG,
        "plan_name": plan_name,
        "format_vnd": format_vnd,
        "format_vnd_millions": format_vnd_millions,
        "payment_term_label": payment_term_label,
        "order_status_label": order_status_label,
        "license_status_label": license_status_label,
    }


@portal_bp.route("/")
@admin_required
def dashboard():
    connection = get_connection(current_app.config["DATABASE_PATH"])
    expire_due_licenses(connection)
    summary = {
        "active": connection.execute("SELECT COUNT(*) FROM license_keys WHERE status = 'active'").fetchone()[0],
        "pending": connection.execute("SELECT COUNT(*) FROM orders WHERE payment_status = 'pending'").fetchone()[0],
        "expired": connection.execute("SELECT COUNT(*) FROM license_keys WHERE status = 'expired'").fetchone()[0],
        "paid_total": connection.execute("SELECT COALESCE(SUM(amount_vnd), 0) FROM orders WHERE payment_status = 'paid'").fetchone()[0],
    }
    recent_orders = connection.execute(
        """
        SELECT o.*, l.organization_name, l.plan_code, l.license_key, l.status AS license_status
        FROM orders o JOIN license_keys l ON l.id = o.license_id
        ORDER BY o.id DESC LIMIT 8
        """
    ).fetchall()
    connection.close()
    return render_template("license_admin/dashboard.html", summary=summary, recent_orders=recent_orders)


@portal_bp.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("license_portal.dashboard"))
    if request.method == "POST":
        if not verify_form_csrf():
            flash("Phiên làm việc không hợp lệ. Hãy thử lại.", "error")
            return redirect(url_for("license_portal.login"))
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        connection = get_connection(current_app.config["DATABASE_PATH"])
        user = connection.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()
        connection.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["admin_id"] = user["id"]
            session["admin_username"] = user["username"]
            get_csrf_token()
            return redirect(url_for("license_portal.dashboard"))
        flash("Sai tên đăng nhập hoặc mật khẩu.", "error")
    return render_template("license_admin/login.html")


@portal_bp.route("/logout", methods=["POST"])
@admin_required
def logout():
    if verify_form_csrf():
        session.clear()
    return redirect(url_for("license_portal.login"))


@portal_bp.route("/orders")
@admin_required
def order_list():
    connection = get_connection(current_app.config["DATABASE_PATH"])
    expire_due_licenses(connection)
    orders = connection.execute(
        """
        SELECT o.*, l.organization_name, l.plan_code, l.license_key, l.status AS license_status
        FROM orders o JOIN license_keys l ON l.id = o.license_id
        ORDER BY o.id DESC
        """
    ).fetchall()
    connection.close()
    return render_template("license_admin/orders.html", orders=orders)


@portal_bp.route("/orders/new", methods=["GET", "POST"])
@admin_required
def order_create():
    if request.method == "POST":
        if not verify_form_csrf():
            flash("Phiên làm việc không hợp lệ. Hãy thử lại.", "error")
            return redirect(url_for("license_portal.order_create"))
        plan_code = request.form.get("plan_code", "")
        plan = PLAN_CATALOG.get(plan_code)
        organization_name = request.form.get("organization_name", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        notes = request.form.get("notes", "").strip()
        try:
            max_devices = int(request.form.get("max_devices", "1"))
        except ValueError:
            max_devices = 0
        if not plan or not organization_name or not contact_name or not 1 <= max_devices <= 500:
            flash("Vui lòng chọn gói và nhập đủ thông tin tổ chức; số thiết bị phải từ 1 đến 500.", "error")
            return redirect(url_for("license_portal.order_create"))

        amount_vnd = plan["amount_vnd"]
        validity_days = plan["validity_days"]
        if plan_code == "enterprise":
            try:
                amount_vnd = int(request.form.get("enterprise_amount_vnd", "0"))
                validity_days = int(request.form.get("enterprise_validity_days", "0"))
            except ValueError:
                amount_vnd = validity_days = 0
            if amount_vnd <= 0 or not 1 <= validity_days <= 1095:
                flash("Gói Doanh nghiệp cần có giá và thời hạn hợp lệ.", "error")
                return redirect(url_for("license_portal.order_create"))

        order_id = create_order(
            current_app.config["DATABASE_PATH"],
            plan_code=plan_code,
            organization_name=organization_name,
            contact_name=contact_name,
            contact_email=contact_email,
            amount_vnd=amount_vnd,
            validity_days=validity_days,
            max_devices=max_devices,
            notes=notes,
        )
        flash("Đã tạo đơn hàng và license key ở trạng thái chờ thanh toán.", "success")
        return redirect(url_for("license_portal.order_detail", order_id=order_id))
    return render_template("license_admin/order_create.html")


@portal_bp.route("/orders/<int:order_id>")
@admin_required
def order_detail(order_id: int):
    connection = get_connection(current_app.config["DATABASE_PATH"])
    expire_due_licenses(connection)
    order = get_order(connection, order_id)
    events = connection.execute(
        "SELECT * FROM webhook_events ORDER BY id DESC LIMIT 10"
    ).fetchall()
    connection.close()
    if not order:
        flash("Không tìm thấy đơn hàng.", "error")
        return redirect(url_for("license_portal.order_list"))
    return render_template("license_admin/order_detail.html", order=order, events=events)


@portal_bp.route("/orders/<int:order_id>/simulate-payment", methods=["POST"])
@admin_required
def simulate_payment(order_id: int):
    if not verify_form_csrf():
        flash("Phiên làm việc không hợp lệ. Hãy thử lại.", "error")
        return redirect(url_for("license_portal.order_detail", order_id=order_id))
    if not current_app.config["DEMO_MODE"]:
        flash("Chế độ mô phỏng thanh toán đã tắt.", "error")
        return redirect(url_for("license_portal.order_detail", order_id=order_id))
    connection = get_connection(current_app.config["DATABASE_PATH"])
    order = get_order(connection, order_id)
    if not order:
        connection.close()
        flash("Không tìm thấy đơn hàng.", "error")
        return redirect(url_for("license_portal.order_list"))
    if order["payment_status"] == "paid":
        connection.close()
        flash("Đơn hàng đã được thanh toán trước đó.", "error")
        return redirect(url_for("license_portal.order_detail", order_id=order_id))
    activate_order(
        connection,
        order_id=order_id,
        transaction_id=f"DEMO-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        payer_name="Thanh toán mô phỏng",
    )
    connection.close()
    flash("Đã mô phỏng thanh toán thành công và kích hoạt license key.", "success")
    return redirect(url_for("license_portal.order_detail", order_id=order_id))


@portal_bp.route("/licenses")
@admin_required
def license_list():
    connection = get_connection(current_app.config["DATABASE_PATH"])
    expire_due_licenses(connection)
    licenses = connection.execute(
        """
        SELECT l.*, o.order_code, o.payment_status, o.amount_vnd
        FROM license_keys l JOIN orders o ON o.license_id = l.id
        ORDER BY l.id DESC
        """
    ).fetchall()
    connection.close()
    return render_template("license_admin/licenses.html", licenses=licenses)


@portal_bp.route("/licenses/<int:license_id>")
@admin_required
def license_detail(license_id: int):
    connection = get_connection(current_app.config["DATABASE_PATH"])
    expire_due_licenses(connection)
    license_row = connection.execute(
        """
        SELECT l.*, o.id AS order_id, o.order_code, o.amount_vnd, o.payment_status,
               o.transfer_content, o.paid_at
        FROM license_keys l JOIN orders o ON o.license_id = l.id
        WHERE l.id = ?
        """,
        (license_id,),
    ).fetchone()
    validations = connection.execute(
        "SELECT * FROM license_validations WHERE license_id = ? ORDER BY id DESC LIMIT 20", (license_id,)
    ).fetchall()
    connection.close()
    if not license_row:
        flash("Không tìm thấy license key.", "error")
        return redirect(url_for("license_portal.license_list"))
    return render_template("license_admin/license_detail.html", license_row=license_row, validations=validations)


@portal_bp.route("/licenses/<int:license_id>/revoke", methods=["POST"])
@admin_required
def revoke_license(license_id: int):
    if not verify_form_csrf():
        flash("Phiên làm việc không hợp lệ. Hãy thử lại.", "error")
        return redirect(url_for("license_portal.license_detail", license_id=license_id))
    connection = get_connection(current_app.config["DATABASE_PATH"])
    changed = connection.execute(
        "UPDATE license_keys SET status = 'revoked' WHERE id = ? AND status = 'active'", (license_id,)
    ).rowcount
    connection.commit()
    connection.close()
    flash("Đã thu hồi license key." if changed else "License không ở trạng thái hoạt động nên không thể thu hồi.", "success" if changed else "error")
    return redirect(url_for("license_portal.license_detail", license_id=license_id))


def record_webhook_event(connection, *, event_id: str | None, signature_valid: bool, status: str, payload: dict, message: str) -> None:
    connection.execute(
        """
        INSERT INTO webhook_events
        (provider_event_id, received_at, signature_valid, processing_status, payload_json, message)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_event_id) DO NOTHING
        """,
        (event_id, utc_now(), int(signature_valid), status, json.dumps(payload, ensure_ascii=False), message),
    )
    connection.commit()


@portal_bp.route("/webhooks/bank/payment", methods=["POST"])
def bank_webhook():
    raw_body = request.get_data(cache=False)
    supplied_signature = request.headers.get("X-Bank-Signature")
    signature_valid = verify_hmac(raw_body, supplied_signature, current_app.config["BANK_WEBHOOK_SECRET"])
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}

    event_id = str(payload.get("event_id", "")).strip() or None
    connection = get_connection(current_app.config["DATABASE_PATH"])
    if not signature_valid:
        record_webhook_event(
            connection, event_id=event_id, signature_valid=False, status="rejected", payload=payload,
            message="Chữ ký webhook không hợp lệ.",
        )
        connection.close()
        return jsonify({"ok": False, "error": "invalid_signature"}), 401
    if not payload or not event_id:
        record_webhook_event(
            connection, event_id=event_id, signature_valid=True, status="rejected", payload=payload,
            message="Thiếu event_id hoặc payload JSON không hợp lệ.",
        )
        connection.close()
        return jsonify({"ok": False, "error": "invalid_payload"}), 400
    if connection.execute("SELECT 1 FROM webhook_events WHERE provider_event_id = ?", (event_id,)).fetchone():
        connection.close()
        return jsonify({"ok": True, "status": "duplicate"})

    transfer_content = str(payload.get("transfer_content", "")).strip().upper()
    transaction_id = str(payload.get("transaction_id", "")).strip()
    payment_status = str(payload.get("status", "")).strip().lower()
    try:
        amount = int(payload.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0
    payer_name = str(payload.get("payer_name", "")).strip() or None
    if payment_status != "success" or not transaction_id or not transfer_content or amount <= 0:
        record_webhook_event(
            connection, event_id=event_id, signature_valid=True, status="ignored", payload=payload,
            message="Giao dịch không đủ điều kiện thanh toán thành công.",
        )
        connection.close()
        return jsonify({"ok": True, "status": "ignored"})

    order = connection.execute(
        "SELECT * FROM orders WHERE transfer_content = ? AND payment_status = 'pending'", (transfer_content,)
    ).fetchone()
    if not order:
        record_webhook_event(
            connection, event_id=event_id, signature_valid=True, status="unmatched", payload=payload,
            message="Không tìm thấy đơn chờ thanh toán với nội dung chuyển khoản này.",
        )
        connection.close()
        return jsonify({"ok": True, "status": "unmatched"})
    if amount != order["amount_vnd"]:
        record_webhook_event(
            connection, event_id=event_id, signature_valid=True, status="amount_mismatch", payload=payload,
            message="Số tiền nhận được không khớp với đơn hàng.",
        )
        connection.close()
        return jsonify({"ok": True, "status": "amount_mismatch"})
    existing_transaction = connection.execute(
        "SELECT id FROM orders WHERE bank_transaction_id = ?", (transaction_id,)
    ).fetchone()
    if existing_transaction:
        record_webhook_event(
            connection, event_id=event_id, signature_valid=True, status="duplicate_transaction", payload=payload,
            message="Mã giao dịch ngân hàng đã được dùng cho một đơn khác.",
        )
        connection.close()
        return jsonify({"ok": True, "status": "duplicate_transaction"})
    activate_order(connection, order_id=order["id"], transaction_id=transaction_id, payer_name=payer_name)
    record_webhook_event(
        connection, event_id=event_id, signature_valid=True, status="activated", payload=payload,
        message=f"Đã kích hoạt license cho đơn {order['order_code']}.",
    )
    connection.close()
    return jsonify({"ok": True, "status": "activated", "order_code": order["order_code"]})


@portal_bp.route("/webhooks/sepay/payment", methods=["POST"])
def sepay_payment_webhook():
    """Receive a SePay inbound-transfer webhook and activate one matching key.

    This endpoint intentionally never accepts a browser/session credential.  It
    only trusts SePay's timestamped HMAC, then checks the direction, exact
    amount, unique transaction id, and unique transfer code before activation.
    """
    raw_body = request.get_data(cache=False)
    supplied_signature = request.headers.get("X-SePay-Signature")
    supplied_timestamp = request.headers.get("X-SePay-Timestamp")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    signature_valid = verify_sepay_signature(
        raw_body,
        supplied_signature,
        supplied_timestamp,
        current_app.config["SEPAY_WEBHOOK_SECRET"],
        current_app.config["SEPAY_WEBHOOK_MAX_AGE_SECONDS"],
    )
    safe_payload = safe_sepay_payload(payload)
    connection = get_connection(current_app.config["DATABASE_PATH"])
    if not signature_valid:
        # A spoofed request must not reserve a real SePay transaction id and
        # block its later legitimate delivery.
        rejected_event_id = "sepay-untrusted-" + hashlib.sha256(raw_body).hexdigest()
        record_webhook_event(
            connection,
            event_id=rejected_event_id,
            signature_valid=False,
            status="rejected",
            payload=safe_payload,
            message="Webhook SePay bị từ chối do chữ ký hoặc thời gian gửi không hợp lệ.",
        )
        connection.close()
        return sepay_error_response("invalid_signature", 401)

    sepay_id = str(payload.get("id", "")).strip()
    if not sepay_id:
        record_webhook_event(
            connection,
            event_id="sepay-invalid-" + hashlib.sha256(raw_body).hexdigest(),
            signature_valid=True,
            status="rejected",
            payload=safe_payload,
            message="Webhook SePay thiếu id giao dịch.",
        )
        connection.close()
        return sepay_error_response("invalid_payload", 400)
    event_id = f"sepay:{sepay_id}"
    if connection.execute("SELECT 1 FROM webhook_events WHERE provider_event_id = ?", (event_id,)).fetchone():
        connection.close()
        return sepay_success_response()

    transfer_type = str(payload.get("transferType", "")).strip().lower()
    payment_code = str(payload.get("code") or "").strip().upper()
    transfer_content = str(payload.get("content") or "").strip()
    raw_amount = payload.get("transferAmount", 0)
    try:
        amount = 0 if isinstance(raw_amount, bool) else int(raw_amount)
    except (TypeError, ValueError):
        amount = 0
    if transfer_type != "in" or amount <= 0:
        record_webhook_event(
            connection,
            event_id=event_id,
            signature_valid=True,
            status="ignored",
            payload=safe_payload,
            message="Webhook SePay không phải giao dịch tiền vào hợp lệ.",
        )
        connection.close()
        return sepay_success_response()

    order = find_pending_order_for_sepay(connection, payment_code, transfer_content)
    if not order:
        record_webhook_event(
            connection,
            event_id=event_id,
            signature_valid=True,
            status="unmatched",
            payload=safe_payload,
            message="Không tìm thấy đơn chờ thanh toán khớp mã SePay hoặc nội dung chuyển khoản.",
        )
        connection.close()
        return sepay_success_response()
    if amount != order["amount_vnd"]:
        record_webhook_event(
            connection,
            event_id=event_id,
            signature_valid=True,
            status="amount_mismatch",
            payload=safe_payload,
            message="Số tiền SePay nhận được không khớp giá trị đơn hàng.",
        )
        connection.close()
        return sepay_success_response()

    transaction_id = f"SEPAY-{sepay_id}"
    existing_transaction = connection.execute(
        "SELECT id FROM orders WHERE bank_transaction_id = ?", (transaction_id,)
    ).fetchone()
    if existing_transaction:
        record_webhook_event(
            connection,
            event_id=event_id,
            signature_valid=True,
            status="duplicate_transaction",
            payload=safe_payload,
            message="Mã giao dịch SePay đã được dùng cho một đơn hàng khác.",
        )
        connection.close()
        return sepay_success_response()

    payer_name = str(payload.get("description") or "").strip() or None
    activate_order(
        connection,
        order_id=order["id"],
        transaction_id=transaction_id,
        payer_name=payer_name,
    )
    record_webhook_event(
        connection,
        event_id=event_id,
        signature_valid=True,
        status="activated",
        payload=safe_payload,
        message=f"SePay đã kích hoạt license cho đơn {order['order_code']}.",
    )
    connection.close()
    return sepay_success_response()


@portal_bp.route("/api/v1/licenses/validate", methods=["POST"])
def license_validation_api():
    raw_body = request.get_data(cache=False)
    supplied_signature = request.headers.get("X-ICU-License-Signature")
    if not verify_hmac(raw_body, supplied_signature, current_app.config["ICU_INTEGRATION_SHARED_SECRET"]):
        return jsonify({"valid": False, "reason": "unauthorized"}), 401
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"valid": False, "reason": "invalid_payload"}), 400
    license_key = str(payload.get("license_key", "")).strip().upper()
    if not license_key:
        return jsonify({"valid": False, "reason": "missing_license_key"}), 400
    connection = get_connection(current_app.config["DATABASE_PATH"])
    result = validate_license(
        connection,
        license_key,
        str(payload.get("client_id", "")).strip() or None,
        str(payload.get("app_version", "")).strip() or None,
    )
    connection.close()
    return jsonify(result)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    init_db(app.config["DATABASE_PATH"], app.config["ADMIN_USERNAME"], app.config["ADMIN_PASSWORD"])
    app.register_blueprint(portal_bp)
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5050")),
        debug=application.config["DEBUG"],
    )
