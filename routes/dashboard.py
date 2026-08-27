from flask import Blueprint, render_template, current_app
from routes.auth import login_required
from models.database import get_db_connection
from models.signal_presentation import describe_signal

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    db_path = current_app.config['DATABASE_PATH']
    conn = get_db_connection(db_path)

    # Stats
    total_patients = conn.execute("SELECT COUNT(*) FROM patients WHERE status = 'active'").fetchone()[0]
    review_queue = conn.execute('''
        SELECT pr.id, p.name, p.patient_code, p.ward, pr.risk_level, pr.predicted_at,
               pr.out_of_distribution, pr.model_version
        FROM predictions pr
        JOIN patients p ON pr.patient_id = p.id
        WHERE pr.id IN (
            SELECT MAX(id) FROM predictions WHERE patient_id IS NOT NULL GROUP BY patient_id
        )
          AND pr.risk_level IN ('Cao', 'Trung bình', 'Trung binh')
          AND pr.acknowledged_at IS NULL
        ORDER BY CASE pr.risk_level WHEN 'Cao' THEN 0 ELSE 1 END, pr.predicted_at DESC
        LIMIT 10
    ''').fetchall()
    review_queue = [
        {**dict(item), 'signal': describe_signal(item['risk_level'])}
        for item in review_queue
    ]
    pending_review = len(review_queue)
    acknowledged_today = conn.execute(
        "SELECT COUNT(*) FROM predictions WHERE DATE(acknowledged_at) = CURRENT_DATE"
    ).fetchone()[0]
    latest_model = current_app.config['PREDICTOR'].metadata['model_version']

    conn.close()

    return render_template('dashboard.html',
        total_patients=total_patients,
        pending_review=pending_review,
        acknowledged_today=acknowledged_today,
        review_queue=review_queue,
        latest_model=latest_model,
    )


@dashboard_bp.route('/about')
@login_required
def about():
    return render_template('about.html')
