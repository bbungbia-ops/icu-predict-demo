from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session, jsonify
from routes.auth import login_required
from models.database import get_db_connection
from models.ml_model import InputValidationError
from models.signal_presentation import describe_signal
import json

predictions_bp = Blueprint('predictions', __name__)


@predictions_bp.route('/predict', methods=['GET'])
@login_required
def predict_form():
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    patients = conn.execute(
        "SELECT id, patient_code, name FROM patients WHERE status = 'active' ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template('predict.html', patients=patients)


@predictions_bp.route('/predict', methods=['POST'])
@login_required
def predict():
    predictor = current_app.config['PREDICTOR']

    raw_values = {
        'sofa': request.form.get('sofa'),
        'map_value': request.form.get('map_value'),
        'pao2_fio2': request.form.get('pao2_fio2'),
        'bilirubin': request.form.get('bilirubin'),
        'creatinine': request.form.get('creatinine'),
        'platelet': request.form.get('platelet'),
        'gcs': request.form.get('gcs'),
    }
    try:
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
    patient_id = request.form.get('patient_id', type=int)
    notes = request.form.get('notes', '').strip()

    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    cursor = conn.execute(
        'INSERT INTO predictions (patient_id, sofa, map_value, pao2_fio2, bilirubin, creatinine, platelet, gcs, '
        'risk_score, risk_level, predicted_by, notes, model_version, model_status, out_of_distribution) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (patient_id, sofa, map_value, pao2_fio2, bilirubin, creatinine, platelet, gcs,
         result['risk_score'], result['risk_level'], session.get('user_id'), notes,
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
        WHERE pr.id = ?
    ''', (prediction_id,)).fetchone()

    conn.close()

    if not prediction:
        flash('Không tìm thấy bản ghi đánh giá.', 'error')
        return redirect(url_for('predictions.predict_form'))

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
        analysis_json=json.dumps(analysis)
    )


@predictions_bp.route('/predict/result/<int:prediction_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge(prediction_id):
    acknowledgement_note = request.form.get('acknowledgement_note', '').strip()
    if not acknowledgement_note:
        flash('Vui lòng ghi lại nhận định của bác sĩ trước khi xác nhận.', 'error')
        return redirect(url_for('predictions.result', prediction_id=prediction_id))
    if len(acknowledgement_note) > 2000:
        flash('Ghi chú đánh giá không được quá 2.000 ký tự.', 'error')
        return redirect(url_for('predictions.result', prediction_id=prediction_id))

    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    cursor = conn.execute(
        '''UPDATE predictions
           SET acknowledged_at = CURRENT_TIMESTAMP,
               acknowledged_by = ?,
               acknowledgement_note = ?
           WHERE id = ? AND acknowledged_at IS NULL''',
        (session.get('user_id'), acknowledgement_note, prediction_id),
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
        ORDER BY pr.predicted_at DESC
        LIMIT 50
    ''').fetchall()

    predictions = [
        {**dict(prediction), 'signal': describe_signal(prediction['risk_level'])}
        for prediction in predictions
    ]
    conn.close()

    return render_template('history.html', predictions=predictions)
