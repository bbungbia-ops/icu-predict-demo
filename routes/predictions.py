from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from routes.auth import login_required
from models.database import get_db_connection
from models.ml_model import InputValidationError
from models.signal_presentation import (
    REVIEW_OUTCOME_LABELS,
    describe_review_outcome,
    describe_signal,
    explain_priority_reasons,
)
from models.trial_access import get_trial_status
from models.trend_analysis import build_trend_summary
from models.model_governance import evidence_status
from datetime import datetime, timedelta
import json

predictions_bp = Blueprint('predictions', __name__)


def current_trial_status(connection):
    return get_trial_status(
        connection,
        session.get('organization_id'),
        role=session.get('role'),
        license_valid=session.get('license_valid', False),
        patient_limit=current_app.config['TRIAL_PATIENT_LIMIT'],
        assessment_limit=current_app.config['TRIAL_ASSESSMENT_LIMIT'],
    )


@predictions_bp.route('/predict', methods=['GET'])
@login_required
def predict_form():
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    patients = conn.execute(
        "SELECT id, patient_code, name FROM patients WHERE status = 'active' AND organization_id = ? ORDER BY name",
        (session.get('organization_id'),),
    ).fetchall()
    trial_status = current_trial_status(conn)
    conn.close()
    if not trial_status['can_create_assessment']:
        flash(
            f"Bạn đã hoàn tất {trial_status['assessment_limit']} lượt đánh giá dùng thử. "
            'Hãy chọn gói để tiếp tục sử dụng.',
            'error',
        )
        return redirect(url_for('account.subscription'))
    return render_template(
        'predict.html',
        patients=patients,
        trial_status=trial_status,
        default_measurement_time=datetime.now().strftime('%Y-%m-%dT%H:%M'),
    )


@predictions_bp.route('/predict', methods=['POST'])
@login_required
def predict():
    predictor = current_app.config['PREDICTOR']

    patient_id = request.form.get('patient_id', type=int)
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    trial_status = current_trial_status(conn)
    if not trial_status['can_create_assessment']:
        conn.close()
        flash(
            f"Bạn đã hoàn tất {trial_status['assessment_limit']} lượt đánh giá dùng thử. "
            'Hãy chọn gói để tiếp tục sử dụng.',
            'error',
        )
        return redirect(url_for('account.subscription'))
    if trial_status['is_trial'] and not patient_id:
        conn.close()
        flash('Bản dùng thử yêu cầu chọn một ca bệnh do tổ chức bạn tự nhập.', 'error')
        return redirect(url_for('predictions.predict_form'))
    if patient_id:
        patient = conn.execute(
            'SELECT id FROM patients WHERE id = ? AND organization_id = ?',
            (patient_id, session.get('organization_id')),
        ).fetchone()
        if not patient:
            conn.close()
            flash('Không tìm thấy bệnh nhân trong tổ chức của bạn.', 'error')
            return redirect(url_for('predictions.predict_form'))
    conn.close()

    raw_values = {
        'sofa': request.form.get('sofa'),
        'map_value': request.form.get('map_value'),
        'pao2_fio2': request.form.get('pao2_fio2'),
        'bilirubin': request.form.get('bilirubin'),
        'creatinine': request.form.get('creatinine'),
        'platelet': request.form.get('platelet'),
        'gcs': request.form.get('gcs'),
    }
    measurement_time_text = request.form.get('measurement_time', '').strip()
    try:
        if request.form.get('unit_confirmed') != 'yes':
            raise InputValidationError(
                'Cần xác nhận đã kiểm tra đơn vị đo và thời điểm lấy mẫu trước khi tạo bản ghi.'
            )
        measurement_time = datetime.fromisoformat(measurement_time_text)
        if measurement_time > datetime.now() + timedelta(minutes=5):
            raise ValueError('Thời điểm lấy mẫu không thể nằm trong tương lai.')
        result = predictor.predict(**raw_values)
        sofa = float(raw_values['sofa'])
        map_value = float(raw_values['map_value'])
        pao2_fio2 = float(raw_values['pao2_fio2'])
        bilirubin = float(raw_values['bilirubin'])
        creatinine = float(raw_values['creatinine'])
        platelet = float(raw_values['platelet'])
        gcs = float(raw_values['gcs'])
    except (InputValidationError, ValueError, TypeError) as exc:
        flash(str(exc) or 'Vui lòng nhập đúng định dạng số.', 'error')
        return redirect(url_for('predictions.predict_form'))

    # Save to database
    notes = request.form.get('notes', '').strip()

    conn = get_db_connection(db_path)

    cursor = conn.execute(
        'INSERT INTO predictions (patient_id, organization_id, sofa, map_value, pao2_fio2, bilirubin, creatinine, platelet, gcs, '
        'risk_score, risk_level, measurement_time, data_quality_confirmed, predicted_by, notes, model_version, model_status, out_of_distribution) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (patient_id, session.get('organization_id'), sofa, map_value, pao2_fio2, bilirubin, creatinine, platelet, gcs,
         result['risk_score'], result['risk_level'], measurement_time.isoformat(timespec='minutes'), 1, session.get('user_id'), notes,
         result['model_version'], result['model_status'], int(bool(result['out_of_distribution'])))
    )
    prediction_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return redirect(url_for('predictions.result', prediction_id=prediction_id))


@predictions_bp.route('/predict/result/<int:prediction_id>')
@login_required
def result(prediction_id):
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    prediction = conn.execute('''
        SELECT pr.*, p.name as patient_name, p.patient_code, p.age, p.gender, p.ward,
               u.full_name as doctor_name, reviewer.full_name as reviewer_name
        FROM predictions pr
        LEFT JOIN patients p ON pr.patient_id = p.id
        LEFT JOIN users u ON pr.predicted_by = u.id
        LEFT JOIN users reviewer ON pr.acknowledged_by = reviewer.id
        WHERE pr.id = ? AND pr.organization_id = ?
    ''', (prediction_id, session.get('organization_id'))).fetchone()

    if not prediction:
        conn.close()
        flash('Không tìm thấy bản ghi đánh giá.', 'error')
        return redirect(url_for('predictions.predict_form'))

    previous_records = conn.execute(
        '''SELECT id, measurement_time, sofa, map_value, pao2_fio2, bilirubin, creatinine, platelet, gcs
           FROM predictions
           WHERE patient_id = ? AND organization_id = ? AND id <> ?
           ORDER BY measurement_time DESC
           LIMIT 100''',
        (prediction['patient_id'], session.get('organization_id'), prediction_id),
    ).fetchall() if prediction['patient_id'] else []
    conn.close()

    # Re-run analysis for visualization
    predictor = current_app.config['PREDICTOR']
    analysis = predictor.predict(
        prediction['sofa'], prediction['map_value'], prediction['pao2_fio2'],
        prediction['bilirubin'], prediction['creatinine'],
        prediction['platelet'], prediction['gcs']
    )

    return render_template('result.html',
        prediction=prediction,
        analysis=analysis,
        priority_reasons=explain_priority_reasons(
            analysis['feature_analysis'], analysis['signal'], prediction['out_of_distribution']
        ),
        review_outcome_label=describe_review_outcome(prediction['review_outcome']),
        trend_summary=build_trend_summary(dict(prediction), [dict(record) for record in previous_records]),
        model_evidence=evidence_status(predictor.metadata),
        analysis_json=json.dumps(analysis)
    )


@predictions_bp.route('/predict/result/<int:prediction_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge(prediction_id):
    acknowledgement_note = request.form.get('acknowledgement_note', '').strip()
    review_outcome = request.form.get('review_outcome', '').strip() or None
    utility_score_text = request.form.get('utility_score', '').strip()
    if not acknowledgement_note:
        flash('Vui lòng ghi lại nhận định của bác sĩ trước khi xác nhận.', 'error')
        return redirect(url_for('predictions.result', prediction_id=prediction_id))
    if len(acknowledgement_note) > 2000:
        flash('Ghi chú đánh giá không được quá 2.000 ký tự.', 'error')
        return redirect(url_for('predictions.result', prediction_id=prediction_id))
    if review_outcome and review_outcome not in REVIEW_OUTCOME_LABELS:
        flash('Đánh giá Pilot không hợp lệ.', 'error')
        return redirect(url_for('predictions.result', prediction_id=prediction_id))
    try:
        utility_score = int(utility_score_text) if utility_score_text else None
    except ValueError:
        utility_score = None
    if utility_score is not None and utility_score not in range(1, 6):
        flash('Mức hữu ích Pilot cần nằm trong khoảng 1 đến 5.', 'error')
        return redirect(url_for('predictions.result', prediction_id=prediction_id))

    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    cursor = conn.execute(
        '''UPDATE predictions
           SET acknowledged_at = CURRENT_TIMESTAMP,
               acknowledged_by = ?,
               acknowledgement_note = ?,
               review_outcome = ?,
               utility_score = ?
           WHERE id = ? AND organization_id = ? AND acknowledged_at IS NULL''',
        (
            session.get('user_id'), acknowledgement_note, review_outcome, utility_score,
            prediction_id, session.get('organization_id'),
        ),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount:
        flash('Đã lưu xác nhận đánh giá vào nhật ký kiểm toán.', 'success')
    else:
        flash('Bản ghi đã được xác nhận trước đó hoặc không tồn tại.', 'error')
    return redirect(url_for('predictions.result', prediction_id=prediction_id))


@predictions_bp.route('/predictions/history')
@login_required
def history():
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    predictions = conn.execute('''
        SELECT pr.*, p.name as patient_name, p.patient_code,
               u.full_name as doctor_name
        FROM predictions pr
        LEFT JOIN patients p ON pr.patient_id = p.id
        LEFT JOIN users u ON pr.predicted_by = u.id
        WHERE pr.organization_id = ?
        ORDER BY pr.predicted_at DESC
        LIMIT 50
    ''', (session.get('organization_id'),)).fetchall()

    predictions = [
        {**dict(prediction), 'signal': describe_signal(prediction['risk_level'])}
        for prediction in predictions
    ]
    conn.close()

    return render_template('history.html', predictions=predictions)
