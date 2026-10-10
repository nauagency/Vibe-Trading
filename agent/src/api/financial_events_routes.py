"""Native, read-only financial-events board for Vibe-Trading."""

from __future__ import annotations

import asyncio
import html
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from fastapi import Depends, FastAPI

from src.api.security import require_auth

_FEED_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
_LANES = (
    ("BTC", "Bitcoin cryptocurrency market when:2d"),
    ("XAU", "gold XAUUSD Federal Reserve inflation when:2d"),
    ("EURUSD", "EURUSD ECB Federal Reserve forex when:2d"),
    ("MACRO", "Federal Reserve CPI inflation jobs interest rates when:2d"),
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


async def _lane(name: str, query: str) -> dict[str, Any]:
    try:
        items = await asyncio.to_thread(_load_feed, query)
        return {"id": name.lower(), "label": name, "available": True, "items": items}
    except Exception as exc:  # noqa: BLE001 - one failed source must not break the board
        return {
            "id": name.lower(),
            "label": name,
            "available": False,
            "items": [],
            "error": f"feed_unavailable:{type(exc).__name__}",
        }


def register_financial_events_routes(app: FastAPI) -> None:
    """Expose market-moving headlines without any AI-Trader runtime dependency."""

    @app.get("/api/financial-events", dependencies=[Depends(require_auth)])
    async def financial_events_dashboard():
        lanes = list(await asyncio.gather(*(_lane(name, query) for name, query in _LANES)))
        return {
            "mode": "native",
            "read_only": True,
            "provider": "Google News RSS",
            "lanes": lanes,
            "total_items": sum(len(lane["items"]) for lane in lanes),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
