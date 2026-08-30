from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from routes.auth import login_required
from models.database import get_db_connection
from models.signal_presentation import describe_signal
from models.trial_access import get_trial_status

patients_bp = Blueprint('patients', __name__)


def current_trial_status(connection):
    return get_trial_status(
        connection,
        session.get('organization_id'),
        role=session.get('role'),
        license_valid=session.get('license_valid', False),
        patient_limit=current_app.config['TRIAL_PATIENT_LIMIT'],
        assessment_limit=current_app.config['TRIAL_ASSESSMENT_LIMIT'],
    )


@patients_bp.route('/patients')
@login_required
def list_patients():
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')

    query = 'SELECT * FROM patients WHERE organization_id = ?'
    params = [session.get('organization_id')]

    if search:
        query += ' AND (name LIKE ? OR patient_code LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    if status_filter != 'all':
        query += ' AND status = ?'
        params.append(status_filter)

    query += ' ORDER BY created_at DESC'

    patients = conn.execute(query, params).fetchall()
    trial_status = current_trial_status(conn)
    conn.close()

    return render_template(
        'patients.html',
        patients=patients,
        search=search,
        status_filter=status_filter,
        trial_status=trial_status,
    )


@patients_bp.route('/patients/add', methods=['POST'])
@login_required
def add_patient():
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    trial_status = current_trial_status(conn)

    if not trial_status['can_add_patient']:
        conn.close()
        flash(
            f"Bạn đã dùng hết {trial_status['patient_limit']} ca dùng thử. "
            'Hãy chọn gói để tiếp tục tạo bệnh nhân và sử dụng không giới hạn.',
            'error',
        )
        return redirect(url_for('account.subscription'))

    patient_code = request.form.get('patient_code', '').strip()
    name = request.form.get('name', '').strip()
    age = request.form.get('age', type=int)
    gender = request.form.get('gender', '')
    ward = request.form.get('ward', '').strip()
    admission_date = request.form.get('admission_date', '')
    notes = request.form.get('notes', '').strip()

    if not patient_code or not name:
        flash('Mã bệnh nhân và tên là bắt buộc.', 'error')
        conn.close()
        return redirect(url_for('patients.list_patients'))

    try:
        conn.execute(
            'INSERT INTO patients (patient_code, name, age, gender, ward, admission_date, notes, created_by, organization_id) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                patient_code, name, age, gender, ward, admission_date, notes,
                session.get('user_id'), session.get('organization_id'),
            )
        )
        conn.commit()
        flash('Đã thêm bệnh nhân thành công.', 'success')
    except Exception:
        flash('Không thể thêm bệnh nhân. Mã bệnh nhân có thể đã tồn tại.', 'error')
    finally:
        conn.close()

    return redirect(url_for('patients.list_patients'))


@patients_bp.route('/patients/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    patient = conn.execute(
        'SELECT * FROM patients WHERE id = ? AND organization_id = ?',
        (patient_id, session.get('organization_id')),
    ).fetchone()
    if not patient:
        flash('Không tìm thấy bệnh nhân.', 'error')
        conn.close()
        return redirect(url_for('patients.list_patients'))

    predictions = conn.execute('''
        SELECT pr.*, u.full_name as doctor_name
        FROM predictions pr
        LEFT JOIN users u ON pr.predicted_by = u.id
        WHERE pr.patient_id = ? AND pr.organization_id = ?
        ORDER BY pr.predicted_at DESC
    ''', (patient_id, session.get('organization_id'))).fetchall()

    predictions = [
        {**dict(prediction), 'signal': describe_signal(prediction['risk_level'])}
        for prediction in predictions
    ]
    trial_status = current_trial_status(conn)
    conn.close()

    return render_template(
        'patient_detail.html', patient=patient, predictions=predictions, trial_status=trial_status
    )


@patients_bp.route('/patients/<int:patient_id>/update', methods=['POST'])
@login_required
def update_patient(patient_id):
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    name = request.form.get('name', '').strip()
    age = request.form.get('age', type=int)
    gender = request.form.get('gender', '')
    ward = request.form.get('ward', '').strip()
    status = request.form.get('status', 'active')
    notes = request.form.get('notes', '').strip()

    cursor = conn.execute(
        'UPDATE patients SET name=?, age=?, gender=?, ward=?, status=?, notes=? WHERE id=? AND organization_id=?',
        (name, age, gender, ward, status, notes, patient_id, session.get('organization_id'))
    )
    conn.commit()
    conn.close()

    if not cursor.rowcount:
        flash('Không tìm thấy bệnh nhân trong tổ chức của bạn.', 'error')
        return redirect(url_for('patients.list_patients'))
    flash('Đã cập nhật thông tin bệnh nhân.', 'success')
    return redirect(url_for('patients.patient_detail', patient_id=patient_id))


@patients_bp.route('/patients/<int:patient_id>/delete', methods=['POST'])
@login_required
def delete_patient(patient_id):
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    organization_id = session.get('organization_id')
    conn.execute(
        'DELETE FROM predictions WHERE patient_id = ? AND organization_id = ?',
        (patient_id, organization_id),
    )
    cursor = conn.execute(
        'DELETE FROM patients WHERE id = ? AND organization_id = ?',
        (patient_id, organization_id),
    )
    conn.commit()
    conn.close()

    if not cursor.rowcount:
        flash('Không tìm thấy bệnh nhân trong tổ chức của bạn.', 'error')
        return redirect(url_for('patients.list_patients'))
    flash('Đã xóa bệnh nhân.', 'success')
    return redirect(url_for('patients.list_patients'))
