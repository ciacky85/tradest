"""
tests/test_api_endpoints.py - Test per gli endpoint FastAPI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Client di test per FastAPI con lifespan context."""
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    """Verifica l'endpoint /health."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data


def test_status_endpoint(client):
    """Verifica l'endpoint /status."""
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "health" in data
    assert data["health"]["status"] == "ok"


def test_config_endpoints(client):
    """Verifica gli endpoint di configurazione."""
    r_params = client.get("/config/trading-params")
    assert r_params.status_code == 200
    assert "assets" in r_params.json()

    r_symbols = client.get("/config/symbols")
    assert r_symbols.status_code == 200
    assert "symbols" in r_symbols.json()

    r_prompts = client.get("/config/prompts")
    assert r_prompts.status_code == 200
    assert "prompts" in r_prompts.json()


def test_bot_control_endpoints(client):
    """Verifica gli endpoint di controllo bot."""
    # Start bot
    r_start = client.post("/bot/start")
    assert r_start.status_code == 200
    assert r_start.json()["trading_enabled"] == "true"

    # Stop bot
    r_stop = client.post("/bot/stop")
    assert r_stop.status_code == 200
    assert r_stop.json()["trading_enabled"] == "false"

    # Emergency stop
    r_emg = client.post("/bot/emergency-stop")
    assert r_emg.status_code == 200
    assert r_emg.json()["status"] == "emergency_stopped"
