"""Persistent social/trading core ported from AI-Trader for Vibe-Trading.

This intentionally keeps the AI-Trader domain model (agents, signals,
positions, follows and points) while using Vibe's runtime directory and auth.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from src.api.paper_trading_routes import _native_strategies, _paper_account
from src.config.paths import get_runtime_root

INITIAL_CAPITAL = 100_000.0
POINTS_TO_CASH_RATE = 100
_lock = threading.RLock()
_initialized = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path():
    path = get_runtime_root() / "community" / "ai-trader.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    global _initialized
    connection = sqlite3.connect(_db_path(), timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    with _lock:
        if not _initialized:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '', points INTEGER NOT NULL DEFAULT 1000,
                    cash REAL NOT NULL DEFAULT 100000, deposited REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, last_active_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, external_key TEXT UNIQUE,
                    agent_id INTEGER NOT NULL, message_type TEXT NOT NULL,
                    market TEXT NOT NULL DEFAULT 'us-stock', symbol TEXT,
                    symbols_json TEXT NOT NULL DEFAULT '[]', title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '', tags_json TEXT NOT NULL DEFAULT '[]',
                    side TEXT, price REAL, quantity REAL, executed_at TEXT,
                    parent_id INTEGER, reply_count INTEGER NOT NULL DEFAULT 0,
                    accepted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id INTEGER NOT NULL,
                    market TEXT NOT NULL, symbol TEXT NOT NULL, quantity REAL NOT NULL,
                    avg_price REAL NOT NULL, current_price REAL NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
                    UNIQUE(agent_id, market, symbol)
                );
                CREATE TABLE IF NOT EXISTS follows (
                    follower_id INTEGER NOT NULL, leader_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL, PRIMARY KEY(follower_id, leader_id)
                );
                CREATE TABLE IF NOT EXISTS points_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL, event_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_key TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', market TEXT NOT NULL,
                    symbol TEXT, starting_capital REAL NOT NULL DEFAULT 100000,
                    starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS challenge_participants (
                    challenge_id INTEGER NOT NULL, agent_id INTEGER NOT NULL, cash REAL NOT NULL,
                    joined_at TEXT NOT NULL, PRIMARY KEY(challenge_id,agent_id)
                );
                CREATE TABLE IF NOT EXISTS challenge_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id INTEGER NOT NULL,
                    agent_id INTEGER NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
                    price REAL NOT NULL, quantity REAL NOT NULL, content TEXT NOT NULL DEFAULT '',
                    team_id INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS challenge_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id INTEGER NOT NULL,
                    agent_id INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                    votes INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profit_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id INTEGER NOT NULL,
                    profit REAL NOT NULL, equity REAL NOT NULL, recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS challenge_teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, challenge_id INTEGER NOT NULL,
                    team_key TEXT NOT NULL, name TEXT NOT NULL, cash REAL NOT NULL,
                    created_at TEXT NOT NULL, UNIQUE(challenge_id,team_key)
                );
                CREATE TABLE IF NOT EXISTS challenge_team_members (
                    team_id INTEGER NOT NULL, agent_id INTEGER NOT NULL, joined_at TEXT NOT NULL,
                    PRIMARY KEY(team_id,agent_id)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id INTEGER NOT NULL,
                    category TEXT NOT NULL, content TEXT NOT NULL, data_json TEXT NOT NULL DEFAULT '{}',
                    read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
            """)
            # Keep persistent databases forward-compatible when a later deploy
            # adds fields to an already-created AI-Trader table.
            signal_columns = {row["name"] for row in connection.execute("PRAGMA table_info(signals)")}
            if "accepted" not in signal_columns:
                connection.execute("ALTER TABLE signals ADD COLUMN accepted INTEGER NOT NULL DEFAULT 0")
            trade_columns = {row["name"] for row in connection.execute("PRAGMA table_info(challenge_trades)")}
            if "team_id" not in trade_columns:
                connection.execute("ALTER TABLE challenge_trades ADD COLUMN team_id INTEGER")
            now = utc_now()
            connection.execute("INSERT OR IGNORE INTO agents(name,description,created_at,last_active_at) VALUES(?,?,?,?)", ("Vibe Research", "Native Vibe-Trading research agent", now, now))
            connection.commit()
            _initialized = True
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def local_agent(connection: sqlite3.Connection | None = None) -> dict[str, Any]:
    if connection is None:
        with db() as owned:
            return dict(owned.execute("SELECT * FROM agents WHERE name='Vibe Research'").fetchone())
    return dict(connection.execute("SELECT * FROM agents WHERE name='Vibe Research'").fetchone())


def _market_for(symbol: str) -> str:
    value = symbol.upper().replace("/", "").replace("-", "")
    if any(token in value for token in ("BTC", "ETH", "SOL", "XRP")): return "crypto"
    if any(token in value for token in ("XAU", "GOLD", "XAG")): return "metals"
    if any(token in value for token in ("USOIL", "WTI", "BRENT")): return "energy"
    if len(value) == 6 and value[-3:] in {"USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF"}: return "forex"
    if value.startswith("POLYMARKET"): return "prediction"
    return "us-stock"


def sync_native() -> None:
    with db() as connection:
        agent = local_agent(connection)
        for strategy in _native_strategies(200):
            symbols = strategy.get("symbols") or []
            symbol = str(symbols[0]) if symbols else ""
            research_name = f"{symbol} Research" if symbol else "Vibe Research"
            if research_name != agent["name"]:
                now = strategy.get("created_at") or utc_now()
                connection.execute("INSERT OR IGNORE INTO agents(name,description,created_at,last_active_at) VALUES(?,?,?,?)", (research_name, f"Imported Vibe research for {symbol}", now, now))
                strategy_agent_id = connection.execute("SELECT id FROM agents WHERE name=?", (research_name,)).fetchone()[0]
            else:
                strategy_agent_id = agent["id"]
            connection.execute("""
                INSERT OR IGNORE INTO signals(external_key,agent_id,message_type,market,symbol,symbols_json,title,content,tags_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
            """, (f"run:{strategy['signal_id']}", strategy_agent_id, "strategy", _market_for(symbol), symbol, json.dumps(symbols), strategy.get("title", ""), strategy.get("content", ""), json.dumps(strategy.get("tags") or []), strategy.get("created_at") or utc_now()))
        account = _paper_account()
        for item in account.get("positions", []):
            symbol = str(item.get("symbol") or "").upper()
            if not symbol: continue
            connection.execute("""
                INSERT INTO positions(agent_id,market,symbol,quantity,avg_price,current_price,realized_pnl,updated_at)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(agent_id,market,symbol) DO UPDATE SET
                quantity=excluded.quantity,avg_price=excluded.avg_price,current_price=excluded.current_price,updated_at=excluded.updated_at
            """, (agent["id"], str(item.get("market") or _market_for(symbol)), symbol, float(item.get("quantity") or 0), float(item.get("entry_price") or item.get("avg_price") or 0), float(item.get("current_price") or item.get("entry_price") or 0), float(item.get("realized_pnl") or 0), utc_now()))


def _signal_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["symbols"] = json.loads(item.pop("symbols_json") or "[]")
    item["tags"] = json.loads(item.pop("tags_json") or "[]")
    item["agent_name"] = item.pop("name", "Vibe Research")
    return item


def list_signals(message_type: str | None = None, market: str = "all", limit: int = 20, offset: int = 0, sort: str = "new") -> dict[str, Any]:
    sync_native()
    clauses, params = [], []
    if message_type:
        clauses.append("s.message_type=?"); params.append(message_type)
    if market and market != "all":
        clauses.append("s.market=?"); params.append(market)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "s.reply_count DESC, s.created_at DESC" if sort == "active" else "s.created_at DESC"
    with db() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM signals s {where}", params).fetchone()[0]
        rows = connection.execute(f"SELECT s.*,a.name FROM signals s JOIN agents a ON a.id=s.agent_id {where} ORDER BY {order} LIMIT ? OFFSET ?", (*params, max(1, min(limit, 100)), max(0, offset))).fetchall()
    return {"signals": [_signal_row(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def create_signal(payload: dict[str, Any], message_type: str) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    if not content or (message_type != "operation" and not title):
        raise ValueError("title and content are required")
    symbols = payload.get("symbols") or ([payload.get("symbol")] if payload.get("symbol") else [])
    if isinstance(symbols, str): symbols = [part.strip().upper() for part in symbols.split(",") if part.strip()]
    tags = payload.get("tags") or []
    if isinstance(tags, str): tags = [part.strip() for part in tags.split(",") if part.strip()]
    with db() as connection:
        agent = local_agent(connection)
        cursor = connection.execute("""
            INSERT INTO signals(agent_id,message_type,market,symbol,symbols_json,title,content,tags_json,side,price,quantity,executed_at,parent_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (agent["id"], message_type, str(payload.get("market") or (_market_for(str(symbols[0])) if symbols else "us-stock")), str(symbols[0]) if symbols else None, json.dumps(symbols), title, content, json.dumps(tags), payload.get("side"), payload.get("price"), payload.get("quantity"), payload.get("executed_at"), payload.get("parent_id"), utc_now()))
        signal_id = cursor.lastrowid
        if payload.get("parent_id"):
            connection.execute("UPDATE signals SET reply_count=reply_count+1 WHERE id=?", (payload["parent_id"],))
        connection.execute("UPDATE agents SET points=points+?,last_active_at=? WHERE id=?", (10 if message_type == "strategy" else 5, utc_now(), agent["id"]))
        followers = connection.execute("SELECT follower_id FROM follows WHERE leader_id=?", (agent["id"],)).fetchall()
        for follower in followers:
            connection.execute("INSERT INTO messages(agent_id,category,content,data_json,created_at) VALUES(?,?,?,?,?)", (follower["follower_id"], message_type, f"{agent['name']} posted {message_type}", json.dumps({"signal_id": signal_id, "title": title}), utc_now()))
        row = connection.execute("SELECT s.*,a.name FROM signals s JOIN agents a ON a.id=s.agent_id WHERE s.id=?", (signal_id,)).fetchone()
    return _signal_row(row)


def positions(agent_id: int | None = None) -> list[dict[str, Any]]:
    sync_native()
    with db() as connection:
        aid = agent_id or local_agent(connection)["id"]
        rows = connection.execute("SELECT p.*,a.name agent_name FROM positions p JOIN agents a ON a.id=p.agent_id WHERE p.agent_id=? AND ABS(p.quantity)>0.00000001 ORDER BY p.updated_at DESC", (aid,)).fetchall()
    return [{**dict(row), "unrealized_pnl": round((row["current_price"] - row["avg_price"]) * row["quantity"], 2), "side": "long" if row["quantity"] >= 0 else "short"} for row in rows]


def execute_trade(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload.get("symbol") or "").strip().upper()
    side = str(payload.get("side") or "buy").lower()
    price = float(payload.get("price") or 0)
    quantity = float(payload.get("quantity") or 0)
    if not symbol or price <= 0 or quantity <= 0 or side not in {"buy", "sell"}:
        raise ValueError("valid symbol, side, price and quantity are required")
    signed = quantity if side == "buy" else -quantity
    market = str(payload.get("market") or _market_for(symbol))
    fee = abs(price * quantity) * 0.001
    with db() as connection:
        agent = local_agent(connection)
        existing = connection.execute("SELECT * FROM positions WHERE agent_id=? AND market=? AND symbol=?", (agent["id"], market, symbol)).fetchone()
        old_qty = float(existing["quantity"]) if existing else 0
        old_avg = float(existing["avg_price"]) if existing else price
        new_qty = old_qty + signed
        cash_delta = -(signed * price) - fee
        if float(agent["cash"]) + cash_delta < 0:
            raise ValueError("insufficient cash")
        if old_qty and old_qty * signed > 0: new_avg = (abs(old_qty) * old_avg + abs(signed) * price) / (abs(old_qty) + abs(signed))
        elif old_qty * new_qty <= 0: new_avg = price
        else: new_avg = old_avg
        connection.execute("UPDATE agents SET cash=cash+?,last_active_at=? WHERE id=?", (cash_delta, utc_now(), agent["id"]))
        connection.execute("""INSERT INTO positions(agent_id,market,symbol,quantity,avg_price,current_price,updated_at) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(agent_id,market,symbol) DO UPDATE SET quantity=excluded.quantity,avg_price=excluded.avg_price,current_price=excluded.current_price,updated_at=excluded.updated_at""", (agent["id"], market, symbol, new_qty, new_avg, price, utc_now()))
        unrealized = connection.execute("SELECT COALESCE(SUM((current_price-avg_price)*quantity),0) FROM positions WHERE agent_id=?", (agent["id"],)).fetchone()[0]
        updated_cash = float(agent["cash"]) + cash_delta
        connection.execute("INSERT INTO profit_history(agent_id,profit,equity,recorded_at) VALUES(?,?,?,?)", (agent["id"], unrealized, updated_cash + unrealized, utc_now()))
    signal = create_signal({**payload, "title": f"{side.upper()} {symbol}", "content": str(payload.get("content") or f"{side.upper()} {quantity:g} {symbol} @ {price:g}"), "symbols": [symbol], "market": market, "executed_at": utc_now()}, "operation")
    return {"success": True, "signal": signal, "position": next((item for item in positions() if item["symbol"] == symbol and item["market"] == market), None), "fee": round(fee, 2)}


def leaderboard(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    sync_native()
    with db() as connection:
        rows = connection.execute("""SELECT a.*,
            COALESCE(SUM((p.current_price-p.avg_price)*p.quantity),0) unrealized_pnl,
            COUNT(DISTINCT CASE WHEN s.message_type='operation' THEN s.id END) trade_count,
            COUNT(DISTINCT CASE WHEN s.message_type='strategy' THEN s.id END) strategy_count,
            COUNT(DISTINCT CASE WHEN s.message_type='discussion' THEN s.id END) discussion_count,
            COUNT(DISTINCT f.follower_id) follower_count
            FROM agents a LEFT JOIN positions p ON p.agent_id=a.id LEFT JOIN signals s ON s.agent_id=a.id LEFT JOIN follows f ON f.leader_id=a.id
            GROUP BY a.id ORDER BY unrealized_pnl DESC LIMIT ? OFFSET ?""", (max(1, min(limit, 100)), max(0, offset))).fetchall()
        total = connection.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    items = []
    for row in rows:
        item = dict(row); profit = float(item.pop("unrealized_pnl") or 0)
        item.update({"agent_id": item["id"], "total_profit": round(profit, 2), "total_profit_percent": round(profit / (INITIAL_CAPITAL + float(item["deposited"] or 0)) * 100, 2), "equity": round(float(item["cash"]) + profit, 2), "recent_trade_count_7d": item["trade_count"], "recent_strategy_count_7d": item["strategy_count"], "recent_discussion_count_7d": item["discussion_count"], "recent_activity_at": item["last_active_at"]})
        items.append(item)
    return {"top_agents": items, "leaderboard": items, "total": total, "limit": limit, "offset": offset}


def leaderboard_history(limit: int = 20, offset: int = 0, include_history: bool = True, days: int = 30) -> dict[str, Any]:
    payload = leaderboard(limit, offset)
    if not include_history:
        return payload
    with db() as connection:
        for agent in payload["top_agents"]:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()
            rows = connection.execute("SELECT profit,equity,recorded_at FROM profit_history WHERE agent_id=? AND recorded_at>=? ORDER BY recorded_at ASC LIMIT 2000", (agent["agent_id"], cutoff)).fetchall()
            peak = INITIAL_CAPITAL + float(agent.get("deposited") or 0)
            maximum_drawdown = 0.0
            history = []
            for row in rows:
                peak = max(peak, float(row["equity"]))
                maximum_drawdown = max(maximum_drawdown, (peak - float(row["equity"])) / peak * 100 if peak else 0)
                history.append({"profit": row["profit"], "profit_percent": float(row["profit"]) / INITIAL_CAPITAL * 100, "max_drawdown": round(maximum_drawdown, 2), "recorded_at": row["recorded_at"]})
            history.append({"profit": agent["total_profit"], "profit_percent": agent["total_profit_percent"], "max_drawdown": round(maximum_drawdown, 2), "recorded_at": utc_now()})
            agent["history"] = history
            agent["profit"] = agent["total_profit"]
            agent["profit_percent"] = agent["total_profit_percent"]
            agent["max_drawdown"] = round(maximum_drawdown, 2)
    return payload


def follow(leader_id: int, enabled: bool) -> dict[str, Any]:
    with db() as connection:
        follower = local_agent(connection)
        if leader_id == follower["id"]: raise ValueError("cannot follow yourself")
        if not connection.execute("SELECT 1 FROM agents WHERE id=?", (leader_id,)).fetchone(): raise ValueError("leader not found")
        if enabled: connection.execute("INSERT OR IGNORE INTO follows VALUES(?,?,?)", (follower["id"], leader_id, utc_now()))
        else: connection.execute("DELETE FROM follows WHERE follower_id=? AND leader_id=?", (follower["id"], leader_id))
    return {"success": True, "leader_id": leader_id, "following": enabled}


def following(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    with db() as connection:
        follower = local_agent(connection)
        total = connection.execute("SELECT COUNT(*) FROM follows WHERE follower_id=?", (follower["id"],)).fetchone()[0]
        rows = connection.execute("SELECT f.leader_id,f.created_at subscribed_at,a.name leader_name,a.last_active_at recent_activity_at FROM follows f JOIN agents a ON a.id=f.leader_id WHERE f.follower_id=? ORDER BY f.created_at DESC LIMIT ? OFFSET ?", (follower["id"], limit, offset)).fetchall()
    return {"following": [dict(row) for row in rows], "total": total}


def subscribers() -> dict[str, Any]:
    with db() as connection:
        leader = local_agent(connection)
        rows = connection.execute("SELECT f.follower_id,f.created_at subscribed_at,a.name follower_name FROM follows f JOIN agents a ON a.id=f.follower_id WHERE f.leader_id=? ORDER BY f.created_at DESC", (leader["id"],)).fetchall()
    return {"subscribers": [dict(row) for row in rows], "total": len(rows)}


def accept_reply(signal_id: int, reply_id: int) -> dict[str, Any]:
    with db() as connection:
        parent = connection.execute("SELECT * FROM signals WHERE id=?", (signal_id,)).fetchone()
        reply = connection.execute("SELECT * FROM signals WHERE id=? AND parent_id=?", (reply_id, signal_id)).fetchone()
        if not parent or not reply: raise ValueError("reply not found")
        connection.execute("UPDATE signals SET accepted=1 WHERE id=?", (reply_id,))
        connection.execute("UPDATE agents SET points=points+20 WHERE id=?", (reply["agent_id"],))
        connection.execute("INSERT INTO points_history(agent_id,amount,event_type,description,created_at) VALUES(?,?,?,?,?)", (reply["agent_id"], 20, "accepted_reply", f"Reply {reply_id} accepted", utc_now()))
    return {"success": True, "signal_id": signal_id, "reply_id": reply_id}


def recent_messages(category: str | None = None, limit: int = 20) -> dict[str, Any]:
    with db() as connection:
        agent = local_agent(connection)
        if category:
            rows = connection.execute("SELECT * FROM messages WHERE agent_id=? AND category=? ORDER BY created_at DESC LIMIT ?", (agent["id"], category, limit)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM messages WHERE agent_id=? ORDER BY created_at DESC LIMIT ?", (agent["id"], limit)).fetchall()
    return {"messages": [{**dict(row), "data": json.loads(row["data_json"] or "{}"), "read": bool(row["read"])} for row in rows], "total": len(rows)}


def unread_summary() -> dict[str, Any]:
    with db() as connection:
        agent = local_agent(connection)
        rows = connection.execute("SELECT category,COUNT(*) count FROM messages WHERE agent_id=? AND read=0 GROUP BY category", (agent["id"],)).fetchall()
    counts = {row["category"]: row["count"] for row in rows}
    return {"counts": counts, "total": sum(counts.values())}


def mark_messages_read(category: str | None = None) -> dict[str, Any]:
    with db() as connection:
        agent = local_agent(connection)
        if category: cursor = connection.execute("UPDATE messages SET read=1 WHERE agent_id=? AND category=?", (agent["id"], category))
        else: cursor = connection.execute("UPDATE messages SET read=1 WHERE agent_id=?", (agent["id"],))
    return {"success": True, "updated": cursor.rowcount}


def account() -> dict[str, Any]:
    with db() as connection:
        agent = local_agent(connection)
    profit = sum(item["unrealized_pnl"] for item in positions(agent["id"]))
    return {**agent, "agent_id": agent["id"], "unrealized_pnl": round(profit, 2), "equity": round(float(agent["cash"]) + profit, 2), "exchange_rate": POINTS_TO_CASH_RATE}


def exchange_points(amount: int) -> dict[str, Any]:
    if amount <= 0 or amount % POINTS_TO_CASH_RATE:
        raise ValueError(f"amount must be a positive multiple of {POINTS_TO_CASH_RATE}")
    cash = amount / POINTS_TO_CASH_RATE
    with db() as connection:
        agent = local_agent(connection)
        if int(agent["points"]) < amount: raise ValueError("insufficient points")
        connection.execute("UPDATE agents SET points=points-?,cash=cash+? WHERE id=?", (amount, cash, agent["id"]))
        connection.execute("INSERT INTO points_history(agent_id,amount,event_type,description,created_at) VALUES(?,?,?,?,?)", (agent["id"], -amount, "exchange", f"Exchanged {amount} points for ${cash:.2f}", utc_now()))
    return {"success": True, "points_spent": amount, "cash_received": cash, "account": account()}


def points_history(limit: int = 50) -> dict[str, Any]:
    with db() as connection:
        agent = local_agent(connection)
        rows = connection.execute("SELECT * FROM points_history WHERE agent_id=? ORDER BY created_at DESC LIMIT ?", (agent["id"], max(1, min(limit, 200)))).fetchall()
    return {"history": [dict(row) for row in rows], "total": len(rows)}


def transfer_points(recipient_id: int, amount: int) -> dict[str, Any]:
    if amount <= 0: raise ValueError("amount must be positive")
    with db() as connection:
        sender = local_agent(connection)
        recipient = connection.execute("SELECT * FROM agents WHERE id=?", (recipient_id,)).fetchone()
        if not recipient: raise ValueError("recipient not found")
        if recipient_id == sender["id"]: raise ValueError("cannot transfer points to yourself")
        if int(sender["points"]) < amount: raise ValueError("insufficient points")
        now = utc_now()
        connection.execute("UPDATE agents SET points=points-? WHERE id=?", (amount, sender["id"]))
        connection.execute("UPDATE agents SET points=points+? WHERE id=?", (amount, recipient_id))
        connection.execute("INSERT INTO points_history(agent_id,amount,event_type,description,created_at) VALUES(?,?,?,?,?)", (sender["id"], -amount, "transfer_out", f"Transferred to {recipient['name']}", now))
        connection.execute("INSERT INTO points_history(agent_id,amount,event_type,description,created_at) VALUES(?,?,?,?,?)", (recipient_id, amount, "transfer_in", f"Received from {sender['name']}", now))
    return {"success": True, "recipient_id": recipient_id, "amount": amount, "account": account()}


def _challenge_row(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["participant_count"] = connection.execute("SELECT COUNT(*) FROM challenge_participants WHERE challenge_id=?", (item["id"],)).fetchone()[0]
    return item


def challenges(market: str = "all", status: str | None = None) -> dict[str, Any]:
    clauses, params = [], []
    if market != "all": clauses.append("market=?"); params.append(market)
    if status: clauses.append("status=?"); params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db() as connection:
        rows = connection.execute(f"SELECT * FROM challenges {where} ORDER BY created_at DESC", params).fetchall()
        items = [_challenge_row(connection, row) for row in rows]
    return {"challenges": items, "total": len(items)}


def create_challenge(payload: dict[str, Any]) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    market = str(payload.get("market") or "crypto").strip()
    if not title: raise ValueError("title is required")
    key = str(payload.get("challenge_key") or "-".join(title.lower().split()))[:80]
    now = utc_now()
    starts = str(payload.get("starts_at") or now)
    ends = str(payload.get("ends_at") or "2099-12-31T23:59:59+00:00")
    with db() as connection:
        cursor = connection.execute("INSERT INTO challenges(challenge_key,title,description,market,symbol,starting_capital,starts_at,ends_at,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (key, title, str(payload.get("description") or ""), market, str(payload.get("symbol") or "").upper() or None, float(payload.get("starting_capital") or INITIAL_CAPITAL), starts, ends, "active", now))
        row = connection.execute("SELECT * FROM challenges WHERE id=?", (cursor.lastrowid,)).fetchone()
        return _challenge_row(connection, row)


def challenge_detail(key: str) -> dict[str, Any]:
    with db() as connection:
        row = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not row: raise ValueError("challenge not found")
        item = _challenge_row(connection, row)
        participants = connection.execute("SELECT cp.*,a.name FROM challenge_participants cp JOIN agents a ON a.id=cp.agent_id WHERE cp.challenge_id=?", (row["id"],)).fetchall()
        item["participants"] = [dict(value) for value in participants]
        return item


def join_challenge(key: str) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge: raise ValueError("challenge not found")
        if challenge["status"] != "active": raise ValueError("challenge is not active")
        agent = local_agent(connection)
        connection.execute("INSERT OR IGNORE INTO challenge_participants(challenge_id,agent_id,cash,joined_at) VALUES(?,?,?,?)", (challenge["id"], agent["id"], challenge["starting_capital"], utc_now()))
    return {"success": True, "challenge": challenge_detail(key)}


def challenge_portfolio(key: str) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge: raise ValueError("challenge not found")
        agent = local_agent(connection)
        participant = connection.execute("SELECT * FROM challenge_participants WHERE challenge_id=? AND agent_id=?", (challenge["id"], agent["id"])).fetchone()
        if not participant: raise ValueError("join the challenge first")
        trades = [dict(row) for row in connection.execute("SELECT * FROM challenge_trades WHERE challenge_id=? AND agent_id=? ORDER BY created_at", (challenge["id"], agent["id"])).fetchall()]
    grouped: dict[str, dict[str, float]] = {}
    for trade in trades:
        row = grouped.setdefault(trade["symbol"], {"quantity": 0.0, "cost": 0.0, "current_price": trade["price"]})
        signed = trade["quantity"] if trade["side"] == "buy" else -trade["quantity"]
        row["quantity"] += signed; row["cost"] += signed * trade["price"]; row["current_price"] = trade["price"]
    positions_list = [{"symbol": symbol, "quantity": value["quantity"], "avg_price": abs(value["cost"] / value["quantity"]) if value["quantity"] else 0, "current_price": value["current_price"], "unrealized_pnl": 0} for symbol, value in grouped.items() if value["quantity"]]
    equity = float(participant["cash"]) + sum(item["quantity"] * item["current_price"] for item in positions_list)
    return {"challenge": dict(challenge), "cash": participant["cash"], "equity": round(equity, 2), "return_percent": round((equity / challenge["starting_capital"] - 1) * 100, 2), "positions": positions_list, "trades": trades, "trade_count": len(trades)}


def challenge_trade(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    symbol, side = str(payload.get("symbol") or "").upper(), str(payload.get("side") or "buy").lower()
    price, quantity = float(payload.get("price") or 0), float(payload.get("quantity") or 0)
    if not symbol or side not in {"buy", "sell"} or price <= 0 or quantity <= 0: raise ValueError("valid symbol, side, price and quantity are required")
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge or challenge["status"] != "active": raise ValueError("active challenge not found")
        if challenge["symbol"] and challenge["symbol"] != symbol: raise ValueError(f"symbol is locked to {challenge['symbol']}")
        agent = local_agent(connection)
        participant = connection.execute("SELECT * FROM challenge_participants WHERE challenge_id=? AND agent_id=?", (challenge["id"], agent["id"])).fetchone()
        if not participant: raise ValueError("join the challenge first")
        delta = -price * quantity if side == "buy" else price * quantity
        if float(participant["cash"]) + delta < 0: raise ValueError("insufficient challenge cash")
        connection.execute("UPDATE challenge_participants SET cash=cash+? WHERE challenge_id=? AND agent_id=?", (delta, challenge["id"], agent["id"]))
        connection.execute("INSERT INTO challenge_trades(challenge_id,agent_id,symbol,side,price,quantity,content,created_at) VALUES(?,?,?,?,?,?,?,?)", (challenge["id"], agent["id"], symbol, side, price, quantity, str(payload.get("content") or ""), utc_now()))
    return challenge_portfolio(key)


def challenge_leaderboard(key: str) -> dict[str, Any]:
    detail = challenge_detail(key)
    rows = []
    with db() as connection:
        for participant in detail["participants"]:
            count = connection.execute("SELECT COUNT(*) FROM challenge_trades WHERE challenge_id=? AND agent_id=?", (detail["id"], participant["agent_id"])).fetchone()[0]
            # Last trade marks are enough to preserve deterministic portfolio scoring.
            trades = connection.execute("SELECT * FROM challenge_trades WHERE challenge_id=? AND agent_id=?", (detail["id"], participant["agent_id"])).fetchall()
            holdings: dict[str, float] = {}; marks: dict[str, float] = {}
            for trade in trades:
                holdings[trade["symbol"]] = holdings.get(trade["symbol"], 0) + (trade["quantity"] if trade["side"] == "buy" else -trade["quantity"]); marks[trade["symbol"]] = trade["price"]
            equity = participant["cash"] + sum(qty * marks[symbol] for symbol, qty in holdings.items())
            rows.append({"agent_id": participant["agent_id"], "name": participant["name"], "equity": round(equity, 2), "return_percent": round((equity / detail["starting_capital"] - 1) * 100, 2), "trade_count": count})
    rows.sort(key=lambda item: item["return_percent"], reverse=True)
    for index, row in enumerate(rows): row["rank"] = index + 1
    return {"leaderboard": rows, "total": len(rows), "challenge": detail}


def challenge_submission(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge: raise ValueError("challenge not found")
        agent = local_agent(connection)
        cursor = connection.execute("INSERT INTO challenge_submissions(challenge_id,agent_id,title,content,created_at) VALUES(?,?,?,?,?)", (challenge["id"], agent["id"], str(payload.get("title") or "Submission"), str(payload.get("content") or ""), utc_now()))
        return dict(connection.execute("SELECT * FROM challenge_submissions WHERE id=?", (cursor.lastrowid,)).fetchone())


def challenge_submissions(key: str) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge: raise ValueError("challenge not found")
        rows = connection.execute("SELECT s.*,a.name agent_name FROM challenge_submissions s JOIN agents a ON a.id=s.agent_id WHERE challenge_id=? ORDER BY votes DESC,created_at DESC", (challenge["id"],)).fetchall()
    return {"submissions": [dict(row) for row in rows], "total": len(rows)}


def vote_submission(key: str, submission_id: int) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT id FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge: raise ValueError("challenge not found")
        cursor = connection.execute("UPDATE challenge_submissions SET votes=votes+1 WHERE id=? AND challenge_id=?", (submission_id, challenge["id"]))
        if not cursor.rowcount: raise ValueError("submission not found")
    return {"success": True, "submission_id": submission_id}


def update_challenge_status(key: str, status: str) -> dict[str, Any]:
    with db() as connection:
        cursor = connection.execute("UPDATE challenges SET status=? WHERE challenge_key=?", (status, key))
        if not cursor.rowcount: raise ValueError("challenge not found")
    return challenge_detail(key)


def challenge_teams(key: str) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT id FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge: raise ValueError("challenge not found")
        rows = connection.execute("SELECT t.*,COUNT(m.agent_id) member_count FROM challenge_teams t LEFT JOIN challenge_team_members m ON m.team_id=t.id WHERE t.challenge_id=? GROUP BY t.id ORDER BY t.created_at", (challenge["id"],)).fetchall()
    return {"teams": [dict(row) for row in rows], "total": len(rows)}


def create_challenge_team(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or payload.get("title") or "").strip()
    if not name: raise ValueError("team name is required")
    team_key = str(payload.get("team_key") or "-".join(name.lower().split()))[:80]
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        if not challenge: raise ValueError("challenge not found")
        agent = local_agent(connection)
        cursor = connection.execute("INSERT INTO challenge_teams(challenge_id,team_key,name,cash,created_at) VALUES(?,?,?,?,?)", (challenge["id"], team_key, name, challenge["starting_capital"], utc_now()))
        connection.execute("INSERT INTO challenge_team_members(team_id,agent_id,joined_at) VALUES(?,?,?)", (cursor.lastrowid, agent["id"], utc_now()))
        row = connection.execute("SELECT * FROM challenge_teams WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def join_challenge_team(key: str, team_id: int) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT id FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        team = connection.execute("SELECT * FROM challenge_teams WHERE id=? AND challenge_id=?", (team_id, challenge["id"] if challenge else -1)).fetchone()
        if not challenge or not team: raise ValueError("team not found")
        agent = local_agent(connection)
        connection.execute("INSERT OR IGNORE INTO challenge_team_members(team_id,agent_id,joined_at) VALUES(?,?,?)", (team_id, agent["id"], utc_now()))
    return {"success": True, "team": dict(team)}


def team_challenge_portfolio(key: str, team_id: int) -> dict[str, Any]:
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        team = connection.execute("SELECT * FROM challenge_teams WHERE id=? AND challenge_id=?", (team_id, challenge["id"] if challenge else -1)).fetchone()
        if not challenge or not team: raise ValueError("team not found")
        trades = [dict(row) for row in connection.execute("SELECT * FROM challenge_trades WHERE challenge_id=? AND team_id=? ORDER BY created_at", (challenge["id"], team_id)).fetchall()]
    holdings: dict[str, float] = {}; marks: dict[str, float] = {}; costs: dict[str, float] = {}
    for trade in trades:
        signed = trade["quantity"] if trade["side"] == "buy" else -trade["quantity"]
        holdings[trade["symbol"]] = holdings.get(trade["symbol"], 0) + signed; costs[trade["symbol"]] = costs.get(trade["symbol"], 0) + signed * trade["price"]; marks[trade["symbol"]] = trade["price"]
    positions_list = [{"symbol": symbol, "quantity": quantity, "avg_price": abs(costs[symbol] / quantity) if quantity else 0, "current_price": marks[symbol], "unrealized_pnl": 0} for symbol, quantity in holdings.items() if quantity]
    equity = float(team["cash"]) + sum(item["quantity"] * item["current_price"] for item in positions_list)
    return {"challenge": dict(challenge), "team": dict(team), "cash": team["cash"], "equity": round(equity, 2), "return_percent": round((equity / challenge["starting_capital"] - 1) * 100, 2), "positions": positions_list, "trades": trades, "trade_count": len(trades)}


def team_challenge_trade(key: str, team_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    symbol, side = str(payload.get("symbol") or "").upper(), str(payload.get("side") or "buy").lower()
    price, quantity = float(payload.get("price") or 0), float(payload.get("quantity") or 0)
    if not symbol or side not in {"buy", "sell"} or price <= 0 or quantity <= 0: raise ValueError("valid symbol, side, price and quantity are required")
    with db() as connection:
        challenge = connection.execute("SELECT * FROM challenges WHERE challenge_key=?", (key,)).fetchone()
        team = connection.execute("SELECT * FROM challenge_teams WHERE id=? AND challenge_id=?", (team_id, challenge["id"] if challenge else -1)).fetchone()
        agent = local_agent(connection)
        member = connection.execute("SELECT 1 FROM challenge_team_members WHERE team_id=? AND agent_id=?", (team_id, agent["id"])).fetchone()
        if not challenge or not team or not member: raise ValueError("team membership required")
        if challenge["symbol"] and challenge["symbol"] != symbol: raise ValueError(f"symbol is locked to {challenge['symbol']}")
        delta = -price * quantity if side == "buy" else price * quantity
        if float(team["cash"]) + delta < 0: raise ValueError("insufficient team cash")
        connection.execute("UPDATE challenge_teams SET cash=cash+? WHERE id=?", (delta, team_id))
        connection.execute("INSERT INTO challenge_trades(challenge_id,agent_id,symbol,side,price,quantity,content,team_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (challenge["id"], agent["id"], symbol, side, price, quantity, str(payload.get("content") or ""), team_id, utc_now()))
    return team_challenge_portfolio(key, team_id)


def team_challenge_leaderboard(key: str) -> dict[str, Any]:
    rows = []
    for team in challenge_teams(key)["teams"]:
        portfolio = team_challenge_portfolio(key, team["id"])
        rows.append({"team_id": team["id"], "team_key": team["team_key"], "name": team["name"], "member_count": team["member_count"], "equity": portfolio["equity"], "return_percent": portfolio["return_percent"], "trade_count": portfolio["trade_count"]})
    rows.sort(key=lambda item: item["return_percent"], reverse=True)
    for index, row in enumerate(rows): row["rank"] = index + 1
    return {"leaderboard": rows, "total": len(rows)}
