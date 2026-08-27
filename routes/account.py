"""Customer account, subscription, and self-service license purchase flow."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from license_admin.config import Config as LicenseAdminConfig
from license_admin.database import (
    create_order,
    expire_due_licenses,
    get_connection as get_license_connection,
    get_order,
    init_db as init_license_database,
)
from license_admin.plans import PLAN_CATALOG, format_vnd, format_vnd_millions, payment_term_label
from models.database import get_db_connection
from models.license_client import validate_icu_license
from routes.auth import login_required, valid_csrf_token


account_bp = Blueprint('account', __name__)


def billing_cycle_label(validity_days: int | None) -> str:
    if validity_days == 90:
        return '90 ngày'
    if validity_days == 365:
        return '12 tháng'
    return f'{validity_days} ngày' if validity_days else 'Theo hợp đồng'


def initialize_license_store() -> str:
    """Ensure the local demonstration has one initialized shared license store."""
    database_path = current_app.config['LICENSE_ADMIN_DATABASE_PATH']
    init_license_database(
        database_path,
        LicenseAdminConfig.ADMIN_USERNAME,
        LicenseAdminConfig.ADMIN_PASSWORD,
    )
    return database_path


def get_current_organization(connection):
    return connection.execute(
        '''SELECT o.*
           FROM organizations o
           JOIN users u ON u.organization_id = o.id
           WHERE u.id = ?''',
        (session.get('user_id'),),
    ).fetchone()


def get_customer_order(organization):
    """Return the central order linked to this organization, never by user input."""
    if not organization or not organization['license_order_id']:
        return None
    license_connection = get_license_connection(initialize_license_store())
    try:
        expire_due_licenses(license_connection)
        order = get_order(license_connection, organization['license_order_id'])
        if not order:
            return None
        # The customer reference prevents a local database pointer from showing
        # an order that belongs to another organization.
        customer_code = order['customer_organization_code']
        if customer_code and customer_code != organization['organization_code']:
            return None
        return order
    finally:
        license_connection.close()


def sync_local_subscription(connection, organization, order) -> None:
    """Cache an activated central license for legacy screens in the demo app."""
    if not order:
        return
    if order['license_status'] == 'active':
        existing = connection.execute(
            "SELECT id FROM subscriptions WHERE organization_id = ? AND status = 'active' LIMIT 1",
            (organization['id'],),
        ).fetchone()
        values = (
            order['plan_code'],
            'quarterly' if order['validity_days'] == 90 else 'annual',
            (order['activated_at'] or order['created_at'])[:10],
            order['expires_at'],
            order['max_devices'],
            PLAN_CATALOG[order['plan_code']]['monthly_amount_vnd'],
        )
        if existing:
            connection.execute(
                '''UPDATE subscriptions
                   SET plan_code = ?, billing_cycle = ?, starts_on = ?, renews_on = ?,
                       licensed_beds = 0, included_users = ?, monthly_price_vnd = ?
                   WHERE id = ?''',
                (*values, existing['id']),
            )
        else:
            connection.execute(
                '''INSERT INTO subscriptions
                   (organization_id, plan_code, billing_cycle, status, starts_on, renews_on,
                    licensed_beds, included_users, monthly_price_vnd)
                   VALUES (?, ?, ?, 'active', ?, ?, 0, ?, ?)''',
                (organization['id'], *values),
            )
    elif order['license_status'] in {'expired', 'revoked'}:
        connection.execute(
            "UPDATE subscriptions SET status = ? WHERE organization_id = ? AND status = 'active'",
            (order['license_status'], organization['id']),
        )
    connection.commit()


def update_session_license_state(order) -> None:
    if not order:
        return
    is_active = order['license_status'] == 'active'
    plan_code = order['plan_code'] if is_active else None
    expires_at = order['expires_at'] if is_active else None
    # Display status comes from the shared store in this local demo.  When
    # enforcement is enabled, clinical access still requires the signed
    # server-to-server validation call, preserving fail-closed behavior.
    if current_app.config.get('LICENSE_ENFORCEMENT_ENABLED'):
        verification = validate_icu_license(current_app.config, license_key=order['license_key'])
        is_active = verification.valid
        plan_code = verification.plan_code if verification.valid else None
        expires_at = verification.expires_at if verification.valid else None
    session['license_valid'] = is_active
    session['license_plan'] = plan_code
    session['license_expires_at'] = expires_at


def plan_cards():
    return [
        {
            'code': code,
            **plan,
            'monthly_price': format_vnd_millions(plan['monthly_amount_vnd']),
            'payment_term': payment_term_label(plan),
            'period': billing_cycle_label(plan['validity_days']),
        }
        for code, plan in PLAN_CATALOG.items()
    ]


@account_bp.route('/account/subscription')
@login_required
def subscription():
    connection = get_db_connection(current_app.config['DATABASE_PATH'])
    try:
        organization = get_current_organization(connection)
        order = get_customer_order(organization)
        sync_local_subscription(connection, organization, order)

        legacy_subscription = None
        if organization and not order:
            legacy_subscription = connection.execute(
                '''SELECT * FROM subscriptions
                   WHERE organization_id = ? AND status = 'active'
                   ORDER BY renews_on DESC LIMIT 1''',
                (organization['id'],),
            ).fetchone()
    finally:
        connection.close()

    if order:
        update_session_license_state(order)
        current_plan = PLAN_CATALOG.get(order['plan_code'])
        current_subscription = {
            'source': 'license',
            'status': order['license_status'],
            'starts_on': (order['activated_at'] or order['created_at'])[:10],
            'renews_on': order['expires_at'],
            'max_devices': order['max_devices'],
            'license_key': order['license_key'],
            'order_id': order['id'],
            'payment_status': order['payment_status'],
        }
    else:
        current_plan = PLAN_CATALOG.get(legacy_subscription['plan_code']) if legacy_subscription else None
        current_subscription = None
        if legacy_subscription:
            current_subscription = {
                'source': 'legacy_demo',
                'status': legacy_subscription['status'],
                'starts_on': legacy_subscription['starts_on'],
                'renews_on': legacy_subscription['renews_on'],
                'max_devices': legacy_subscription['included_users'],
                'license_key': None,
                'order_id': None,
                'payment_status': 'paid',
            }

    return render_template(
        'subscription.html',
        organization=organization,
        current_subscription=current_subscription,
        current_plan=current_plan,
        current_monthly_price=format_vnd_millions(current_plan['monthly_amount_vnd']) if current_plan else None,
        current_payment_term=payment_term_label(current_plan) if current_plan else None,
        current_period=billing_cycle_label(current_plan['validity_days']) if current_plan else None,
        plans=plan_cards(),
    )


@account_bp.route('/account/purchase', methods=['POST'])
@login_required
def purchase_plan():
    if not valid_csrf_token():
        flash('Phiên mua gói không hợp lệ. Vui lòng thử lại.', 'error')
        return redirect(url_for('account.subscription'))
    plan_code = request.form.get('plan_code', '')
    plan = PLAN_CATALOG.get(plan_code)
    if not plan:
        flash('Gói dịch vụ không hợp lệ.', 'error')
        return redirect(url_for('account.subscription'))
    if plan['amount_vnd'] is None:
        flash('Gói Doanh nghiệp cần khảo sát và báo giá theo phạm vi triển khai. Vui lòng liên hệ đội ngũ ICU Predict.', 'error')
        return redirect(url_for('account.subscription'))

    connection = get_db_connection(current_app.config['DATABASE_PATH'])
    try:
        organization = get_current_organization(connection)
        if not organization:
            flash('Không tìm thấy tổ chức của tài khoản này.', 'error')
            return redirect(url_for('auth.logout'))
        existing_order = get_customer_order(organization)
        if existing_order and existing_order['license_status'] in {'pending_payment', 'active'}:
            flash('Tổ chức đã có đơn hàng hoặc license đang hoạt động. Hãy mở chi tiết đơn để tiếp tục.', 'error')
            return redirect(url_for('account.customer_order', order_id=existing_order['id']))

        user = connection.execute(
            'SELECT full_name, email FROM users WHERE id = ?', (session['user_id'],)
        ).fetchone()
        order_id = create_order(
            initialize_license_store(),
            plan_code=plan_code,
            organization_name=organization['name'],
            contact_name=user['full_name'],
            contact_email=user['email'] or '',
            amount_vnd=plan['amount_vnd'],
            validity_days=plan['validity_days'],
            max_devices=plan['max_devices'],
            notes=f"Đơn tự tạo từ website người dùng · {organization['organization_code']}",
            customer_organization_code=organization['organization_code'],
        )
        license_connection = get_license_connection(initialize_license_store())
        try:
            order = get_order(license_connection, order_id)
        finally:
            license_connection.close()
        connection.execute(
            'UPDATE organizations SET license_key = ?, license_order_id = ? WHERE id = ?',
            (order['license_key'], order_id, organization['id']),
        )
        connection.commit()
    finally:
        connection.close()

    flash('Đã tạo đơn hàng và key chờ thanh toán. Hãy dùng đúng nội dung chuyển khoản để hệ thống kích hoạt tự động.', 'success')
    return redirect(url_for('account.customer_order', order_id=order_id))


@account_bp.route('/account/orders/<int:order_id>')
@login_required
def customer_order(order_id: int):
    connection = get_db_connection(current_app.config['DATABASE_PATH'])
    try:
        organization = get_current_organization(connection)
        if not organization or organization['license_order_id'] != order_id:
            flash('Bạn không có quyền xem đơn hàng này.', 'error')
            return redirect(url_for('account.subscription'))
        order = get_customer_order(organization)
        if not order:
            flash('Không tìm thấy đơn hàng trong hệ thống license.', 'error')
            return redirect(url_for('account.subscription'))
        sync_local_subscription(connection, organization, order)
    finally:
        connection.close()

    update_session_license_state(order)
    return render_template(
        'purchase_checkout.html',
        order=order,
        plan=PLAN_CATALOG.get(order['plan_code']),
        price=format_vnd(order['amount_vnd']),
        period=billing_cycle_label(order['validity_days']),
        bank_name=current_app.config['PAYMENT_BANK_NAME'],
        account_number=current_app.config['PAYMENT_ACCOUNT_NUMBER'],
        account_name=current_app.config['PAYMENT_ACCOUNT_NAME'],
    )
