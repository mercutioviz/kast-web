import pytest
from app import create_app, db as _db


@pytest.fixture(scope='session')
def app():
    application = create_app('testing')
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Isolated in-memory DB for each test. Tables created fresh, torn down after."""
    with app.app_context():
        _db.create_all()
        yield _db.session
        _db.session.remove()
        _db.drop_all()
