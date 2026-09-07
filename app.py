from flask import Flask
import os
from config import Config
from models.database import init_db
from models.ml_model import ICUPredictor


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['DATABASE_PATH'] = Config.DATABASE_PATH

    # Initialize database
    init_db(
        Config.DATABASE_PATH,
        Config.ADMIN_USERNAME,
        Config.ADMIN_PASSWORD,
        reset_admin_password=Config.RESET_DEFAULT_ADMIN_PASSWORD,
    )

    # Load AI model once
    predictor = ICUPredictor(Config.MODEL_PATH)
    app.config['PREDICTOR'] = predictor

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.patients import patients_bp
    from routes.predictions import predictions_bp
    from routes.reports import reports_bp
    from routes.account import account_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(predictions_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(account_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    print("=" * 50)
    print("  ICU PREDICT - Ứng dụng demo nghiên cứu")
    print("  http://localhost:5000")
    if Config.DEMO_MODE:
        print(f"  Tài khoản demo: {Config.ADMIN_USERNAME} / {Config.ADMIN_PASSWORD}")
    else:
        print("  Đang chạy với cấu hình triển khai.")
    print("=" * 50)
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=int(os.environ.get('PORT', '5000')))
