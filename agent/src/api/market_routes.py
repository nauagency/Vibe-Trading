"""Native, read-only market board for Vibe-Trading.

The board replaces AI-Trader's marketplace view without proxying or depending
on the AI-Trader service. It combines Vibe backtests, the local paper account,
and the four focus-market news lanes into one safe research surface.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Query

from src.api.financial_events_routes import _ASSET_LANES, _feed
from src.api.paper_trading_routes import _native_strategies, _paper_account
from src.api.security import require_auth

_MARKETS = {"all", "crypto", "metals", "forex", "energy", "us-stock", "prediction"}


def _market_for_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    if any(token in normalized for token in ("BTC", "ETH", "SOL", "XRP", "DOGE")):
        return "crypto"
    if any(token in normalized for token in ("XAU", "GOLD", "XAG", "SILVER")):
        return "metals"
    if any(token in normalized for token in ("USOIL", "WTI", "BRENT", "UKOIL")):
        return "energy"
    if normalized.endswith(("USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "NZD")) and len(normalized) == 6:
        return "forex"
    if normalized.startswith(("POLYMARKET", "PREDICTION")):
        return "prediction"
    return "us-stock"


def _focus_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
    if "BTC" in normalized:
        return "BTC"
    if any(token in normalized for token in ("XAU", "GOLD")):
        return "XAU"
    if normalized.startswith("EURUSD"):
        return "EURUSD"
    if any(token in normalized for token in ("USOIL", "WTI", "BRENT", "UKOIL")):
        return "USOIL"
    return symbol.upper()


def _position_items(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, position in enumerate(positions):
        if not isinstance(position, dict):
            continue
        symbol = str(position.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        items.append({
            "id": f"position-{index}-{symbol}",
            "kind": "position",
            "market": str(position.get("market") or _market_for_symbol(symbol)),
            "title": f"{symbol} paper position",
            "content": "",
            "symbols": [symbol],
            "side": str(position.get("side") or "long"),
            "quantity": float(position.get("quantity") or 0),
            "price": position.get("current_price") or position.get("entry_price"),
            "pnl": position.get("unrealized_pnl"),
            "tags": ["paper-only", "open-position"],
            "created_at": str(position.get("opened_at") or ""),
        })
    return items


def _strategy_items(strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for strategy in strategies:
        symbols = [str(value).strip().upper() for value in strategy.get("symbols", []) if str(value).strip()]
        market = _market_for_symbol(symbols[0]) if symbols else "us-stock"
        items.append({
            "id": f"strategy-{strategy.get('signal_id')}",
            "kind": "strategy",
            "market": market,
            "title": str(strategy.get("title") or "Vibe backtest"),
            "content": str(strategy.get("content") or ""),
            "symbols": symbols,
            "side": None,
            "quantity": None,
            "price": None,
            "pnl": None,
            "tags": list(strategy.get("tags") or []),
            "created_at": str(strategy.get("created_at") or ""),
        })
    return items


async def _focus_activity() -> list[dict[str, Any]]:
    feeds = await asyncio.gather(
        *(_feed(feed_id, label, query) for feed_id, label, query in _ASSET_LANES),
        return_exceptions=True,
    )
    activity: list[dict[str, Any]] = []
    for (_feed_id, label, _query), feed in zip(_ASSET_LANES, feeds):
        payload = {} if isinstance(feed, Exception) else feed
        items = payload.get("items", []) if isinstance(payload, dict) else []
        activity.append({
            "symbol": label,
            "market": _market_for_symbol(label),
            "event_count": len(items),
            "latest_event_at": str(items[0].get("published") or "") if items else "",
        })
    return activity


async def _market_dashboard(selected_market: str) -> dict[str, Any]:
    account = _paper_account()
    all_items = [*_position_items(account["positions"]), *_strategy_items(_native_strategies())]
    filtered_items = all_items if selected_market == "all" else [
        item for item in all_items if item["market"] == selected_market
    ]

    mentions: Counter[str] = Counter()
    for item in all_items:
        for symbol in item["symbols"]:
            mentions[_focus_symbol(symbol)] += 1
    prices = {
        _focus_symbol(str(position.get("symbol") or "")): position.get("current_price")
        for position in account["positions"] if isinstance(position, dict)
    }
    trends = []
    for focus in await _focus_activity():
        symbol = focus["symbol"]
        trends.append({
            **focus,
            "current_price": prices.get(symbol),
            "signal_count": mentions[symbol],
            "position_count": sum(1 for item in account["positions"] if _focus_symbol(str(item.get("symbol") or "")) == symbol),
        })
    known_focus = {item["symbol"] for item in trends}
    for symbol, count in mentions.most_common():
        if symbol in known_focus:
            continue
        trends.append({
            "symbol": symbol,
            "market": _market_for_symbol(symbol),
            "event_count": 0,
            "latest_event_at": "",
            "current_price": prices.get(symbol),
            "signal_count": count,
            "position_count": sum(1 for item in account["positions"] if _focus_symbol(str(item.get("symbol") or "")) == symbol),
        })
    trends.sort(key=lambda item: (item["position_count"], item["signal_count"], item["event_count"]), reverse=True)

    counts = Counter(item["market"] for item in all_items)
    return {
        "mode": "native",
        "read_only": True,
        "paper_only": True,
        "live_trading_enabled": False,
        "selected_market": selected_market,
        "items": filtered_items,
        "total": len(filtered_items),
        "counts": {"all": len(all_items), **{market: counts[market] for market in sorted(_MARKETS - {"all"})}},
        "trending": trends,
        "account": {"cash": account["cash"], "equity": account["equity"], "open_positions": len(account["positions"])},
        "capabilities": {"signals": True, "strategies": True, "paper_positions": True, "live_orders": False},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def register_market_routes(app: FastAPI) -> None:
    """Register the standalone Vibe market dashboard."""

    @app.get("/api/market", dependencies=[Depends(require_auth)])
    async def market_dashboard(market: str = Query("all")):
        selected = market.lower().strip()
        if selected not in _MARKETS:
            selected = "all"
        return await _market_dashboard(selected)
