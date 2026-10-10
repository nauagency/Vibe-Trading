"""Native, read-only financial-events board for Vibe-Trading."""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from fastapi import Depends, FastAPI

from src.api.security import require_auth
from src.config.paths import get_runtime_root

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
_LOCALES = {"en", "vi"}
_LOCALIZATION_BATCH_SIZE = 20
_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
_TRANSLATION_CACHE_VERSION = "machine-preview-v4"


def _clean(value: str | None) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", value or "")).split())


def _article_preview(title: str, source: str, description: str) -> str:
    preview = _clean(description)
    base_title = title.removesuffix(f" - {source}") if source else title
    for duplicate in (f"{title} {source}", title, f"{base_title} {source}", base_title):
        if duplicate:
            preview = preview.replace(duplicate, "").strip(" -·")
    if len(preview) >= 24:
        return preview
    return "Open the original source for the full article."


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
        raw_title = _clean(item.findtext("title"))
        source_name = _clean(source.text if source is not None else None)
        title = raw_title.removesuffix(f" - {source_name}") if source_name else raw_title
        items.append({
            "title": title,
            "url": (item.findtext("link") or "").strip(),
            "source": source_name,
            "published": (item.findtext("pubDate") or "").strip(),
            "summary": _article_preview(raw_title, source_name, item.findtext("description") or ""),
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


def _localization_cache_path(locale: str) -> Path:
    return get_runtime_root() / "financial-events" / f"localized-{locale}.json"


def _read_localization_cache(locale: str) -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(_localization_cache_path(locale).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_localization_cache(locale: str, cache: dict[str, dict[str, str]]) -> None:
    path = _localization_cache_path(locale)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _event_key(item: dict[str, Any]) -> str:
    value = f"{_TRANSLATION_CACHE_VERSION}\n{item.get('source', '')}\n{item.get('title', '')}\n{item.get('summary', '')}"
    return hashlib.sha256(value.encode()).hexdigest()


def _request_translations(items: list[dict[str, Any]], locale: str) -> dict[str, dict[str, str]]:
    if locale == "en":
        return {
            _event_key(item): {
                "title": str(item.get("title", "")),
                "summary": (
                    "Scheduled economic event from Forex Factory."
                    if item.get("event_type") == "economic-calendar"
                    else str(item.get("summary", ""))
                ),
            }
            for item in items
        }
    blocks: list[str] = []
    for index, item in enumerate(items):
        preview = (
            "Scheduled economic event from Forex Factory."
            if item.get("event_type") == "economic-calendar"
            else str(item.get("summary", ""))
        )
        blocks.append(f"[[VIBE_ITEM_{index:03d}]]\n{item.get('title', '')}\n[[VIBE_PREVIEW]]\n{preview}")
    form = urlencode({
        "client": "gtx",
        "sl": "en",
        "tl": "vi",
        "dt": "t",
        "q": "\n".join(blocks),
    }).encode("utf-8")
    request = Request(
        _TRANSLATE_URL,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Vibe-Trading/0.1"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed Google HTTPS host
        result = json.loads(response.read().decode("utf-8"))
    translated = "".join(part[0] for part in result[0] if isinstance(part, list) and part and isinstance(part[0], str))
    localized: dict[str, dict[str, str]] = {}
    for index, item in enumerate(items):
        marker = f"[[VIBE_ITEM_{index:03d}]]"
        next_marker = f"[[VIBE_ITEM_{index + 1:03d}]]"
        if marker not in translated:
            continue
        block = translated.split(marker, 1)[1]
        if next_marker in block:
            block = block.split(next_marker, 1)[0]
        if "[[VIBE_PREVIEW]]" not in block:
            continue
        title, preview = block.split("[[VIBE_PREVIEW]]", 1)
        localized[_event_key(item)] = {"title": _clean(title), "summary": _clean(preview)}
    return localized


def _localize_feeds(feeds: list[dict[str, Any]], locale: str) -> bool:
    cache = _read_localization_cache(locale)
    unique: dict[str, dict[str, Any]] = {}
    for feed in feeds:
        for item in feed.get("items", []):
            key = _event_key(item)
            item["_localization_key"] = key
            if item.get("event_type") == "economic-calendar":
                item["_metrics"] = item.get("summary", "")
            unique.setdefault(key, item)
    missing = [item for key, item in unique.items() if key not in cache]
    try:
        for start in range(0, len(missing), _LOCALIZATION_BATCH_SIZE):
            batch = missing[start:start + _LOCALIZATION_BATCH_SIZE]
            cache.update(_request_translations(batch, locale))
        if missing:
            _write_localization_cache(locale, cache)
    except Exception:  # noqa: BLE001 - optional enrichment must not break the board
        return False

    for feed in feeds:
        for item in feed.get("items", []):
            localized = cache.get(item.pop("_localization_key", ""))
            metrics = item.pop("_metrics", "")
            if not localized:
                continue
            item["title"] = localized["title"]
            item["summary"] = f"{localized['summary']} · {metrics}" if metrics else localized["summary"]
    return all(key in cache for key in unique)


def register_financial_events_routes(app: FastAPI) -> None:
    """Expose market-moving headlines without any AI-Trader runtime dependency."""

    @app.get("/api/financial-events", dependencies=[Depends(require_auth)])
    async def financial_events_dashboard(locale: str = "en"):
        locale = locale.lower() if locale.lower() in _LOCALES else "en"
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
        localized = await asyncio.to_thread(_localize_feeds, [*sections, *assets], locale)
        if locale == "vi" and not localized:
            for feed in [*sections, *assets]:
                feed["available"] = False
                feed["items"] = []
                feed["error"] = "localization_unavailable"
        return {
            "mode": "native",
            "read_only": True,
            "provider": "Forex Factory + Google News RSS",
            "priority_provider": "Forex Factory",
            "locale": locale,
            "localized": localized,
            "sections": sections,
            "assets": assets,
            "lanes": assets,
            "total_items": sum(len(feed["items"]) for feed in [*sections, *assets]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
