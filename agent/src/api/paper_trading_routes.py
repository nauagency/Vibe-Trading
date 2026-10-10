"""Native Vibe-Trading paper dashboard with no AI-Trader dependency."""

from __future__ import annotations

import csv
import json
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI

from src.api.security import require_auth
from src.config.paths import get_runs_dir, get_runtime_root

_SUCCESS_STATUSES = {"success", "completed", "ok"}
_DEFAULT_CASH = 100_000.0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _run_status(run_dir: Path) -> str:
    state = _read_json(run_dir / "state.json")
    if state:
        return str(state.get("status") or "unknown").lower()
    if (run_dir / "artifacts" / "equity.csv").exists() or (run_dir / "review_report.json").exists():
        return "success"
    return "unknown"


def _run_prompt(run_dir: Path) -> str:
    request = _read_json(run_dir / "req.json")
    planner = _read_json(run_dir / "planner_output.json")
    prompt = request.get("prompt") or planner.get("user_goal") or planner.get("goal")
    if prompt:
        return str(prompt)
    try:
        return (run_dir / "user_prompt.txt").read_text(encoding="utf-8").strip() or "Vibe backtest"
    except OSError:
        return "Vibe backtest"


def _run_metrics(run_dir: Path) -> dict[str, str]:
    try:
        with (run_dir / "artifacts" / "metrics.csv").open("r", encoding="utf-8", newline="") as handle:
            return next(csv.DictReader(handle), {})
    except (OSError, csv.Error):
        return {}


def _run_context(run_dir: Path) -> dict[str, Any]:
    for name in ("run_context.json", "config.json", "req.json", "planner_output.json"):
        value = _read_json(run_dir / name)
        if value:
            return value
    return {}


def _symbols(context: dict[str, Any]) -> list[str]:
    raw = context.get("codes") or context.get("symbols") or context.get("tickers") or []
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.replace(";", ",").split(",")]
    if not isinstance(raw, list):
        return []
    return [str(item).strip().upper() for item in raw if str(item).strip()]


def _native_strategies(limit: int = 100) -> list[dict[str, Any]]:
    runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return []
    directories = sorted(
        (item for item in runs_dir.iterdir() if item.is_dir()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    strategies: list[dict[str, Any]] = []
    for run_dir in directories:
        if len(strategies) >= limit or _run_status(run_dir) not in _SUCCESS_STATUSES:
            continue
        prompt = _run_prompt(run_dir)
        metrics = _run_metrics(run_dir)
        context = _run_context(run_dir)
        symbols = _symbols(context)
        metric_text = ", ".join(
            f"{name}={value}" for name, value in metrics.items()
            if value not in (None, "") and name in {"total_return", "annual_return", "sharpe", "max_drawdown", "win_rate", "trade_count"}
        ) or "Metrics available in the backtest report"
        title_symbols = ", ".join(symbols) or "Market research"
        strategies.append({
            "signal_id": zlib.crc32(run_dir.name.encode("utf-8")),
            "market": "native",
            "title": f"Vibe backtest · {title_symbols}",
            "content": f"{prompt}\nRun: {run_dir.name}\nMetrics: {metric_text}",
            "symbols": symbols,
            "tags": ["vibe-trading", "backtest", "paper_candidate", "paper-only"],
            "source": "vibe-trading",
            "created_at": datetime.fromtimestamp(run_dir.stat().st_mtime, timezone.utc).isoformat(),
        })
    return strategies


def _paper_account() -> dict[str, Any]:
    state = _read_json(get_runtime_root() / "paper-trading.json")
    cash = float(state.get("cash") or _DEFAULT_CASH)
    raw_positions = state.get("positions")
    positions = raw_positions if isinstance(raw_positions, list) else []
    unrealized = sum(float(item.get("unrealized_pnl") or 0) for item in positions if isinstance(item, dict))
    market_value = sum(
        abs(float(item.get("quantity") or 0)) * float(item.get("current_price") or item.get("entry_price") or 0)
        for item in positions if isinstance(item, dict)
    )
    return {
        "name": "Vibe Paper Account",
        "email": None,
        "points": 0,
        "cash": cash,
        "equity": cash + market_value,
        "unrealized_pnl": unrealized,
        "positions": positions,
    }


def register_paper_trading_routes(app: FastAPI) -> None:
    """Expose Vibe's native, read-only, paper-only dashboard."""

    @app.get("/api/paper-trading", dependencies=[Depends(require_auth)])
    async def paper_trading_dashboard():
        account = _paper_account()
        return {
            "mode": "paper",
            "live_trading_enabled": False,
            "account": {key: value for key, value in account.items() if key != "positions"},
            "positions": account["positions"],
            "strategies": _native_strategies(),
            "capabilities": {
                "research_import": True,
                "paper_positions": True,
                "live_orders": False,
                "supported_execution_markets": [],
                "research_only_markets": ["crypto", "metals", "forex", "futures", "equities"],
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
