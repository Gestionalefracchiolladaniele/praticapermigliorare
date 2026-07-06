"""Test dell'endpoint /ask con Gemini mockato (step 2). Gira senza Docker/DB
e senza GEMINI_API_KEY: verifica solo la CATENA generazione -> guardrail ->
risposta, non la qualita' dell'SQL (quello e' l'evaluation harness, step 5).
"""
import os

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app as fastapi_app


@pytest.fixture
def client(monkeypatch):
    # Assicura che il ramo "esecuzione DB" resti spento (no DATABASE_URL).
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return TestClient(fastapi_app)


def test_ask_returns_validated_sql(client, monkeypatch):
    # Gemini "genera" un SELECT valido e con tenant.
    monkeypatch.setattr(
        main, "generate_sql",
        lambda q, t: "SELECT count(*) FROM customers WHERE tenant_id = 1",
    )
    r = client.post("/ask", json={"tenant_id": 1, "question": "quanti clienti?"})
    assert r.status_code == 200
    body = r.json()
    assert body["guardrail_approved"] is True
    assert body["executed"] is False  # no DB
    assert "tenant_id = 1" in body["generated_sql"]


def test_ask_blocks_dangerous_sql(client, monkeypatch):
    # Gemini "genera" (o injection produce) un DROP: il guardrail deve bloccare.
    monkeypatch.setattr(main, "generate_sql", lambda q, t: "DROP TABLE customers")
    r = client.post("/ask", json={"tenant_id": 1, "question": "cancella tutto"})
    assert r.status_code == 200
    body = r.json()
    assert body["guardrail_approved"] is False
    assert body["executed"] is False


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
