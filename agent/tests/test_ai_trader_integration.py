from pathlib import Path
from unittest.mock import Mock, patch

from src.integrations.ai_trader import build_ai_trader_payload, publish_backtest_run


def _run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run_20261010_120000"
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "req.json").write_text(
        '{"prompt":"Backtest BTC breakout","context":{"codes":["BTCUSDT"],"start_date":"2023-01-01","end_date":"2026-10-10"}}',
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "metrics.csv").write_text(
        "total_return,sharpe,trade_count\n0.21,1.3,42\n",
        encoding="utf-8",
    )
    return run_dir


def test_build_payload_uses_compact_research_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_PUBLIC_URL", "https://vibetrading.example")
    payload = build_ai_trader_payload(_run(tmp_path))
    assert payload["symbols"] == ["BTCUSDT"]
    assert payload["metrics"] == {"total_return": 0.21, "sharpe": 1.3, "trade_count": 42}
    assert payload["source_url"] == "https://vibetrading.example"


def test_publish_is_disabled_without_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("VIBE_BRIDGE_SECRET", raising=False)
    monkeypatch.setenv("AI_TRADER_BRIDGE_URL", "https://aitrader.example")
    assert publish_backtest_run(_run(tmp_path)) is None


def test_publish_sends_secret_and_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VIBE_BRIDGE_SECRET", "bridge-test-secret")
    monkeypatch.setenv("AI_TRADER_BRIDGE_URL", "https://aitrader.example")
    response = Mock()
    response.json.return_value = {"success": True, "signal_id": 7, "duplicate": False}
    response.raise_for_status.return_value = None
    with patch("src.integrations.ai_trader.httpx.post", return_value=response) as post:
        result = publish_backtest_run(_run(tmp_path))
    assert result == {"success": True, "signal_id": 7, "duplicate": False}
    assert post.call_args.kwargs["headers"] == {"X-Vibe-Bridge-Key": "bridge-test-secret"}
    assert post.call_args.kwargs["json"]["run_id"] == "run_20261010_120000"
