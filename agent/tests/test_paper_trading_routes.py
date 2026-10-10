from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.paper_trading_routes import register_paper_trading_routes
from src.api.security import require_auth


def test_native_dashboard_uses_vibe_backtests(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIBE_TRADING_HOME", str(tmp_path))
    run = tmp_path / "runs" / "run_20261010_120000"
    artifacts = run / "artifacts"
    artifacts.mkdir(parents=True)
    (run / "state.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
    (run / "req.json").write_text(
        json.dumps({"prompt": "BTC H1 breakout", "symbols": ["BTCUSDT"]}),
        encoding="utf-8",
    )
    (artifacts / "metrics.csv").write_text(
        "total_return,sharpe,trade_count\n0.18,1.2,84\n",
        encoding="utf-8",
    )

    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: None
    register_paper_trading_routes(app)
    response = TestClient(app).get("/api/paper-trading")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "paper"
    assert body["live_trading_enabled"] is False
    assert body["account"]["cash"] == 100_000
    assert body["strategies"][0]["symbols"] == ["BTCUSDT"]
    assert body["strategies"][0]["source"] == "vibe-trading"
    assert body["capabilities"]["live_orders"] is False
