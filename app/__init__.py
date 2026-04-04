import os

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
    from app.routes.profile import profile_bp
    from app.routes.tax_years import tax_years_bp
    from app.routes.settings import settings_bp
    from app.routes.llc import llc_bp
    from app.routes.federal_summary import federal_summary_bp
    from app.routes.ca_summary import ca_summary_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(w2_bp)
    app.register_blueprint(se_bp)
    app.register_blueprint(deductions_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(vehicles_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(tax_years_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(llc_bp)
    app.register_blueprint(federal_summary_bp)
    app.register_blueprint(ca_summary_bp)

    @app.context_processor
    def inject_person_names():
        from flask_login import current_user
        if current_user.is_authenticated:
            p1 = current_user.person1_name or "Person 1"
            p2 = current_user.person2_name or "Person 2"
        else:
            p1, p2 = "Person 1", "Person 2"

        def person_display(val):
            if val == "Person 1":
                return p1
            if val == "Person 2":
                return p2
            return val

        return dict(person1_name=p1, person2_name=p2, person_display=person_display)

    @app.context_processor
    def inject_tax_years():
        from flask_login import current_user
        from flask import request as _req
        if current_user.is_authenticated:
            from app.models import TaxYear
            all_years = TaxYear.query.order_by(TaxYear.year.desc()).all()
            active_year = _req.args.get("year", type=int)
            if active_year is None and all_years:
                active_year = all_years[0].year
        else:
            all_years = []
            active_year = None
        return dict(nav_all_years=all_years, nav_active_year=active_year)

    # Auto-initialise the database and seed the default user on first boot.
    with app.app_context():
        os.makedirs(app.instance_path, exist_ok=True)
        db.create_all()
        if not app.testing:
            from app.models import User
            from werkzeug.security import generate_password_hash
            from sqlalchemy.exc import IntegrityError
            if not User.query.filter_by(username="mike").first():
                try:
                    default_user = User(
                        username="mike",
                        password_hash=generate_password_hash("change-me-now"),
                    )
                    db.session.add(default_user)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()

    return app
