from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import financial_events_routes
from src.api.financial_events_routes import register_financial_events_routes
from src.api.security import require_auth


def test_native_financial_events_board(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        financial_events_routes,
        "_load_feed",
        lambda query, limit=8: [{
            "title": f"Event for {query}",
            "url": "https://example.com/event",
            "source": "Example",
            "published": "Fri, 10 Oct 2026 10:00:00 GMT",
            "summary": "Market-moving update",
        }],
    )
    monkeypatch.setattr(
        financial_events_routes,
        "_load_forex_factory",
        lambda: [{
            "title": "US CPI",
            "url": "https://www.forexfactory.com/calendar",
            "source": "Forex Factory",
            "published": "2026-10-10T08:30:00-04:00",
            "summary": "Forecast: 0.3%",
            "country": "USD",
            "impact": "High",
            "event_type": "economic-calendar",
        }],
    )
    monkeypatch.setattr(
        financial_events_routes,
        "_localization_cache_path",
        lambda locale: tmp_path / f"localized-{locale}.json",
    )
    monkeypatch.setattr(
        financial_events_routes,
        "_request_translations",
        lambda items, locale: {
            financial_events_routes._event_key(item): {
                "title": "Chỉ số giá tiêu dùng Mỹ" if item["source"] == "Forex Factory" else "Tin thị trường đã dịch",
                "summary": "Sự kiện có thể làm gia tăng biến động thị trường.",
            }
            for item in items
        },
    )

    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: None
    register_financial_events_routes(app)
    response = TestClient(app).get("/api/financial-events?locale=vi")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "native"
    assert body["read_only"] is True
    assert body["locale"] == "vi"
    assert body["localized"] is True
    assert body["total_items"] == 14
    assert [section["id"] for section in body["sections"]] == [
        "macro-signals", "etf-flows", "featured-stocks", "financial-news",
    ]
    assert [lane["label"] for lane in body["assets"]] == ["XAU", "BTC", "USOIL", "EURUSD"]
    assert body["lanes"] == body["assets"]
    assert all(feed["available"] for feed in [*body["sections"], *body["assets"]])
    assert body["priority_provider"] == "Forex Factory"
    assert body["sections"][0]["items"][0]["source"] == "Forex Factory"
    assert body["sections"][0]["items"][0]["title"] == "Chỉ số giá tiêu dùng Mỹ"
    assert "Forecast: 0.3%" in body["sections"][0]["items"][0]["summary"]
    assert body["assets"][0]["items"][0]["source"] == "Forex Factory"
