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


def test_get_realtime_data(client, mock_db):
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    response = client.get("/api/electric/realtime")
    assert response.status_code == 200
    assert response.json() == []
