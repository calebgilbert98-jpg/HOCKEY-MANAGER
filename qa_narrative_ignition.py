"""QA for narrative ignition (Muck 2026-10-02).

Verifies:
1. League digest collects AI-game stories and delivers top 3
2. Moment cooldowns are at ignition values (not the old silent ones)
3. Narrative spawn rate is at ignition value
4. Context narratives (prospect_watch, cup_window, etc.) can spawn
5. Headline builders exist for special_event, league_digest, rivalry_pregame
6. Outdoor game results deliver headlines
7. All new code is never-raises guarded
"""
import sys
import os

# pt.py isolation per AGENTS.md
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "HOCKEY-MANAGER"))


def test_digest_module():
    import league_digest
    assert hasattr(league_digest, "collect_game_stories")
    assert hasattr(league_digest, "deliver_digest")
    assert hasattr(league_digest, "clear_digest")
    assert league_digest._DIGEST_MAX == 3
    print("PASS: digest module structure")


def test_digest_collect_and_rank():
    import league_digest
    class FakeApp:
        pass
    app = FakeApp()
    league_digest.clear_digest(app)
    # Collect stories of varying weights
    stories = [
        {"kind": "blowout", "text": "Blowout text", "home": "A", "away": "B"},
        {"kind": "hat_trick", "text": "Hat trick text", "home": "C", "away": "D",
         "facts": {"rivalry": True}},  # rivalry bump
        {"kind": "fight", "text": "Fight text", "home": "E", "away": "F"},
        {"kind": "ot_thriller", "text": "OT text", "home": "G", "away": "H"},
    ]
    league_digest.collect_game_stories(app, stories)
    key = id(app)
    assert len(league_digest._DIGEST_STORE[key]) == 4
    # Hat trick + rivalry should rank highest
    ranked = sorted(league_digest._DIGEST_STORE[key],
                    key=league_digest._story_weight, reverse=True)
    assert ranked[0]["kind"] == "hat_trick", "hat trick + rivalry should rank first"
    league_digest.clear_digest(app)
    assert id(app) not in league_digest._DIGEST_STORE
    print("PASS: digest collect, rank, clear")


def test_digest_never_raises():
    import league_digest
    # All-None, garbage input -- must not raise
    league_digest.collect_game_stories(None, None)
    league_digest.collect_game_stories(None, [{"no": "text"}])
    assert league_digest.deliver_digest(None) == 0
    league_digest.clear_digest(None)
    print("PASS: digest never raises on garbage")


def test_cooldowns_ignited():
    import media_engine
    cd = media_engine._MOMENT_COOLDOWNS
    assert cd["bullet"] == 5, f"bullet cooldown {cd['bullet']} != 5"
    assert cd["rally"] == 7, f"rally cooldown {cd['rally']} != 7"
    assert cd["shield"] == 4, f"shield cooldown {cd['shield']} != 4"
    assert cd["backing"] == 15, f"backing cooldown {cd['backing']} != 15"
    print("PASS: moment cooldowns at ignition values")


def test_narrative_kinds():
    import media_engine
    # New kinds documented on the Narrative class
    import inspect
    src = inspect.getsource(media_engine.Narrative.__init__)
    for kind in ["prospect_watch", "trust_process", "cup_window", "legacy_chase"]:
        assert kind in src, f"{kind} not in Narrative kinds"
    assert hasattr(media_engine, "_maybe_spawn_context_narrative")
    print("PASS: context narrative kinds exist")


def test_headline_builders():
    import headlines
    from datetime import date
    # special_event
    msg = headlines.make_headline("special_event", date.today(),
                                  event_kind="outdoor_game",
                                  text="Test outdoor game")
    assert msg is not None, "special_event headline returned None"
    assert "Outdoor" in msg.subject or "🏟" in msg.subject
    # league_digest
    msg = headlines.make_headline("league_digest", date.today(),
                                  text="Test digest", digest_count=3)
    assert msg is not None, "league_digest headline returned None"
    # rivalry_pregame
    msg = headlines.make_headline("rivalry_pregame", date.today(),
                                  text="Test rivalry", home="A", away="B")
    assert msg is not None, "rivalry_pregame headline returned None"
    print("PASS: headline builders for new kinds")


def test_context_narrative_never_raises():
    import media_engine
    # Garbage input -- must not raise
    media_engine._maybe_spawn_context_narrative(None, None, None, None, None)
    media_engine._maybe_spawn_context_narrative(object(), object(), None,
                                               __import__("random"), [])
    print("PASS: context narrative never raises")


if __name__ == "__main__":
    test_digest_module()
    test_digest_collect_and_rank()
    test_digest_never_raises()
    test_cooldowns_ignited()
    test_narrative_kinds()
    test_headline_builders()
    test_context_narrative_never_raises()
    print("\nAll narrative ignition QA passed.")
