from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # Import models so SQLAlchemy registers them before create_all()
    from app import models  # noqa: F401

    from app.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.w2 import w2_bp
    from app.routes.se import se_bp
    from app.routes.deductions import deductions_bp
    from app.routes.payments import payments_bp
    from app.routes.vehicles import vehicles_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(w2_bp)
    app.register_blueprint(se_bp)
    app.register_blueprint(deductions_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(vehicles_bp)

    return app
