from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import market_routes
from src.api.market_routes import register_market_routes
from src.api.security import require_auth


def test_native_market_combines_paper_data_and_focus_activity(monkeypatch) -> None:
    monkeypatch.setattr(market_routes, "_paper_account", lambda: {
        "cash": 99_000.0,
        "equity": 101_000.0,
        "positions": [{
            "symbol": "BTCUSDT", "market": "crypto", "side": "long", "quantity": 0.1,
            "entry_price": 90_000.0, "current_price": 92_000.0, "unrealized_pnl": 200.0,
            "opened_at": "2026-10-10T00:00:00Z",
        }],
    })
    monkeypatch.setattr(market_routes, "_native_strategies", lambda: [{
        "signal_id": 7, "title": "BTC H1 breakout", "content": "Sharpe=1.2",
        "symbols": ["BTCUSDT"], "tags": ["paper-only"], "created_at": "2026-10-10T00:00:00Z",
    }])

    async def focus():
        return [{"symbol": "BTC", "market": "crypto", "event_count": 6, "latest_event_at": "2026-10-10"}]

    monkeypatch.setattr(market_routes, "_focus_activity", focus)
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: None
    register_market_routes(app)

    response = TestClient(app).get("/api/market?market=crypto")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "native"
    assert body["paper_only"] is False
    assert body["live_trading_enabled"] is True
    assert body["capabilities"]["live_orders"] is True
    assert body["total"] == 2
    assert {item["kind"] for item in body["items"]} == {"position", "strategy"}
    assert next(item for item in body["trending"] if item["symbol"] == "BTC")["event_count"] == 6


def test_unknown_market_falls_back_to_all(monkeypatch) -> None:
    monkeypatch.setattr(market_routes, "_paper_account", lambda: {"cash": 100_000, "equity": 100_000, "positions": []})
    monkeypatch.setattr(market_routes, "_native_strategies", lambda: [])

    async def focus():
        return []

    monkeypatch.setattr(market_routes, "_focus_activity", focus)
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: None
    register_market_routes(app)
    body = TestClient(app).get("/api/market?market=bad-value").json()
    assert body["selected_market"] == "all"
