from __future__ import annotations

from src.api import market_intel_core as core


def _series(start: float = 100.0, count: int = 80, step: float = 1.0):
    # Core series are newest first.
    return [
        {"date": f"2026-09-{(30 - index % 28):02d}", "close": start - index * step, "volume": 1_000_000 + index * 10_000}
        for index in range(count)
    ]


def test_ported_macro_rules_return_full_signal_set(monkeypatch):
    monkeypatch.setattr(core, "_series", lambda _symbol: _series())
    payload = core.build_macro_signals()
    assert payload["available"] is True
    assert payload["verdict"] == "risk_on"
    assert {item["id"] for item in payload["signals"]} == {
        "btc_trend", "qqq_trend", "gld_trend", "uup_trend", "risk_appetite"
    }


def test_ported_etf_and_stock_analysis(monkeypatch):
    monkeypatch.setattr(core, "_series", lambda _symbol: _series())
    etf = core.build_etf_flows()
    stock = core.build_stock_analysis("NVDA")
    assert etf["summary"]["tracked_count"] == len(core.BTC_ETF_SYMBOLS)
    assert stock["available"] is True
    assert stock["symbol"] == "NVDA"
    assert stock["signal"] in {"buy", "hold", "watch", "sell"}
    assert stock["support_levels"] and stock["resistance_levels"]
