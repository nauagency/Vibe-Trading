from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import financial_events_routes
from src.api.financial_events_routes import register_financial_events_routes
from src.api.security import require_auth


def test_native_financial_events_board(monkeypatch) -> None:
    monkeypatch.setattr(
        financial_events_routes,
        "_load_feed",
        lambda query, limit=8: [{
            "title": f"Event for {query}",
            "url": "https://example.com/event",
            "source": "Example",
            "published": "Fri, 10 Oct 2026 10:00:00 GMT",
            "summary": "Market-moving update",
        }],
    )

    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: None
    register_financial_events_routes(app)
    response = TestClient(app).get("/api/financial-events")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "native"
    assert body["read_only"] is True
    assert body["total_items"] == 4
    assert [lane["label"] for lane in body["lanes"]] == ["BTC", "XAU", "EURUSD", "MACRO"]
    assert all(lane["available"] for lane in body["lanes"])
