"""
Unit tests for FastAPI endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_home_and_health_endpoints():
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()

    r2 = client.get("/health")
    assert r2.status_code == 200
    assert r2.json()["status"] in ["ok", "running"]


def test_list_projects_and_definitions():
    r1 = client.get("/projects")
    assert r1.status_code == 200
    assert isinstance(r1.json(), list)

    r2 = client.get("/metrics/definitions")
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)
