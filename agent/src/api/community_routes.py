"""AI-Trader compatible community and simulated-trading API routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query

from src.api.community_core import (
    account,
    accept_reply,
    challenge_detail,
    challenge_leaderboard,
    challenge_portfolio,
    challenge_submission,
    challenge_submissions,
    challenge_trade,
    challenge_teams,
    challenges,
    create_challenge,
    create_challenge_team,
    create_signal,
    exchange_points,
    execute_trade,
    follow,
    following,
    leaderboard,
    leaderboard_history,
    list_signals,
    local_agent,
    mark_messages_read,
    positions,
    points_history,
    recent_messages,
    join_challenge,
    join_challenge_team,
    update_challenge_status,
    transfer_points,
    subscribers,
    unread_summary,
    vote_submission,
    team_challenge_leaderboard,
    team_challenge_portfolio,
    team_challenge_trade,
)
from src.api.security import require_auth
from src.api.market_intel_core import _series


def _error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def register_community_routes(app: FastAPI) -> None:
    auth = [Depends(require_auth)]

    @app.get("/api/claw/agents/me", dependencies=auth)
    async def agent_me(): return account()

    @app.get("/api/claw/agents/me/points", dependencies=auth)
    async def agent_points():
        value = account(); return {"points": value["points"], "cash": value["cash"], "exchange_rate": value["exchange_rate"]}

    @app.get("/api/claw/agents/count", dependencies=auth)
    async def agent_count(): return {"count": leaderboard(1)["total"]}

    @app.get("/api/claw/messages/unread-summary", dependencies=auth)
    async def messages_unread_summary(): return unread_summary()

    @app.get("/api/claw/messages/recent", dependencies=auth)
    async def messages_recent(category: str | None = None, limit: int = 20): return recent_messages(category, limit)

    @app.post("/api/claw/messages/mark-read", dependencies=auth)
    async def messages_mark_read(payload: dict[str, Any]): return mark_messages_read(payload.get("category"))

    @app.get("/api/profit/history", dependencies=auth)
    async def profit_history(limit: int = 10, offset: int = 0, include_history: bool = True, days: int = 30, metric: str = "return"):
        payload = leaderboard_history(limit, offset, include_history, days); payload.update({"days": days, "metric": metric, "include_history": include_history}); return payload

    @app.get("/api/leaderboard/position-pnl", dependencies=auth)
    async def position_pnl(): return {"positions": positions(), "account": account()}

    @app.get("/api/positions", dependencies=auth)
    async def my_positions(): return {"positions": positions(), "account": account()}

    @app.get("/api/agents/{agent_id}/positions", dependencies=auth)
    async def agent_positions(agent_id: int): return {"positions": positions(agent_id)}

    @app.get("/api/agents/{agent_id}/summary", dependencies=auth)
    async def agent_summary(agent_id: int):
        rows = [item for item in leaderboard(100)["top_agents"] if item["agent_id"] == agent_id]
        if not rows: raise HTTPException(status_code=404, detail="agent not found")
        return rows[0]

    @app.get("/api/signals/feed", dependencies=auth)
    async def signals_feed(message_type: str | None = None, market: str = "all", limit: int = 20, offset: int = 0, sort: str = "new"):
        return list_signals(message_type, market, limit, offset, sort)

    @app.get("/api/signals/grouped", dependencies=auth)
    async def signals_grouped(message_type: str = "operation", market: str = "all", limit: int = 20, offset: int = 0):
        signals = list_signals(message_type, market, 500, 0)["signals"]
        by_agent: dict[int, dict[str, Any]] = {}
        for signal in signals:
            agent = by_agent.setdefault(signal["agent_id"], {"agent_id": signal["agent_id"], "agent_name": signal["agent_name"], "signals": [], "signal_count": 0, "position_count": len(positions(signal["agent_id"])), "positions": positions(signal["agent_id"])})
            agent["signals"].append(signal); agent["signal_count"] += 1
        groups = list(by_agent.values())[offset:offset + max(1, min(limit, 100))]
        return {"groups": groups, "agents": groups, "total": len(by_agent), "limit": limit, "offset": offset}

    @app.get("/api/signals/{agent_id:int}", dependencies=auth)
    async def agent_signals(agent_id: int, message_type: str | None = None, limit: int = 50):
        payload = list_signals(message_type, "all", 500, 0)
        rows = [item for item in payload["signals"] if item["agent_id"] == agent_id][:limit]
        return {"signals": rows, "total": len(rows)}

    @app.get("/api/signals/{signal_id}/replies", dependencies=auth)
    async def signal_replies(signal_id: int):
        payload = list_signals(None, "all", 500, 0)
        rows = [item for item in payload["signals"] if item.get("parent_id") == signal_id]
        return {"replies": rows, "total": len(rows)}

    @app.post("/api/signals/strategy", dependencies=auth)
    async def post_strategy(payload: dict[str, Any]):
        try: return {"success": True, "signal": create_signal(payload, "strategy")}
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/signals/discussion", dependencies=auth)
    async def post_discussion(payload: dict[str, Any]):
        try: return {"success": True, "signal": create_signal(payload, "discussion")}
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/signals/reply", dependencies=auth)
    async def post_reply(payload: dict[str, Any]):
        try: return {"success": True, "reply": create_signal(payload, "reply")}
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/signals/{signal_id}/replies/{reply_id}/accept", dependencies=auth)
    async def post_accept_reply(signal_id: int, reply_id: int):
        try: return accept_reply(signal_id, reply_id)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/signals/realtime", dependencies=auth)
    async def realtime_trade(payload: dict[str, Any]):
        try: return execute_trade(payload)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/signals/follow", dependencies=auth)
    async def follow_agent(payload: dict[str, Any]):
        try: return follow(int(payload.get("leader_id") or 0), True)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/signals/unfollow", dependencies=auth)
    async def unfollow_agent(payload: dict[str, Any]):
        try: return follow(int(payload.get("leader_id") or 0), False)
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/signals/following", dependencies=auth)
    async def following_agents(limit: int = 20, offset: int = 0): return following(limit, offset)

    @app.get("/api/signals/subscribers", dependencies=auth)
    async def signal_subscribers(): return subscribers()

    @app.post("/api/agents/points/exchange", dependencies=auth)
    async def points_exchange(payload: dict[str, Any]):
        try: return exchange_points(int(payload.get("amount") or 0))
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/users/points", dependencies=auth)
    async def user_points(): return {"points": account()["points"], "cash": account()["cash"]}

    @app.get("/api/users/me", dependencies=auth)
    async def user_me(): return account()

    @app.get("/api/users/points/history", dependencies=auth)
    async def user_points_history(limit: int = 50): return points_history(limit)

    @app.post("/api/users/points/transfer", dependencies=auth)
    async def user_points_transfer(payload: dict[str, Any]):
        try: return transfer_points(int(payload.get("recipient_id") or 0), int(payload.get("amount") or 0))
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/trending", dependencies=auth)
    async def trending(limit: int = Query(10, ge=1, le=50)):
        rows = positions()
        return {"trending": [{"symbol": row["symbol"], "market": row["market"], "current_price": row["current_price"], "holder_count": 1} for row in rows[:limit]]}

    @app.get("/api/price", dependencies=auth)
    async def market_price(symbol: str, market: str = "us-stock"):
        aliases = {"BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "XAUUSD": "GC=F", "USOIL": "CL=F", "EURUSD": "EURUSD=X"}
        yahoo_symbol = aliases.get(symbol.upper().replace("/", ""), symbol.upper())
        try:
            row = (await asyncio.to_thread(_series, yahoo_symbol))[0]
            return {"symbol": symbol.upper(), "market": market, "price": row["close"], "current_price": row["close"], "as_of": row["date"], "source": "Yahoo Finance"}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"price unavailable: {type(exc).__name__}") from exc

    @app.get("/api/challenges", dependencies=auth)
    async def list_challenges(market: str = "all", status: str | None = None): return challenges(market, status)

    @app.post("/api/challenges", dependencies=auth)
    async def post_challenge(payload: dict[str, Any]):
        try: return create_challenge(payload)
        except (ValueError, Exception) as exc:
            if isinstance(exc, ValueError): raise _error(exc) from exc
            raise HTTPException(status_code=409, detail="challenge key already exists") from exc

    @app.get("/api/challenges/me", dependencies=auth)
    async def my_challenges():
        mine = []
        for challenge in challenges()["challenges"]:
            try:
                portfolio = challenge_portfolio(challenge["challenge_key"])
                mine.append({**challenge, "portfolio": portfolio})
            except ValueError:
                continue
        return {"challenges": mine, "team_challenges": []}

    @app.get("/api/challenges/{challenge_key}/leaderboard", dependencies=auth)
    async def get_challenge_leaderboard(challenge_key: str):
        try: return challenge_leaderboard(challenge_key)
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/challenges/{challenge_key}/team-leaderboard", dependencies=auth)
    async def get_team_challenge_leaderboard(challenge_key: str):
        try: return team_challenge_leaderboard(challenge_key)
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/challenges/{challenge_key}/teams", dependencies=auth)
    async def get_challenge_teams(challenge_key: str):
        try: return challenge_teams(challenge_key)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/teams", dependencies=auth)
    async def post_challenge_team(challenge_key: str, payload: dict[str, Any]):
        try: return create_challenge_team(challenge_key, payload)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/teams/{team_id}/join", dependencies=auth)
    async def post_join_challenge_team(challenge_key: str, team_id: int):
        try: return join_challenge_team(challenge_key, team_id)
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/challenges/{challenge_key}/teams/{team_id}/portfolio", dependencies=auth)
    async def get_team_challenge_portfolio(challenge_key: str, team_id: int):
        try: return team_challenge_portfolio(challenge_key, team_id)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/teams/{team_id}/trade", dependencies=auth)
    async def post_team_challenge_trade(challenge_key: str, team_id: int, payload: dict[str, Any]):
        try: return team_challenge_trade(challenge_key, team_id, payload)
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/challenges/{challenge_key}/teams/{team_id}/submissions", dependencies=auth)
    async def get_team_challenge_submissions(challenge_key: str, team_id: int):
        payload = challenge_submissions(challenge_key); payload["team_id"] = team_id; return payload

    @app.post("/api/challenges/{challenge_key}/teams/{team_id}/submissions", dependencies=auth)
    async def post_team_challenge_submission(challenge_key: str, team_id: int, payload: dict[str, Any]):
        try:
            result = challenge_submission(challenge_key, payload); result["team_id"] = team_id; return result
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/challenges/{challenge_key}/submissions", dependencies=auth)
    async def get_challenge_submissions(challenge_key: str):
        try: return challenge_submissions(challenge_key)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/join", dependencies=auth)
    async def post_join_challenge(challenge_key: str):
        try: return join_challenge(challenge_key)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/submit", dependencies=auth)
    async def post_challenge_submission(challenge_key: str, payload: dict[str, Any]):
        try: return challenge_submission(challenge_key, payload)
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/challenges/{challenge_key}/portfolio", dependencies=auth)
    async def get_challenge_portfolio(challenge_key: str):
        try: return challenge_portfolio(challenge_key)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/trade", dependencies=auth)
    async def post_challenge_trade(challenge_key: str, payload: dict[str, Any]):
        try: return challenge_trade(challenge_key, payload)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/submissions/{submission_id}/vote", dependencies=auth)
    async def post_submission_vote(challenge_key: str, submission_id: int):
        try: return vote_submission(challenge_key, submission_id)
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/settle", dependencies=auth)
    async def settle_challenge(challenge_key: str):
        try: return update_challenge_status(challenge_key, "settled")
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/cancel", dependencies=auth)
    async def cancel_challenge(challenge_key: str):
        try: return update_challenge_status(challenge_key, "cancelled")
        except ValueError as exc: raise _error(exc) from exc

    @app.post("/api/challenges/{challenge_key}/notify", dependencies=auth)
    async def notify_challenge(challenge_key: str):
        try: return {"success": True, "challenge": challenge_detail(challenge_key)}
        except ValueError as exc: raise _error(exc) from exc

    @app.get("/api/challenges/{challenge_key}", dependencies=auth)
    async def get_challenge(challenge_key: str):
        try: return challenge_detail(challenge_key)
        except ValueError as exc: raise _error(exc) from exc
