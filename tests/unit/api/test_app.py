from fastapi.testclient import TestClient

from meridian.main import app


def test_app_exposes_telemetry_route():
    routes = set()
    for route in app.routes:
        if hasattr(route, 'path'):
            routes.add(route.path)
        elif hasattr(route, 'effective_candidates'):
            for candidate in route.effective_candidates():
                if hasattr(candidate, 'path'):
                    routes.add(candidate.path)
    assert "/api/v1/telemetry/event" in routes


def test_app_exposes_write_keys_routes():
    routes = set()
    for route in app.routes:
        if hasattr(route, 'path'):
            routes.add(route.path)
        elif hasattr(route, 'effective_candidates'):
            for candidate in route.effective_candidates():
                if hasattr(candidate, 'path'):
                    routes.add(candidate.path)
    assert "/api/v1/write-keys" in routes


def test_docs_endpoint_available():
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
