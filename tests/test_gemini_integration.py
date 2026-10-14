"""
tests/test_gemini_integration.py - Test per client Gemini, selezione modello e dashboard.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from integration.gemini_client import DEFAULT_FALLBACK_MODELS, GeminiClient


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_dashboard_endpoint(client):
    """Verifica che la dashboard HTML venga servita correttamente su /."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Tradest" in res.text
    assert "Google Gemini" in res.text


def test_gemini_client_defaults():
    """Verifica inizializzazione e normalizzazione del modello nel GeminiClient."""
    gc = GeminiClient(api_key="test_key", model="models/gemini-1.5-pro")
    assert gc.model == "gemini-1.5-pro"
    assert gc.api_key == "test_key"

    gc.set_model("models/gemini-1.5-flash")
    assert gc.model == "gemini-1.5-flash"


def test_gemini_config_endpoint(client):
    """Verifica lettura e salvataggio configurazione Gemini."""
    # Salvataggio
    payload = {
        "api_key": "AIzaSyFakeKeyTest123456",
        "model": "gemini-1.5-flash",
        "temperature": 0.25,
    }
    r_save = client.post("/api/gemini/config", json=payload)
    assert r_save.status_code == 200
    data = r_save.json()
    assert data["status"] == "updated"
    assert data["model"] == "gemini-1.5-flash"
    assert data["has_api_key"] is True

    # Lettura
    r_get = client.get("/api/gemini/config")
    assert r_get.status_code == 200
    cfg = r_get.json()
    assert cfg["has_api_key"] is True
    assert cfg["model"] == "gemini-1.5-flash"


def test_gemini_models_endpoint(client):
    """Verifica che l'endpoint modelli restituisca una lista valida."""
    res = client.get("/api/gemini/models")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert len(data["models"]) > 0


def test_gemini_test_connection_without_key():
    """Verifica gestione corretta di assenza chiave."""
    gc = GeminiClient(api_key="", model="gemini-1.5-pro")
    import asyncio
    res = asyncio.run(gc.test_connection())
    assert res["success"] is False
    assert "mancante" in res["error"].lower()
