"""Publish completed research runs to AI-Trader without enabling live trading."""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from src.ui_services import load_run_context

logger = logging.getLogger(__name__)


def _metrics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "artifacts" / "metrics.csv"
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle), {})
    except OSError:
        return {}
    result: dict[str, Any] = {}
    for key, raw in row.items():
        if not key or raw in (None, ""):
            continue
        try:
            number = float(raw)
            result[key] = int(number) if number.is_integer() else number
        except (TypeError, ValueError):
            result[key] = str(raw)[:200]
    return result


def build_ai_trader_payload(run_dir: Path) -> dict[str, Any]:
    context = load_run_context(run_dir)
    source_url = os.getenv("VIBE_PUBLIC_URL", "https://vibetrading.nauagency.asia").strip()
    return {
        "run_id": run_dir.name,
        "status": "success",
        "prompt": context.get("prompt") or None,
        "symbols": context.get("codes") or [],
        "start_date": context.get("start_date"),
        "end_date": context.get("end_date"),
        "metrics": _metrics(run_dir),
        "source_url": source_url or None,
    }


def publish_backtest_run(run_dir: Path) -> dict[str, Any] | None:
    """Send one successful backtest to AI-Trader; failures never fail the run."""
    base_url = os.getenv("AI_TRADER_BRIDGE_URL", "").strip().rstrip("/")
    secret = os.getenv("VIBE_BRIDGE_SECRET", "").strip()
    if not base_url or not secret:
        return None
    if not (run_dir / "artifacts" / "metrics.csv").is_file():
        return None
    try:
        response = httpx.post(
            f"{base_url}/api/integrations/vibe/runs",
            json=build_ai_trader_payload(run_dir),
            headers={"X-Vibe-Bridge-Key": secret},
            timeout=httpx.Timeout(8.0, connect=4.0),
            follow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        logger.info(
            "AI-Trader bridge accepted run %s (signal_id=%s, duplicate=%s)",
            run_dir.name,
            payload.get("signal_id"),
            payload.get("duplicate", False),
        )
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("AI-Trader bridge could not publish run %s: %s", run_dir.name, exc)
        return None
