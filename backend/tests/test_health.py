"""Health endpoint tests."""

from fastapi.testclient import TestClient


def test_health_endpoints_return_200(client: TestClient) -> None:
    endpoints = {
        "/health/live": "live",
        "/health/ready": "ready",
    }

    for path, expected_status in endpoints.items():
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": expected_status}
