import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from meridian.api.middleware import RequestLoggingMiddleware


def _make_app():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def test_middleware_logs_route_status_and_latency(caplog):
    app = _make_app()
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="meridian.request"):
        response = client.get("/ping")
    assert response.status_code == 200
    assert len(caplog.records) == 1
    record = caplog.records[0]
    payload = json.loads(record.getMessage())
    assert payload["route"] == "/ping"
    assert payload["status_code"] == 200
    assert "latency_ms" in payload


def test_middleware_includes_tenant_id_when_set_on_request_state():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/tenant-scoped")
    def scoped(request: Request):
        request.state.tenant_id = "11111111-1111-1111-1111-111111111111"
        return {"ok": True}

    client = TestClient(app)
    import logging as _logging
    logger = _logging.getLogger("meridian.request")
    records = []

    class _Capture(_logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(_logging.INFO)
    try:
        client.get("/tenant-scoped")
    finally:
        logger.removeHandler(handler)

    assert len(records) == 1
    payload = json.loads(records[0].getMessage())
    assert payload["tenant_id"] == "11111111-1111-1111-1111-111111111111"
