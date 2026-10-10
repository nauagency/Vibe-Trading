from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import community_core as core
from src.api.community_routes import register_community_routes
from src.api.security import require_auth


def test_community_routes_cover_ai_trader_workflow(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(core, "get_runtime_root", lambda: tmp_path)
    monkeypatch.setattr(core, "_native_strategies", lambda _limit=100: [])
    monkeypatch.setattr(core, "_paper_account", lambda: {"positions": []})
    core._initialized = False
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: None
    register_community_routes(app)
    client = TestClient(app)

    assert client.post("/api/signals/strategy", json={"title": "BTC", "content": "Breakout", "symbols": ["BTCUSD"]}).status_code == 200
    assert client.post("/api/signals/realtime", json={"symbol": "BTCUSD", "side": "buy", "price": 60000, "quantity": .1}).status_code == 200
    assert client.get("/api/positions").json()["positions"][0]["symbol"] == "BTCUSD"
    assert client.get("/api/profit/history").json()["top_agents"][0]["history"]
    assert client.get("/api/signals/following").status_code == 200

    challenge = client.post("/api/challenges", json={"title": "BTC challenge", "market": "crypto", "symbol": "BTCUSD"}).json()
    key = challenge["challenge_key"]
    assert client.post(f"/api/challenges/{key}/join").status_code == 200
    assert client.post(f"/api/challenges/{key}/trade", json={"symbol": "BTCUSD", "side": "buy", "price": 60000, "quantity": .1}).status_code == 200
    assert client.get(f"/api/challenges/{key}/leaderboard").json()["leaderboard"][0]["rank"] == 1
