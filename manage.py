#!/usr/bin/env python3
"""Management CLI for Tax Estimator."""
import os
import sys
import getpass

# Ensure the app directory is on the path
sys.path.insert(0, os.path.dirname(__file__))


def get_app():
    from app import create_app
    return create_app(os.environ.get("FLASK_ENV", "development"))


def cmd_init_db():
    """Create all database tables."""
    app = get_app()
    with app.app_context():
        from app import db
        db.create_all()
        print("Database tables created.")


def cmd_create_user():
    """Create or update the single app user."""
    from werkzeug.security import generate_password_hash
    username = input("Username [admin]: ").strip() or "admin"
    while True:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password == confirm:
            break
        print("Passwords do not match. Try again.")

    app = get_app()
    with app.app_context():
        from app import db
        from app.models import User
        user = User.query.filter_by(username=username).first()
        if user:
            user.password_hash = generate_password_hash(password)
            print(f"Password updated for user '{username}'.")
        else:
            user = User(username=username, password_hash=generate_password_hash(password))
            db.session.add(user)
            print(f"User '{username}' created.")
        db.session.commit()


COMMANDS = {
    "init-db": cmd_init_db,
    "create-user": cmd_create_user,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python manage.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
