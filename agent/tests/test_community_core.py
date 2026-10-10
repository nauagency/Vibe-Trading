from pathlib import Path

from src.api import community_core as core


def _isolated(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(core, "get_runtime_root", lambda: tmp_path)
    monkeypatch.setattr(core, "_native_strategies", lambda _limit=100: [])
    monkeypatch.setattr(core, "_paper_account", lambda: {"positions": []})
    core._initialized = False


def test_social_posts_trade_and_leaderboard(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    signal = core.create_signal({"title": "BTC trend", "content": "H4 breakout", "symbols": ["BTCUSD"]}, "strategy")
    assert signal["message_type"] == "strategy"
    trade = core.execute_trade({"symbol": "BTCUSD", "side": "buy", "price": 60_000, "quantity": .1})
    assert trade["success"] is True
    assert trade["position"]["quantity"] == .1
    board = core.leaderboard()
    assert board["total"] == 1
    assert board["top_agents"][0]["trade_count"] == 1


def test_points_exchange(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    before = core.account()
    result = core.exchange_points(100)
    assert result["cash_received"] == 1
    assert result["account"]["points"] == before["points"] - 100
    assert result["account"]["cash"] == before["cash"] + 1


def test_challenge_lifecycle(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    challenge = core.create_challenge({"title": "BTC H4", "market": "crypto", "symbol": "BTCUSD"})
    core.join_challenge(challenge["challenge_key"])
    portfolio = core.challenge_trade(challenge["challenge_key"], {"symbol": "BTCUSD", "side": "buy", "price": 60_000, "quantity": .1})
    assert portfolio["trade_count"] == 1
    assert portfolio["positions"][0]["symbol"] == "BTCUSD"
    board = core.challenge_leaderboard(challenge["challenge_key"])
    assert board["leaderboard"][0]["rank"] == 1
    submission = core.challenge_submission(challenge["challenge_key"], {"title": "Plan", "content": "Breakout"})
    core.vote_submission(challenge["challenge_key"], submission["id"])
    assert core.challenge_submissions(challenge["challenge_key"])["submissions"][0]["votes"] == 1


def test_team_challenge(monkeypatch, tmp_path):
    _isolated(monkeypatch, tmp_path)
    challenge = core.create_challenge({"title": "Gold team", "market": "metals", "symbol": "XAUUSD"})
    team = core.create_challenge_team(challenge["challenge_key"], {"name": "Brown team"})
    portfolio = core.team_challenge_trade(challenge["challenge_key"], team["id"], {"symbol": "XAUUSD", "side": "buy", "price": 4_000, "quantity": 1})
    assert portfolio["trade_count"] == 1
    assert core.team_challenge_leaderboard(challenge["challenge_key"])["leaderboard"][0]["team_id"] == team["id"]
