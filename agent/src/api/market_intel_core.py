"""AI-Trader market-intelligence core adapted to Vibe-Trading.

The scoring rules are ported from AI-Trader's ``market_intel.py``.  Only the
storage and quote adapters differ: Vibe uses Yahoo's public chart endpoint and
its runtime directory instead of AI-Trader's Alpha Vantage/SQLite workers.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.config.paths import get_runtime_root

FEATURED_SYMBOLS = ("NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "META")
BTC_ETF_SYMBOLS = ("IBIT", "FBTC", "ARKB", "BITB", "HODL", "BRRR", "EZBC", "BTCW")
MACRO_SYMBOLS = {"growth": "QQQ", "defensive": "XLP", "safe_haven": "GLD", "dollar": "UUP"}
_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=6mo&interval=1d&events=history"
_CACHE_TTL = 300
_memory_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_path() -> Path:
    return get_runtime_root() / "market-intel" / "snapshots.json"


def _read_store() -> dict[str, Any]:
    try:
        value = json.loads(_cache_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_store(value: dict[str, Any]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _cached(key: str, builder):
    with _cache_lock:
        item = _memory_cache.get(key)
        if item and time.time() - item[0] < _CACHE_TTL:
            return item[1]
    value = builder()
    with _cache_lock:
        _memory_cache[key] = (time.time(), value)
    return value


def _fetch_daily_series(symbol: str) -> list[dict[str, Any]]:
    request = Request(
        _YAHOO_CHART.format(symbol=quote(symbol, safe="")),
        headers={"User-Agent": "Mozilla/5.0 Vibe-Trading market-intel"},
    )
    with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed HTTPS host
        payload = json.loads(response.read().decode("utf-8"))
    result = ((payload.get("chart") or {}).get("result") or [None])[0] or {}
    timestamps = result.get("timestamp") or []
    quote_row = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    adjusted = (((result.get("indicators") or {}).get("adjclose") or [{}])[0]).get("adjclose") or []
    closes = adjusted or quote_row.get("close") or []
    volumes = quote_row.get("volume") or []
    rows = []
    for index, timestamp in enumerate(timestamps):
        close = closes[index] if index < len(closes) else None
        if close is None:
            continue
        rows.append({
            "date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
            "close": float(close),
            "volume": float(volumes[index] or 0) if index < len(volumes) else 0.0,
        })
    rows.reverse()
    if len(rows) < 21:
        raise RuntimeError(f"Not enough daily history for {symbol}")
    return rows


def _series(symbol: str) -> list[dict[str, Any]]:
    return _cached(f"series:{symbol}", lambda: _fetch_daily_series(symbol))


def _return_pct(series: list[dict[str, Any]], days: int) -> float | None:
    if len(series) <= days or not float(series[days]["close"]):
        return None
    return (float(series[0]["close"]) / float(series[days]["close"]) - 1) * 100


def _average(series: list[dict[str, Any]], days: int) -> float | None:
    values = [float(row["close"]) for row in series[:days]]
    return sum(values) / len(values) if len(values) == days else None


def _signal(signal_id: str, label: str, value: float | None, bullish: float, defensive: float, explanation: tuple[str, str, str], *, days: int, source: str, as_of: str) -> dict[str, Any]:
    status = "neutral" if value is None else "bullish" if value >= bullish else "defensive" if value <= defensive else "neutral"
    text = explanation[0] if status == "bullish" else explanation[1] if status == "defensive" else explanation[2]
    return {"id": signal_id, "label": label, "status": status, "value": round(value, 2) if value is not None else None, "unit": "%", "lookback_days": days, "explanation": text, "source": source, "as_of": as_of}


def build_macro_signals() -> dict[str, Any]:
    series = {key: _series(symbol) for key, symbol in MACRO_SYMBOLS.items()}
    series["btc"] = _series("BTC-USD")
    signals = [
        _signal("btc_trend", "BTC trend", _return_pct(series["btc"], 7), 4, -4, ("BTC momentum remains positive over the last week.", "BTC weakened materially over the last week.", "BTC momentum is mixed."), days=7, source="Yahoo Finance", as_of=series["btc"][0]["date"]),
        _signal("qqq_trend", "QQQ trend", _return_pct(series["growth"], 20), 3, -3, ("Growth equities are trending higher.", "Growth equities are losing momentum.", "Growth equity momentum is mixed."), days=20, source="Yahoo Finance", as_of=series["growth"][0]["date"]),
        _signal("gld_trend", "Gold trend", _return_pct(series["safe_haven"], 20), 3, -3, ("Gold strength supports a defensive or inflation-sensitive regime.", "Gold momentum is weak.", "Gold momentum is mixed."), days=20, source="Yahoo Finance", as_of=series["safe_haven"][0]["date"]),
        _signal("uup_trend", "US dollar trend", _return_pct(series["dollar"], 20), 2, -2, ("The US dollar is strengthening.", "The US dollar is weakening.", "The US dollar is range-bound."), days=20, source="Yahoo Finance", as_of=series["dollar"][0]["date"]),
    ]
    qqq = _return_pct(series["growth"], 20) or 0
    xlp = _return_pct(series["defensive"], 20) or 0
    spread = qqq - xlp
    signals.append(_signal("risk_appetite", "Growth vs defensive spread", spread, 2, -2, ("Growth is outperforming defensive equities.", "Defensive equities are outperforming growth.", "Risk appetite is balanced."), days=20, source="Yahoo Finance", as_of=series["growth"][0]["date"]))
    bullish = sum(item["status"] == "bullish" for item in signals)
    defensive = sum(item["status"] == "defensive" for item in signals)
    verdict = "risk_on" if bullish >= defensive + 2 else "risk_off" if defensive >= bullish + 2 else "mixed"
    return {"available": True, "verdict": verdict, "bullish_count": bullish, "defensive_count": defensive, "total_count": len(signals), "signals": signals, "meta": {"lookback_days": 20}, "source": {"provider": "Yahoo Finance", "ported_from": "AI-Trader"}, "created_at": _now()}


def build_etf_flows() -> dict[str, Any]:
    rows = []
    for symbol in BTC_ETF_SYMBOLS:
        try:
            series = _series(symbol)
            latest, previous = series[0], series[1]
            baseline = [float(row.get("volume") or 0) for row in series[1:6] if float(row.get("volume") or 0) > 0]
            avg_volume = sum(baseline) / len(baseline) if baseline else float(latest.get("volume") or 1)
            change = (float(latest["close"]) / float(previous["close"]) - 1) * 100
            ratio = float(latest.get("volume") or 0) / avg_volume if avg_volume else 1
            score = change * max(ratio, .1)
            direction = "inflow" if score >= 2.5 else "outflow" if score <= -2.5 else "mixed"
            rows.append({"symbol": symbol, "price_change_pct": round(change, 2), "latest_volume": int(latest.get("volume") or 0), "avg_volume": int(avg_volume), "volume_ratio": round(ratio, 2), "estimated_flow_score": round(score, 2), "direction": direction, "as_of": latest["date"]})
        except Exception:
            continue
    rows.sort(key=lambda row: abs(row["estimated_flow_score"]), reverse=True)
    inflows = sum(row["direction"] == "inflow" for row in rows)
    outflows = sum(row["direction"] == "outflow" for row in rows)
    net = round(sum(row["estimated_flow_score"] for row in rows), 2)
    direction = "inflow" if inflows >= outflows + 2 and net > 0 else "outflow" if outflows >= inflows + 2 and net < 0 else "mixed"
    summary = {"direction": direction, "summary": f"Estimated BTC ETF flow is {direction}.", "inflow_count": inflows, "outflow_count": outflows, "tracked_count": len(rows), "net_score": net, "is_estimated": True}
    return {"available": bool(rows), "summary": summary, "etfs": rows, "created_at": _now(), "is_estimated": True}


def build_stock_analysis(symbol: str) -> dict[str, Any]:
    symbol = symbol.strip().upper()
    series = _series(symbol)
    price = float(series[0]["close"])
    ma5, ma10, ma20, ma60 = (_average(series, days) for days in (5, 10, 20, 60))
    ret5, ret20 = _return_pct(series, 5) or 0, _return_pct(series, 20) or 0
    recent = [float(row["close"]) for row in series[:20]]
    support, resistance = min(recent), max(recent)
    bullish: list[str] = []
    risks: list[str] = []
    score = 0.0
    if ma20 and price > ma20: bullish.append("Price is above the 20-day moving average."); score += 1
    else: risks.append("Price is below the 20-day moving average."); score -= 1
    if ma60 and price > ma60: bullish.append("Price is above the 60-day moving average."); score += 1
    elif ma60: risks.append("Price is below the 60-day moving average."); score -= 1
    if ret5 > 2: bullish.append("Short-term momentum is positive."); score += 1
    elif ret5 < -2: risks.append("Short-term momentum weakened materially."); score -= 1
    if ret20 > 5: bullish.append("Monthly trend remains constructive."); score += 1
    elif ret20 < -5: risks.append("Monthly trend remains weak."); score -= 1
    if ma5 and ma10 and ma20 and ma5 > ma10 > ma20: bullish.append("Moving averages are stacked in a bullish order."); score += 1
    elif ma5 and ma10 and ma20 and ma5 < ma10 < ma20: risks.append("Moving averages are stacked in a bearish order."); score -= 1
    distance_support = (price / support - 1) * 100 if support else 0
    distance_resistance = (resistance / price - 1) * 100 if price else 0
    if distance_resistance < 3: risks.append("Price is approaching the recent resistance zone."); score -= .5
    if distance_support < 3: bullish.append("Price is holding near recent support."); score += .5
    if score >= 3: signal, trend = "buy", "bullish"
    elif score >= 1: signal, trend = "hold", "constructive"
    elif score <= -3: signal, trend = "sell", "defensive"
    else: signal, trend = "watch", "mixed"
    summary = f"{symbol} is {trend}; model score {score:+.1f}. Five-day return {ret5:+.2f}% and 20-day return {ret20:+.2f}%."
    return {"available": True, "symbol": symbol, "market": "us-stock", "analysis_id": f"{symbol}:{series[0]['date']}", "current_price": round(price, 2), "currency": "USD", "signal": signal, "signal_score": round(score, 2), "trend_status": trend, "support_levels": [round(support, 2)], "resistance_levels": [round(resistance, 2)], "bullish_factors": bullish, "risk_factors": risks, "summary": summary, "analysis": {"return_5d_pct": round(ret5, 2), "return_20d_pct": round(ret20, 2), "moving_averages": {"ma5": round(ma5, 2) if ma5 else None, "ma10": round(ma10, 2) if ma10 else None, "ma20": round(ma20, 2) if ma20 else None, "ma60": round(ma60, 2) if ma60 else None}, "distance_to_support_pct": round(distance_support, 2), "distance_to_resistance_pct": round(distance_resistance, 2)}, "price_state": "delayed", "price_source": "Yahoo Finance", "price_as_of": series[0]["date"], "created_at": _now()}


def stock_latest(symbol: str) -> dict[str, Any]:
    analysis = _cached(f"stock:{symbol.upper()}", lambda: build_stock_analysis(symbol))
    store = _read_store()
    history = store.setdefault("stocks", {}).setdefault(symbol.upper(), [])
    if not history or history[0].get("analysis_id") != analysis["analysis_id"]:
        history.insert(0, analysis)
        del history[30:]
        _write_store(store)
    return analysis


def stock_history(symbol: str, limit: int = 10) -> dict[str, Any]:
    stock_latest(symbol)
    history = _read_store().get("stocks", {}).get(symbol.upper(), [])
    return {"available": bool(history), "symbol": symbol.upper(), "history": history[:max(1, min(limit, 30))]}


def featured_stocks(limit: int = 6) -> dict[str, Any]:
    items = []
    for symbol in FEATURED_SYMBOLS[:max(1, min(limit, len(FEATURED_SYMBOLS)))]:
        try: items.append(stock_latest(symbol))
        except Exception as exc: items.append({"available": False, "symbol": symbol, "error": type(exc).__name__})
    return {"available": any(item.get("available") for item in items), "items": items}
