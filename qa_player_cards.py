"""QA: player card, comparison, and universal right-click bindings."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tkinter as tk
import game_classes as g
from game_classes import PlayerPosition

passed, failed = 0, []
def check(name, fn):
    global passed
    try:
        fn(); passed += 1; print(f"  PASS {name}")
    except Exception as e:
        import traceback; traceback.print_exc(); failed.append(name); print(f"  FAIL {name}: {e}")

p1 = g.Player("Test", "Player", 25, PlayerPosition.CENTER, 75)
p2 = g.Player("Other", "Guy", 27, PlayerPosition.LEFT_WING, 72)

root = tk.Tk(); root.geometry("1600x900")
root.BG_COLOR="#1E1E1E"; root.CONTENT_BG="#2D2D2D"; root.HEADER_COLOR="#FFFFFF"; root.TEXT_COLOR="#FFFFFF"
root.user_team = type('T', (), {'roster': [p1, p2], 'ahl_roster': [], 'prospects': []})()

def t_card_modern():
    from modern_profile import PlayerProfile
    w = PlayerProfile(root, p1); root.update(); w.destroy()
def t_compare():
    from player_context_menu import PlayerContextMenu
    mgr = PlayerContextMenu(root); mgr.parent = root
    mgr._compare_players(p1); root.update()
    for w in root.winfo_children():
        try: w.destroy()
        except Exception: pass
def t_compare_legacy_entry():
    # Legacy _create_comparison_window must not crash (delegates to enhanced)
    from player_context_menu import PlayerContextMenu
    mgr = PlayerContextMenu(root); mgr.parent = root
    mgr._create_comparison_window(p1); root.update()
    for w in root.winfo_children():
        try: w.destroy()
        except Exception: pass
def t_bind_helper():
    from player_context_menu import bind_player_context
    lbl = tk.Label(root, text=p1.full_name); lbl.pack()
    mgr = bind_player_context(lbl, p1, root)
    assert mgr is not None
    lbl.destroy()
def t_boxscore_grid_players_param():
    import inspect
    from game_box_score import GameBoxScoreView
    sig = inspect.signature(GameBoxScoreView._grid_table)
    assert 'players' in sig.parameters, "players param missing"

# ---------------------------------------------------------------------------
# Analytics tab: per-player shot map (module 04 tactical context)
# ---------------------------------------------------------------------------
from types import SimpleNamespace

def _walk(w):
    yield w
    try:
        kids = w.winfo_children()
    except Exception:
        return
    for k in kids:
        yield from _walk(k)

def _labels(w):
    return [x for x in _walk(w)
            if x.winfo_class() == "Label" and str(x.cget("text") or "")]

def _canvases(w):
    return [x for x in _walk(w) if x.winfo_class() == "Canvas"]

def _mk_team_with_shots(player, n_shots=2):
    team = g.Team("Testers", "TST", "D", "C")
    team.roster.append(player)
    player.id = 4242
    shots = []
    for i in range(n_shots):
        shots.append({"shooter_id": 4242, "shooter": player.full_name,
                      "team": "Testers", "opp": "Others",
                      "x": 175.0 - i * 25, "y": 42.5,
                      "xg": 0.18, "outcome": "goal" if i == 0 else "save",
                      "period": 1, "clock": 600.0, "location": "slot",
                      "distance": 12.0, "shot_type": "wrist"})
    # another player's shot must NOT leak into this card's map
    shots.append({"shooter_id": 9999, "shooter": "Someone Else",
                  "team": "Testers", "opp": "Others",
                  "x": 160.0, "y": 60.0, "xg": 0.09, "outcome": "blocked",
                  "period": 2, "clock": 300.0, "location": "point",
                  "distance": 40.0, "shot_type": "slap"})
    team.analytics_games = [{"date": "2026-10-01", "home": "Testers",
                             "away": "Others", "score": (3, 2),
                             "shots": shots, "momentum": [], "entries": [],
                             "lines": {}}]
    return team

def t_card_analytics_shot_map():
    from modern_profile import PlayerProfile
    team = _mk_team_with_shots(p1)
    root.league = SimpleNamespace(teams=[team])
    w = PlayerProfile(root, p1); root.update()
    try:
        maps = [c for c in _canvases(w)
                if str(c.cget("bg")).lower() == "#1d2b33"]
        assert maps, "shot map canvas not rendered on Analytics tab"
        summary = [l for l in _labels(w) if "2 shots" in str(l.cget("text"))]
        assert summary, "shot map summary should count only this player's shots"
        stale = [l for l in _labels(w)
                 if "No shot locations are tracked" in str(l.cget("text"))]
        assert not stale, "stale disclaimer still present"
    finally:
        w.destroy()

def t_card_analytics_no_shot_data():
    from modern_profile import PlayerProfile
    p3 = g.Player("No", "Data", 22, PlayerPosition.CENTER, 68)
    team = g.Team("Testers", "TST", "D", "C")
    team.roster.append(p3)
    team.analytics_games = []  # nothing tracked yet
    root.league = SimpleNamespace(teams=[team])
    w = PlayerProfile(root, p3); root.update()
    try:
        note = [l for l in _labels(w) if "No tracked shots yet" in str(l.cget("text"))]
        assert note, "empty-state note missing"
        maps = [c for c in _canvases(w)
                if str(c.cget("bg")).lower() == "#1d2b33"]
        assert not maps, "map canvas should not render without data"
    finally:
        w.destroy()

def t_card_analytics_goalie_no_map():
    from modern_profile import PlayerProfile
    pg = g.Player("Goal", "Tender", 28, PlayerPosition.GOALIE, 80)
    team = g.Team("Testers", "TST", "D", "C")
    team.roster.append(pg)
    team.analytics_games = []
    root.league = SimpleNamespace(teams=[team])
    w = PlayerProfile(root, pg); root.update()
    try:
        maps = [c for c in _canvases(w)
                if str(c.cget("bg")).lower() == "#1d2b33"]
        assert not maps, "goalies have no per-goalie shot tracking; no map expected"
    finally:
        w.destroy()

# ---------------------------------------------------------------------------
# Exit path: _quit_app must tear the root down even when a widget's
# Python-side destroy() raises (the "game doesn't close" hang).
# ---------------------------------------------------------------------------
def t_quit_app_survives_raising_destroy():
    from main import HockeyManagerGUI
    r = tk.Tk(); r.withdraw()
    bad = tk.Frame(r)
    def _boom():
        raise AttributeError("half-built widget (no _font)")
    bad.destroy = _boom  # instance attr shadows Misc.destroy
    bad.pack()
    HockeyManagerGUI._quit_app(r)  # must not raise
    try:
        r.update()
    except Exception:
        pass
    try:
        alive = bool(r.winfo_exists())
    except Exception:
        alive = False
    assert not alive, "root survived _quit_app"

def t_full_app_quit_app():
    # Real app, real widgets, real _quit_app: no hang, root gone.
    from main import HockeyManagerGUI
    t1 = g.Team("Home", "HOM", "D", "C"); t2 = g.Team("Away", "AWY", "D", "C")
    for i in range(5):
        for t in (t1, t2):
            t.roster.append(g.Player(first_name=f"P{i}", last_name="X", age=25,
                                     primary_position=PlayerPosition.CENTER,
                                     jersey_number=i + 1))
    class FakeGM:
        league = SimpleNamespace(teams=[t1, t2], standings={})
        user_team = t1
        current_date = "2026-10-01"
        startup_settings = {}
    app = HockeyManagerGUI(FakeGM())
    app.is_new_game = True
    app.update()
    app._quit_app()
    try:
        app.update()
    except Exception:
        pass
    try:
        alive = bool(app.winfo_exists())
    except Exception:
        alive = False
    assert not alive, "app root survived _quit_app"

def t_dashboard_no_font_crash():
    # dashboard_home must not pass tkinter Font objects to CTk widgets
    # (raises "Wrong font type" and leaves a half-built zombie widget).
    import dashboard_home
    import tkinter.font as tkfont
    assert isinstance(dashboard_home._ctk_font(tkfont.Font(family="Segoe UI", size=11,
                                                          weight="bold")),
                      tuple)

print("player card / comparison / right-click QA:")
check("modern_profile card constructs", t_card_modern)
check("enhanced comparison constructs", t_compare)
check("legacy comparison entry delegates", t_compare_legacy_entry)
check("bind_player_context helper works", t_bind_helper)
check("box score grid accepts players", t_boxscore_grid_players_param)
check("analytics tab: per-player shot map", t_card_analytics_shot_map)
check("analytics tab: no-data state", t_card_analytics_no_shot_data)
check("analytics tab: goalie has no shot map", t_card_analytics_goalie_no_map)
check("exit: _quit_app survives raising destroy()", t_quit_app_survives_raising_destroy)
check("exit: full app _quit_app tears down", t_full_app_quit_app)
check("dashboard: Font objects coerced for CTk", t_dashboard_no_font_crash)
root.destroy()
print(f"\n{passed} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
