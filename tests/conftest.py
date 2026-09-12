import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from services.api.app import db
from services.api.app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}', connect_args={'check_same_thread': False})
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(db, 'Session', sessionmaker(engine))
    monkeypatch.delenv('SLACK_WEBHOOK_URL', raising=False)
    with TestClient(app) as client:
        yield client
    engine.dispose()

