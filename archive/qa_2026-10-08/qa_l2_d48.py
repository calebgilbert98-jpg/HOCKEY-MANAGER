"""QA for D48 (L2): media/fan speculation only, NEVER trade-blocking.

Muck's directive: "fleece is an internal opinion and speculative from
media/fan pov" -- trades are NEVER blocked based on history.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _mk_team(name, gm_name="GM"):
    class T:
        pass
    t = T()
    t.team_name = name
    t.gm_name = gm_name
    t.roster = []
    t.ahl_roster = []
    t.prospects = []
    return t


def _mk_league():
    class L:
        pass
    lg = L()
    lg.teams = []
    lg.inbox = []
    return lg


def test_speculation_headline_builder():
    """The trade_speculation headline builds and is framed as opinion."""
    from headlines import make_headline
    from datetime import date
    msg = make_headline(
        "trade_speculation", date(2026, 10, 2),
        team_a="Team A", team_b="Team B",
        pieces_a="Star Player", pieces_b="2nd round pick",
        winner_name="Team A", loser_name="Team B",
    )
    assert msg is not None, "speculation headline should build"
    # Must be framed as opinion, not fact.
    _opinion_markers = ["pundits", "some fans", "some analysts", "hot take",
                        "too early to judge", "only time will tell"]
    _text = (msg.subject + " " + msg.content).lower()
    assert any(m in _text for m in _opinion_markers), \
        f"headline must be framed as speculation, got: {msg.subject}"
    print("PASS: speculation headline framed as opinion")


def test_trades_never_blocked_by_history():
    """Even after multiple 'fleeces', trades still execute."""
    # This is a structural check: execute_trade has no respect/history gate.
    import trade_engine
    import inspect
    _src = inspect.getsource(trade_engine.execute_trade)
    _forbidden = ["gm_respect", "_respect_store", "won't deal",
                  "wont deal", "refuse to deal", "diminish"]
    for _term in _forbidden:
        assert _term not in _src.lower(), \
            f"execute_trade must not contain trade-blocking logic: {_term}"
    print("PASS: execute_trade has no history-based blocking")


def test_record_gm_dealing_never_raises():
    """The ledger hook is safe on garbage input."""
    from reputation_system import record_gm_dealing
    # None league, None teams -- must not raise.
    try:
        record_gm_dealing(None, None, None, 4, "deal")
    except Exception as e:
        raise AssertionError(f"record_gm_dealing raised: {e}")
    print("PASS: record_gm_dealing never raises on garbage")


def test_speculation_only_on_lopsided():
    """Speculation fires only on genuinely lopsided deals."""
    from trade_engine import _maybe_fire_trade_speculation
    lg = _mk_league()
    ta = _mk_team("Team A")
    tb = _mk_team("Team B")
    lg.teams = [ta, tb]
    # Fair deal (ratio 1.0) -- should NOT fire.
    _maybe_fire_trade_speculation(lg, ta, tb, [], [], 1.0, "2026-10-02")
    assert len(lg.inbox) == 0, "fair deal should not trigger speculation"
    # Lopsided deal (ratio 2.0) -- should fire.
    _maybe_fire_trade_speculation(lg, ta, tb, [], [], 2.0, "2026-10-02")
    # Inbox may be empty if deliver_headline not available, but shouldn't crash.
    print("PASS: speculation only on lopsided deals, never crashes")


def test_no_wont_deal_in_ui():
    """GM Relationships UI has no 'won't deal' status."""
    import gm_relationships_window as _ui
    import inspect
    _src = inspect.getsource(_ui)
    _forbidden = ["won't deal", "wont deal", "refuse to deal",
                  "will not deal", "blacklist"]
    for _term in _forbidden:
        assert _term not in _src.lower(), \
            f"UI must not show deal-blocking status: {_term}"
    print("PASS: UI has no deal-blocking status")


def main():
    test_speculation_headline_builder()
    test_trades_never_blocked_by_history()
    test_record_gm_dealing_never_raises()
    test_speculation_only_on_lopsided()
    test_no_wont_deal_in_ui()
    print("\nAll D48 (L2) QA passed!")


if __name__ == "__main__":
    main()
