"""Native, read-only financial-events board for Vibe-Trading."""

from __future__ import annotations

import asyncio
import html
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from fastapi import Depends, FastAPI

from src.api.security import require_auth

_FEED_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
_FOREX_FACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FOREX_FACTORY_CALENDAR = "https://www.forexfactory.com/calendar"
_CORE_SECTIONS = (
    ("macro-signals", "Macro signals", "Federal Reserve CPI inflation jobs interest rates economic outlook when:2d"),
    ("etf-flows", "ETF flows", "ETF inflows outflows fund flows Bitcoin gold equities when:2d"),
    ("featured-stocks", "Featured stocks", "US stocks market movers earnings analyst upgrades when:2d"),
    ("financial-news", "Financial news", "global financial markets economy stocks commodities currencies when:2d"),
)
_ASSET_LANES = (
    ("xau", "XAU", "gold XAUUSD Federal Reserve inflation when:2d"),
    ("btc", "BTC", "Bitcoin cryptocurrency market when:2d"),
    ("usoil", "USOIL", "WTI crude oil USOIL OPEC inventory when:2d"),
    ("eurusd", "EURUSD", "EURUSD ECB Federal Reserve forex when:2d"),
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(value: str | None) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", value or "")).split())


def _load_feed(query: str, limit: int = 8) -> list[dict[str, Any]]:
    request = Request(
        _FEED_URL.format(query=quote_plus(query)),
        headers={"User-Agent": "Vibe-Trading/0.1 financial-events"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed HTTPS host
        root = ElementTree.fromstring(response.read())

    items: list[dict[str, Any]] = []
    for item in root.findall("./channel/item")[:limit]:
        source = item.find("source")
        items.append({
            "title": _clean(item.findtext("title")),
            "url": (item.findtext("link") or "").strip(),
            "source": _clean(source.text if source is not None else None),
            "published": (item.findtext("pubDate") or "").strip(),
            "summary": _clean(item.findtext("description")),
        })
    return [item for item in items if item["title"] and item["url"]]


def _load_forex_factory() -> list[dict[str, Any]]:
    request = Request(
        _FOREX_FACTORY_URL,
        headers={"User-Agent": "Vibe-Trading/0.1 financial-events"},
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed HTTPS host
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        return []
    events: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict) or not raw.get("title"):
            continue
        country = str(raw.get("country") or "").upper()
        impact = str(raw.get("impact") or "")
        details = [
            f"Actual: {raw['actual']}" if raw.get("actual") else "",
            f"Forecast: {raw['forecast']}" if raw.get("forecast") else "",
            f"Previous: {raw['previous']}" if raw.get("previous") else "",
        ]
        events.append({
            "title": _clean(str(raw["title"])),
            "url": _FOREX_FACTORY_CALENDAR,
            "source": "Forex Factory",
            "published": str(raw.get("date") or ""),
            "summary": " · ".join(part for part in details if part),
            "country": country,
            "impact": impact,
            "event_type": "economic-calendar",
        })
    impact_order = {"high": 0, "medium": 1, "low": 2, "holiday": 3}
    return sorted(events, key=lambda item: (impact_order.get(str(item["impact"]).lower(), 4), item["published"]))


def _forex_factory_for(feed_id: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if feed_id == "macro-signals":
        return events[:12]
    if feed_id == "financial-news":
        return [item for item in events if str(item.get("impact", "")).lower() == "high"][:8]
    if feed_id == "xau":
        countries, impacts = {"USD"}, {"high", "medium"}
    elif feed_id == "btc":
        countries, impacts = {"USD"}, {"high"}
    elif feed_id == "usoil":
        countries, impacts = {"USD", "CAD"}, {"high", "medium"}
    elif feed_id == "eurusd":
        countries, impacts = {"USD", "EUR"}, {"high", "medium"}
    else:
        return []
    return [
        item for item in events
        if item.get("country") in countries and str(item.get("impact", "")).lower() in impacts
    ][:8]


async def _feed(feed_id: str, label: str, query: str) -> dict[str, Any]:
    try:
        items = await asyncio.to_thread(_load_feed, query)
        return {"id": feed_id, "label": label, "available": True, "items": items}
    except Exception as exc:  # noqa: BLE001 - one failed source must not break the board
        return {
            "id": feed_id,
            "label": label,
            "available": False,
            "items": [],
            "error": f"feed_unavailable:{type(exc).__name__}",
        }


def register_financial_events_routes(app: FastAPI) -> None:
    """Expose market-moving headlines without any AI-Trader runtime dependency."""

    @app.get("/api/financial-events", dependencies=[Depends(require_auth)])
    async def financial_events_dashboard():
        sections, assets, forex_factory = await asyncio.gather(
            asyncio.gather(*(_feed(feed_id, label, query) for feed_id, label, query in _CORE_SECTIONS)),
            asyncio.gather(*(_feed(feed_id, label, query) for feed_id, label, query in _ASSET_LANES)),
            asyncio.to_thread(_load_forex_factory),
            return_exceptions=True,
        )
        sections = list(sections) if not isinstance(sections, Exception) else []
        assets = list(assets) if not isinstance(assets, Exception) else []
        forex_factory = [] if isinstance(forex_factory, Exception) else list(forex_factory)
        for feed in [*sections, *assets]:
            priority_items = _forex_factory_for(feed["id"], forex_factory)
            if priority_items:
                feed["items"] = [*priority_items, *feed["items"]]
                feed["sources"] = ["Forex Factory", "Google News RSS"]
            else:
                feed["sources"] = ["Google News RSS"]
        return {
            "mode": "native",
            "read_only": True,
            "provider": "Forex Factory + Google News RSS",
            "priority_provider": "Forex Factory",
            "sections": sections,
            "assets": assets,
            "lanes": assets,
            "total_items": sum(len(feed["items"]) for feed in [*sections, *assets]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
