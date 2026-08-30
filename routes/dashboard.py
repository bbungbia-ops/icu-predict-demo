from datetime import datetime
from statistics import median

from flask import Blueprint, render_template, current_app, session
from routes.auth import login_required
from models.database import get_db_connection
from models.signal_presentation import describe_signal, explain_priority_reasons
from models.trial_access import get_trial_status

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)
    organization_id = session.get('organization_id')

    # Stats
    total_patients = conn.execute(
        "SELECT COUNT(*) FROM patients WHERE status = 'active' AND organization_id = ?",
        (organization_id,),
    ).fetchone()[0]
    review_items = conn.execute('''
        SELECT pr.id, p.name, p.patient_code, p.ward, pr.risk_level, pr.predicted_at,
               pr.out_of_distribution, pr.model_version, pr.sofa, pr.map_value,
               pr.pao2_fio2, pr.bilirubin, pr.creatinine, pr.platelet, pr.gcs
        FROM predictions pr
        JOIN patients p ON pr.patient_id = p.id
        WHERE pr.organization_id = ?
          AND pr.id IN (
            SELECT MAX(id) FROM predictions
            WHERE patient_id IS NOT NULL AND organization_id = ?
            GROUP BY patient_id
        )
          AND pr.risk_level IN ('Cao', 'Trung bình', 'Trung binh')
          AND pr.acknowledged_at IS NULL
        ORDER BY CASE pr.risk_level WHEN 'Cao' THEN 0 ELSE 1 END, pr.predicted_at DESC
        LIMIT 10
    ''', (organization_id, organization_id)).fetchall()
    predictor = current_app.config['PREDICTOR']
    review_queue = []
    for item in review_items:
        item_data = dict(item)
        analysis = predictor.predict(
            item_data['sofa'], item_data['map_value'], item_data['pao2_fio2'],
            item_data['bilirubin'], item_data['creatinine'], item_data['platelet'], item_data['gcs'],
        )
        item_data['signal'] = describe_signal(item_data['risk_level'])
        item_data['priority_reasons'] = explain_priority_reasons(
            analysis['feature_analysis'], item_data['signal'], item_data['out_of_distribution']
        )
        review_queue.append(item_data)
    pending_review = len(review_queue)
    acknowledged_today = conn.execute(
        "SELECT COUNT(*) FROM predictions WHERE organization_id = ? AND DATE(acknowledged_at) = CURRENT_DATE",
        (organization_id,),
    ).fetchone()[0]
    latest_model = current_app.config['PREDICTOR'].metadata['model_version']
    trial_status = get_trial_status(
        conn,
        organization_id,
        role=session.get('role'),
        license_valid=session.get('license_valid', False),
        patient_limit=current_app.config['TRIAL_PATIENT_LIMIT'],
        assessment_limit=current_app.config['TRIAL_ASSESSMENT_LIMIT'],
    )

    conn.close()

    return render_template('dashboard.html',
        total_patients=total_patients,
        pending_review=pending_review,
        acknowledged_today=acknowledged_today,
        review_queue=review_queue,
        latest_model=latest_model,
        trial_status=trial_status,
    )


@dashboard_bp.route('/about')
@login_required
def about():
    return render_template('about.html')


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


@dashboard_bp.route('/pilot')
@login_required
def pilot():
    """Show only observable Pilot measures; unavailable evidence stays explicit."""
    conn = get_db_connection(current_app.config['DATABASE_PATH'])
    organization_id = session.get('organization_id')
    totals = conn.execute('''
        SELECT
            COUNT(*) AS total_records,
            SUM(CASE WHEN acknowledged_at IS NOT NULL THEN 1 ELSE 0 END) AS reviewed_records,
            SUM(CASE WHEN review_outcome = 'not_appropriate' THEN 1 ELSE 0 END) AS not_appropriate_records,
            SUM(CASE WHEN utility_score IS NOT NULL THEN 1 ELSE 0 END) AS scored_records
        FROM predictions
        WHERE organization_id = ?
    ''', (organization_id,)).fetchone()
    review_times = conn.execute(
        'SELECT predicted_at, acknowledged_at FROM predictions WHERE organization_id = ? AND acknowledged_at IS NOT NULL',
        (organization_id,),
    ).fetchall()
    utility_scores = conn.execute(
        'SELECT utility_score FROM predictions WHERE organization_id = ? AND utility_score BETWEEN 1 AND 5',
        (organization_id,),
    ).fetchall()
    conn.close()

    elapsed_minutes = []
    for item in review_times:
        created_at = _as_datetime(item['predicted_at'])
        reviewed_at = _as_datetime(item['acknowledged_at'])
        if created_at and reviewed_at and reviewed_at >= created_at:
            elapsed_minutes.append((reviewed_at - created_at).total_seconds() / 60)

    total_records = int(totals['total_records'] or 0)
    reviewed_records = int(totals['reviewed_records'] or 0)
    return render_template(
        'pilot.html',
        total_records=total_records,
        reviewed_records=reviewed_records,
        completion_rate=round(reviewed_records / total_records * 100) if total_records else None,
        median_review_minutes=round(median(elapsed_minutes)) if elapsed_minutes else None,
        not_appropriate_records=int(totals['not_appropriate_records'] or 0),
        scored_records=int(totals['scored_records'] or 0),
        average_utility=round(sum(item['utility_score'] for item in utility_scores) / len(utility_scores), 1)
        if utility_scores else None,
    )
