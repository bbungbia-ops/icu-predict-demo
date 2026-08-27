import re
import secrets

from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from models.database import create_organization_account, get_db_connection
from models.license_client import validate_icu_license

auth_bp = Blueprint('auth', __name__)


def get_csrf_token():
    """Return a per-session token used on registration and purchase forms."""
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    return token


def valid_csrf_token():
    submitted = request.form.get('csrf_token', '')
    expected = session.get('csrf_token', '')
    return bool(submitted and expected and secrets.compare_digest(submitted, expected))


@auth_bp.app_context_processor
def inject_security_helpers():
    return {'csrf_token': get_csrf_token}


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def establish_session(user, license_check):
    """Store only identity and license state in the signed Flask session."""
    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['role'] = user['role']
    session['organization_id'] = user['organization_id']
    session['organization_name'] = user['organization_name']
    session['organization_code'] = user['organization_code']
    session['license_valid'] = license_check.valid
    session['license_plan'] = license_check.plan_code
    session['license_expires_at'] = license_check.expires_at
    get_csrf_token()


@auth_bp.before_app_request
def keep_unlicensed_accounts_in_commercial_flow():
    """In an enforced deployment, pending customers may only manage their order.

    This keeps a newly registered organization out of clinical screens until its
    license has been activated, while still allowing it to complete checkout.
    The local demo keeps its former open behavior unless enforcement is enabled.
    """
    if not current_app.config.get('LICENSE_ENFORCEMENT_ENABLED'):
        return None
    if not session.get('user_id') or session.get('license_valid'):
        return None
    endpoint = request.endpoint or ''
    permitted = {
        'auth.login', 'auth.logout', 'auth.register',
        'account.subscription', 'account.purchase_plan', 'account.customer_order',
        'static',
    }
    if endpoint in permitted or endpoint.startswith('static'):
        return None
    flash('Tài khoản tổ chức cần có license đang hoạt động trước khi sử dụng các màn hình lâm sàng.', 'error')
    return redirect(url_for('account.subscription'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db_path = current_app.config['DATABASE_PATH']
        conn = get_db_connection(db_path)
        user = conn.execute(
            '''SELECT u.*, o.name AS organization_name, o.organization_code,
                      o.license_key AS organization_license_key
               FROM users u
               LEFT JOIN organizations o ON o.id = u.organization_id
               WHERE u.username = ?''',
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            license_check = validate_icu_license(
                current_app.config,
                license_key=user['organization_license_key'],
            )
            if not license_check.valid:
                messages = {
                    'configuration_missing': 'Hệ thống chưa được cấu hình license hợp lệ. Vui lòng liên hệ quản trị viên.',
                    'validation_unavailable': 'Không thể kiểm tra license lúc này. Vui lòng thử lại hoặc liên hệ quản trị viên.',
                    'expired': 'License ICU Predict đã hết hạn. Vui lòng liên hệ quản trị viên để gia hạn.',
                    'revoked': 'License ICU Predict đã bị thu hồi. Vui lòng liên hệ quản trị viên.',
                    'pending_payment': 'License đang chờ xác nhận thanh toán.',
                    'not_found': 'Không tìm thấy license của hệ thống.',
                    'authorization_failed': 'Không thể xác thực kết nối license. Vui lòng liên hệ quản trị viên.',
                    'invalid_response': 'Dịch vụ license trả về dữ liệu không hợp lệ. Vui lòng liên hệ quản trị viên.',
                }
                message = messages.get(license_check.reason, 'License không hợp lệ. Vui lòng liên hệ quản trị viên.')
                # A customer with an organization must still be able to see a
                # pending order or buy its first key.  The global guard above
                # limits this session to commercial screens until activation.
                if user['organization_id']:
                    establish_session(user, license_check)
                    flash(f'{message} Bạn vẫn có thể xem và hoàn tất đơn hàng của tổ chức.', 'error')
                    return redirect(url_for('account.subscription'))
                flash(message, 'error')
                return render_template('login.html')
            establish_session(user, license_check)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu.', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Self-service registration for the first administrator of an organization."""
    if session.get('user_id'):
        return redirect(url_for('account.subscription'))
    if request.method == 'POST':
        if not valid_csrf_token():
            flash('Phiên đăng ký không hợp lệ. Vui lòng thử lại.', 'error')
            return redirect(url_for('auth.register'))

        organization_name = request.form.get('organization_name', '').strip()
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not 2 <= len(organization_name) <= 150 or not 2 <= len(full_name) <= 100:
            flash('Vui lòng nhập tên tổ chức và họ tên từ 2 ký tự trở lên.', 'error')
        elif not re.fullmatch(r'[a-z0-9._-]{4,40}', username):
            flash('Tên đăng nhập gồm 4–40 ký tự: chữ thường, số, dấu chấm, gạch dưới hoặc gạch ngang.', 'error')
        elif not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email) or len(email) > 150:
            flash('Email chưa đúng định dạng.', 'error')
        elif not 8 <= len(password) <= 128:
            flash('Mật khẩu cần có từ 8 đến 128 ký tự.', 'error')
        elif password != password_confirm:
            flash('Xác nhận mật khẩu chưa khớp.', 'error')
        else:
            try:
                account = create_organization_account(
                    current_app.config['DATABASE_PATH'],
                    organization_name=organization_name,
                    full_name=full_name,
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password),
                )
            except ValueError as exc:
                flash(str(exc), 'error')
            except RuntimeError:
                flash('Không thể tạo tài khoản lúc này. Vui lòng thử lại.', 'error')
            else:
                session.clear()
                session['user_id'] = account['user_id']
                session['username'] = username
                session['full_name'] = full_name
                session['role'] = 'organization_admin'
                session['organization_id'] = account['organization_id']
                session['organization_name'] = organization_name
                session['organization_code'] = account['organization_code']
                session['license_valid'] = False
                session['license_plan'] = None
                session['license_expires_at'] = None
                get_csrf_token()
                flash('Đã tạo tài khoản tổ chức. Hãy chọn gói để tạo đơn hàng và nhận hướng dẫn thanh toán.', 'success')
                return redirect(url_for('account.subscription'))

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
