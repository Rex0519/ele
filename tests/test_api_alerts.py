from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.db import get_db
from src.main import app


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_alerts(client, mock_db):
    mock_db.query.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert response.json() == []


def test_list_active_alerts(client, mock_db):
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    response = client.get("/api/alerts/active")
    assert response.status_code == 200
    assert response.json() == []
