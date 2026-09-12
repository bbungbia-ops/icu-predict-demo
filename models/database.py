import os
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash

from models.database_compat import DATABASE_INTEGRITY_ERRORS, connect_database


def get_db_connection(db_path):
    """Open the configured SQLite demo file or the shared PostgreSQL database."""
    return connect_database(db_path)


def init_db(
    db_path,
    admin_username='admin',
    admin_password='admin123',
    *,
    reset_admin_password=False,
):
    """Initialize database tables and create default admin user."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # An organization owns the commercial subscription; users belong to it.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            license_key TEXT,
            license_order_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'doctor',
            organization_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ,FOREIGN KEY (organization_id) REFERENCES organizations(id)
        )
    ''')

    organization_columns = {row['name'] for row in cursor.execute('PRAGMA table_info(organizations)').fetchall()}
    organization_migrations = {
        'license_key': 'TEXT',
        'license_order_id': 'INTEGER',
    }
    for column, definition in organization_migrations.items():
        if column not in organization_columns:
            cursor.execute(f'ALTER TABLE organizations ADD COLUMN {column} {definition}')

    user_columns = {row['name'] for row in cursor.execute('PRAGMA table_info(users)').fetchall()}
    if 'organization_id' not in user_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN organization_id INTEGER')
    if 'email' not in user_columns:
        cursor.execute('ALTER TABLE users ADD COLUMN email TEXT')
    cursor.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) WHERE email IS NOT NULL'
    )
    cursor.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_license_key ON organizations(license_key) WHERE license_key IS NOT NULL'
    )

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            plan_code TEXT NOT NULL,
            billing_cycle TEXT NOT NULL,
            status TEXT NOT NULL,
            starts_on DATE NOT NULL,
            renews_on DATE NOT NULL,
            licensed_beds INTEGER NOT NULL,
            included_users INTEGER NOT NULL,
            monthly_price_vnd INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscription_change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            requested_plan TEXT NOT NULL,
            message TEXT,
            requested_by INTEGER,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (requested_by) REFERENCES users(id)
        )
    ''')

    # Seed a single tenant subscription to make the commercial demo usable.
    organization = cursor.execute(
        'SELECT id FROM organizations WHERE organization_code = ?', ('DEMO-ICU',)
    ).fetchone()
    if not organization:
        cursor.execute(
            'INSERT INTO organizations (organization_code, name) VALUES (?, ?)',
            ('DEMO-ICU', 'ICU Predict Demo Center'),
        )
        organization_id = cursor.lastrowid
    else:
        organization_id = organization['id']

    subscription = cursor.execute(
        "SELECT id FROM subscriptions WHERE organization_id = ? AND status = 'active'",
        (organization_id,),
    ).fetchone()
    if not subscription:
        cursor.execute(
            '''INSERT INTO subscriptions
               (organization_id, plan_code, billing_cycle, status, starts_on, renews_on,
                licensed_beds, included_users, monthly_price_vnd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (organization_id, 'pilot', 'quarterly', 'active', '2026-08-01', '2026-11-01', 15, 15, 15000000),
        )

    # Tên gói cũ được ánh xạ về catalog dùng chung với license_admin.
    cursor.execute(
        "UPDATE subscriptions SET plan_code = 'pilot' WHERE plan_code = 'research_pilot'"
    )
    cursor.execute(
        "UPDATE subscriptions SET plan_code = 'core' WHERE plan_code = 'icu_core'"
    )
    cursor.execute(
        "UPDATE subscriptions SET plan_code = 'pro' WHERE plan_code = 'icu_pro'"
    )
    cursor.execute(
        "UPDATE subscriptions SET monthly_price_vnd = 15000000 WHERE plan_code = 'pilot' AND monthly_price_vnd = 45000000"
    )
    cursor.execute(
        "UPDATE subscriptions SET monthly_price_vnd = 9000000 WHERE plan_code = 'core' AND monthly_price_vnd = 108000000"
    )
    cursor.execute(
        "UPDATE subscriptions SET monthly_price_vnd = 18000000 WHERE plan_code = 'pro' AND monthly_price_vnd = 216000000"
    )

    # Create patients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            ward TEXT,
            admission_date DATE,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_by INTEGER,
            organization_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (organization_id) REFERENCES organizations(id)
        )
    ''')

    # Create predictions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            organization_id INTEGER,
            sofa REAL NOT NULL,
            map_value REAL NOT NULL,
            pao2_fio2 REAL NOT NULL,
            bilirubin REAL NOT NULL,
            creatinine REAL NOT NULL,
            platelet REAL NOT NULL,
            gcs REAL NOT NULL,
            risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            measurement_time TIMESTAMP,
            data_quality_confirmed INTEGER DEFAULT 0,
            predicted_by INTEGER,
            notes TEXT,
            model_version TEXT,
            model_status TEXT,
            out_of_distribution INTEGER DEFAULT 0,
            acknowledged_at TIMESTAMP,
            acknowledged_by INTEGER,
            acknowledgement_note TEXT,
            review_outcome TEXT,
            utility_score INTEGER,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (predicted_by) REFERENCES users(id),
            FOREIGN KEY (acknowledged_by) REFERENCES users(id)
        )
    ''')

    # Lightweight migrations for databases created by previous demo versions.
    patient_columns = {
        row['name'] for row in cursor.execute('PRAGMA table_info(patients)').fetchall()
    }
    if 'organization_id' not in patient_columns:
        cursor.execute('ALTER TABLE patients ADD COLUMN organization_id INTEGER')

    prediction_columns = {
        row['name'] for row in cursor.execute('PRAGMA table_info(predictions)').fetchall()
    }
    migration_columns = {
        'model_version': 'TEXT',
        'model_status': 'TEXT',
        'out_of_distribution': 'INTEGER DEFAULT 0',
        'acknowledged_at': 'TIMESTAMP',
        'acknowledged_by': 'INTEGER',
        'acknowledgement_note': 'TEXT',
        'review_outcome': 'TEXT',
        'utility_score': 'INTEGER',
        'organization_id': 'INTEGER',
        'measurement_time': 'TIMESTAMP',
        'data_quality_confirmed': 'INTEGER DEFAULT 0',
    }
    for column, definition in migration_columns.items():
        if column not in prediction_columns:
            cursor.execute(f'ALTER TABLE predictions ADD COLUMN {column} {definition}')

    # Historical demo records pre-date tenant ownership. Keep them available
    # to the demo organization only; newly registered organizations start empty.
    cursor.execute(
        'UPDATE patients SET organization_id = ? WHERE organization_id IS NULL',
        (organization_id,),
    )
    cursor.execute(
        '''UPDATE predictions
           SET organization_id = COALESCE(
               (SELECT organization_id FROM patients WHERE patients.id = predictions.patient_id),
               ?
           )
           WHERE organization_id IS NULL''',
        (organization_id,),
    )

    # Create default admin user if not exists
    existing = cursor.execute(
        'SELECT id FROM users WHERE username = ?', (admin_username,)
    ).fetchone()

    if not existing:
        cursor.execute(
            'INSERT INTO users (username, password_hash, full_name, role, organization_id) VALUES (?, ?, ?, ?, ?)',
            (admin_username, generate_password_hash(admin_password), 'Administrator', 'admin', organization_id)
        )
    else:
        cursor.execute(
            'UPDATE users SET organization_id = ? WHERE id = ? AND organization_id IS NULL',
            (organization_id, existing['id']),
        )
        if reset_admin_password:
            cursor.execute(
                'UPDATE users SET password_hash = ? WHERE id = ?',
                (generate_password_hash(admin_password), existing['id']),
            )

    # Seed sample patients if empty
    patient_count = cursor.execute('SELECT COUNT(*) FROM patients').fetchone()[0]
    if patient_count == 0:
        sample_patients = [
            ('BN001', 'Nguyễn Minh Anh', 65, 'Nam', 'ICU-1', '2024-01-15', 'active'),
            ('BN002', 'Trần Thu Hà', 72, 'Nữ', 'ICU-1', '2024-01-16', 'active'),
            ('BN003', 'Lê Quốc Bảo', 58, 'Nam', 'ICU-2', '2024-01-17', 'active'),
            ('BN004', 'Phạm Ngọc Mai', 80, 'Nữ', 'ICU-2', '2024-01-18', 'active'),
            ('BN005', 'Hoàng Gia Huy', 45, 'Nam', 'ICU-1', '2024-01-19', 'active'),
            ('BN006', 'Võ Khánh Linh', 69, 'Nữ', 'ICU-3', '2024-01-20', 'active'),
            ('BN007', 'Đặng Đức Thành', 55, 'Nam', 'ICU-1', '2024-01-21', 'active'),
            ('BN008', 'Bùi Thanh Vy', 77, 'Nữ', 'ICU-2', '2024-01-22', 'active'),
        ]
        for p in sample_patients:
            cursor.execute(
                'INSERT INTO patients (patient_code, name, age, gender, ward, admission_date, status, organization_id, created_by) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)',
                (*p, organization_id)
            )

        # Seed sample predictions
        sample_predictions = [
            (1, 6, 70, 180, 1.2, 1.1, 200, 14, 18.5, 'Thấp'),
            (2, 10, 55, 90, 3.8, 3.2, 80, 9, 82.3, 'Cao'),
            (3, 4, 80, 200, 0.9, 1.0, 250, 15, 12.1, 'Thấp'),
            (4, 17, 50, 75, 4.2, 3.9, 65, 8, 95.7, 'Cao'),
            (5, 8, 65, 140, 2.1, 1.9, 150, 12, 35.2, 'Trung binh'),
            (6, 12, 45, 60, 5.0, 4.5, 50, 7, 91.4, 'Cao'),
            (7, 5, 75, 210, 1.0, 0.9, 230, 15, 8.3, 'Thấp'),
            (8, 9, 58, 100, 3.0, 2.8, 100, 10, 72.6, 'Cao'),
        ]
        for pr in sample_predictions:
            cursor.execute(
                'INSERT INTO predictions (patient_id, organization_id, sofa, map_value, pao2_fio2, bilirubin, creatinine, platelet, gcs, risk_score, risk_level, predicted_by) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)',
                (pr[0], organization_id, *pr[1:])
            )

    # Upgrade only the known placeholder demo names on existing databases.
    # User-entered records are preserved, even if they reuse a demo patient code.
    demo_name_upgrades = {
        'BN001': ('Nguyen Van A', 'Nguyễn Minh Anh'),
        'BN002': ('Tran Thi B', 'Trần Thu Hà'),
        'BN003': ('Le Van C', 'Lê Quốc Bảo'),
        'BN004': ('Pham Thi D', 'Phạm Ngọc Mai'),
        'BN005': ('Hoang Van E', 'Hoàng Gia Huy'),
        'BN006': ('Vo Thi F', 'Võ Khánh Linh'),
        'BN007': ('Dang Van G', 'Đặng Đức Thành'),
        'BN008': ('Bui Thi H', 'Bùi Thanh Vy'),
    }
    for patient_code, (legacy_name, demo_name) in demo_name_upgrades.items():
        cursor.execute(
            'UPDATE patients SET name = ? WHERE patient_code = ? AND name = ?',
            (demo_name, patient_code, legacy_name),
        )
    cursor.execute(
        "UPDATE patients SET gender = 'Nữ' WHERE patient_code IN ('BN002', 'BN004', 'BN006', 'BN008') AND gender = 'Nu'"
    )
    cursor.execute("UPDATE predictions SET risk_level = 'Thấp' WHERE risk_level = 'Thap'")
    cursor.execute("UPDATE predictions SET risk_level = 'Trung bình' WHERE risk_level = 'Trung binh'")

    conn.commit()
    conn.close()


def create_organization_account(db_path, *, organization_name, full_name, username, email, password_hash):
    """Create one customer organization and its initial organization admin.

    The caller must validate presentation-level rules (password policy, e-mail
    format, etc.) before calling this function.  Integrity errors are exposed
    as ``ValueError`` with a safe, user-facing message.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        if cursor.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
            raise ValueError('Tên đăng nhập này đã được sử dụng.')
        if cursor.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone():
            raise ValueError('Email này đã được sử dụng.')

        organization_code = f'ORG-{secrets.token_hex(4).upper()}'
        for _ in range(5):
            if not cursor.execute(
                'SELECT 1 FROM organizations WHERE organization_code = ?', (organization_code,)
            ).fetchone():
                break
            organization_code = f'ORG-{secrets.token_hex(4).upper()}'
        else:
            raise RuntimeError('Không thể tạo mã tổ chức. Vui lòng thử lại.')

        cursor.execute(
            'INSERT INTO organizations (organization_code, name) VALUES (?, ?)',
            (organization_code, organization_name),
        )
        organization_id = cursor.lastrowid
        cursor.execute(
            '''INSERT INTO users (username, password_hash, full_name, email, role, organization_id)
               VALUES (?, ?, ?, ?, 'organization_admin', ?)''',
            (username, password_hash, full_name, email, organization_id),
        )
        user_id = cursor.lastrowid
        conn.commit()
        return {
            'user_id': user_id,
            'organization_id': organization_id,
            'organization_code': organization_code,
        }
    except DATABASE_INTEGRITY_ERRORS as exc:
        conn.rollback()
        raise ValueError('Không thể tạo tài khoản với thông tin này.') from exc
    finally:
        conn.close()
