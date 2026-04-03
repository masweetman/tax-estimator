"""Pytest configuration and shared fixtures."""
import pytest
from werkzeug.security import generate_password_hash

from app import create_app, db as _db
from app.models import User


@pytest.fixture(scope="session")
def app():
    """Application configured for testing (in-memory SQLite, CSRF off)."""
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
    yield application
    with application.app_context():
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """Provide a clean database for each test via transaction rollback."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        yield _db
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def auth_client(app, client):
    """A test client that is already logged in."""
    with app.app_context():
        # Ensure the test user exists
        user = User.query.filter_by(username="testuser").first()
        if not user:
            user = User(
                username="testuser",
                password_hash=generate_password_hash("testpass"),
            )
            _db.session.add(user)
            _db.session.commit()

    with client.session_transaction() as sess:
        # Directly set Flask-Login session variables
        sess["_user_id"] = "1"
        sess["_fresh"] = True

    return client
