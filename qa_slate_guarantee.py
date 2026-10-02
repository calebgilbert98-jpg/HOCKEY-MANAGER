"""QA: guaranteed slate, Part 2 -- no-drop fallback + season-integrity audit.

Covers the BUG-003/004/005 follow-up in main.py:
  1. Error injection: force _simulate_game_full_batch to raise -> the
     lightweight fallback fires, the game is recorded (NOT dropped), the
     🛟 counter bumps and the news log gets the fallback line.
  2. Error injection: force BOTH tiers to raise -> the deterministic
     last-resort tier fires: valid result, reproducible, plausible
     scoreline, winner/loser/OT consistent.
  3. Preseason flag flows through every tier (no standings touch, the
     lightweight stub sees preseason=True).
  4. Season-integrity audit: fake standings short of the target ->
     [(team_name, gp, target)]; whole slate -> [].
  5. Shortfall handling: bulk/headless mode raises SeasonIntegrityError
     (loud, with detail); GUI mode arms the 'season_integrity' day-blocker
     (loud + blocking, no ugly tkinter-callback crash).

Deterministic. Run: python3 qa_slate_guarantee.py
"""
import sys
from datetime import date, timedelta
from types import SimpleNamespace

import main

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {detail}" if detail and not cond else ""))


class FakePlayer:
    def __init__(self, ovr):
        self._ovr = ovr
        self.nhl_games_played = 0

    def overall_rating(self):
        return self._ovr


def mkteam(name, ovr=82, n=20):
    return SimpleNamespace(
        team_name=name,
        roster=[FakePlayer(ovr) for _ in range(n)],
        league_name='National Hockey League',
        is_user_team=False,
        inbox=None,
    )


def mkapp():
    """Bare app instance: no tkinter, heavy per-game hooks stubbed."""
    app = main.HockeyManagerGUI.__new__(main.HockeyManagerGUI)
    # Bare instance (no tk.Tk.__init__): give it a tk attr so
    # tk.Tk.__getattr__ delegation doesn't infinitely recurse on
    # getattr-with-default for attributes that were never set.
    app.tk = None
    app._slate_fallbacks = 0
    app._season_integrity_shortfall = None
    app._bulk_simming = False
    app.news_log = []
    app.current_date = date(2027, 4, 10)
    app.user_team = None
    app.game_manager = None
    app.league = SimpleNamespace(standings={}, teams=[], schedule=[],
                                 season_games_count=84)
    app.recorded = []
    # Heavy per-game hooks: stubbed (their own QA covers them).
    app._grudge_week_market = lambda *a, **k: None
    app._grudge_week_grade = lambda *a, **k: None
    app._credit_nhl_games_played = lambda *a, **k: None
    app._narrative_postgame = lambda *a, **k: {'fights': 0}
    app._record_game_result = lambda gr: app.recorded.append(gr)
    return app


D = date(2027, 4, 10)

# --- 1. Full-batch raises -> lightweight fallback, game NOT dropped --------
app = mkapp()
H, A = mkteam('Test Home', ovr=85), mkteam('Test Away', ovr=80)
app.league.teams = [H, A]


def boom_full(h, a):
    raise RuntimeError("injected full-batch failure")


def fake_light(h, a, preseason=False):
    return (h, a, (3, 2), False)


app._league_sim_detail = lambda league_key: 'full'
app._simulate_game_full_batch = boom_full
app._simulate_game_lightweight = fake_light
app._simulate_games_batch([{'date': D, 'home_team': H, 'away_team': A}])

check("t1: game recorded, not dropped", len(app.recorded) == 1,
      f"recorded={len(app.recorded)}")
gr = app.recorded[0]
check("t1: recorded teams/scores right",
      gr['home_team'] is H and gr['away_team'] is A
      and gr['home_score'] == 3 and gr['away_score'] == 2
      and gr['winner'] is H)
check("t1: fallback counter bumped", app._slate_fallbacks == 1,
      f"counter={app._slate_fallbacks}")
check("t1: news log has SLATE-GUARANTEE line",
      any('🛟' in s.get('story', '') for s in app.news_log),
      f"news_log={app.news_log}")
check("t1: standings updated via normal post-processing",
      app.league.standings.get('Test Home', {}).get('W') == 1
      and app.league.standings.get('Test Away', {}).get('L') == 1,
      f"standings={app.league.standings}")

# --- 2. Both tiers raise -> deterministic last resort -----------------------
app2 = mkapp()
H2, A2 = mkteam('Alpha HC', ovr=88), mkteam('Beta HC', ovr=78)
app2.league.teams = [H2, A2]


def boom_light(h, a, preseason=False):
    raise RuntimeError("injected lightweight failure")


app2._league_sim_detail = lambda league_key: 'quick'
app2._simulate_game_lightweight = boom_light
app2._simulate_games_batch([{'date': D, 'home_team': H2, 'away_team': A2}])

check("t2: game recorded via deterministic tier", len(app2.recorded) == 1,
      f"recorded={len(app2.recorded)}")
gr2 = app2.recorded[0]
hs, aws = gr2['home_score'], gr2['away_score']
_wg, _lg = max(hs, aws), min(hs, aws)
check("t2: plausible scoreline (winner 2-5, loser 0..winner-1)",
      2 <= _wg <= 5 and 0 <= _lg <= _wg - 1,
      f"scores={(hs, aws)}")
check("t2: winner/loser consistent with scores",
      (gr2['winner'] is H2 and hs > aws)
      or (gr2['winner'] is A2 and aws > hs))
check("t2: counter bumped exactly once", app2._slate_fallbacks == 1,
      f"counter={app2._slate_fallbacks}")
check("t2: deterministic tier named in news",
      any('deterministic' in s.get('story', '') for s in app2.news_log),
      f"news_log={app2.news_log}")

# Reproducibility: same inputs -> identical result.
r1 = app2._slate_deterministic_result(H2, A2, D)
r2 = app2._slate_deterministic_result(H2, A2, D)
check("t2: deterministic result reproducible",
      (r1[2], r1[3]) == (r2[2], r2[3])
      and (r1[0] is r2[0]) and (r1[1] is r2[1]),
      f"r1={r1[2:]} r2={r2[2:]}")

# Team-symmetric: the stronger club wins more often over many seeds,
# regardless of home/away assignment.
_home_wins_as_home = sum(
    1 for d in range(40)
    if app2._slate_deterministic_result(
        H2, A2, date(2027, 4, 1) + timedelta(days=d))[0] is H2)
_away_wins_as_away = sum(
    1 for d in range(40)
    if app2._slate_deterministic_result(
        A2, H2, date(2027, 4, 1) + timedelta(days=d))[0] is H2)
check("t2: stronger club favored home AND away (symmetric, not a cheat)",
      _home_wins_as_home > 20 and _away_wins_as_away > 20,
      f"strong-wins-as-home={_home_wins_as_home}/40 "
      f"strong-wins-as-away={_away_wins_as_away}/40")

# --- 3. Preseason flag flows through every tier -----------------------------
app3 = mkapp()
H3, A3 = mkteam('Pre Home'), mkteam('Pre Away')
app3.league.teams = [H3, A3]
_seen = {}


def spy_light(h, a, preseason=False):
    _seen['preseason'] = preseason
    return (h, a, (4, 1), False)


app3._league_sim_detail = lambda league_key: 'full'  # would-be full path
app3._simulate_game_full_batch = boom_full  # must NOT be reached either
app3._simulate_game_lightweight = spy_light
app3._simulate_games_batch(
    [{'date': D, 'home_team': H3, 'away_team': A3, 'preseason': True}])
check("t3: preseason game recorded", len(app3.recorded) == 1)
check("t3: lightweight got preseason=True", _seen.get('preseason') is True,
      f"seen={_seen}")
check("t3: standings untouched by exhibition",
      'Pre Home' not in app3.league.standings
      and 'Pre Away' not in app3.league.standings,
      f"standings={app3.league.standings}")

# --- Corrupt / malformed entries: loud skip, no crash -----------------------
app4 = mkapp()
H4 = mkteam('Only Home')
app4._simulate_games_batch([
    {'date': D, 'home_team': H4, 'away_team': None},  # corrupt
    "not-a-game",                                      # malformed
])
check("t4: corrupt entries skipped loudly, nothing recorded",
      len(app4.recorded) == 0, f"recorded={len(app4.recorded)}")

# --- 4. Season-integrity audit ----------------------------------------------
app5 = mkapp()
T1 = mkteam('Whole Club')
T2 = mkteam('Short Club')
T3 = mkteam('Ghost Club')  # no standings entry at all
app5.league.teams = [T1, T2, T3]
app5.league.standings = {
    'Whole Club': {'W': 50, 'L': 30, 'OTL': 4},   # 84 GP
    'Short Club': {'W': 40, 'L': 38, 'OTL': 3},   # 81 GP
}
short = app5._audit_season_slate()
check("t4a: audit flags short + missing clubs",
      ('Short Club', 81, 84) in short and ('Ghost Club', 0, 84) in short
      and len(short) == 2,
      f"short={short}")
app5.league.standings['Short Club'] = {'W': 41, 'L': 38, 'OTL': 5}
app5.league.standings['Ghost Club'] = {'W': 42, 'L': 40, 'OTL': 2}
check("t4b: whole slate -> no shortfalls", app5._audit_season_slate() == [],
      f"short={app5._audit_season_slate()}")

# Legacy saves without season_games_count default to 82.
try:
    del app5.league.season_games_count
except AttributeError:
    pass
app5.league.standings = {'Whole Club': {'W': 50, 'L': 30, 'OTL': 2}}  # 82
app5.league.teams = [T1]
check("t4c: missing season_games_count defaults to 82",
      app5._audit_season_slate() == [])

# --- 5a. Headless/bulk: raise SeasonIntegrityError --------------------------
app6 = mkapp()
app6._bulk_simming = True
UT = mkteam('User Club')
UT.inbox = SimpleNamespace(messages=[],
                           add_message=lambda m: UT.inbox.messages.append(m))
app6.user_team = UT
app6.league.teams = [T1, T2]
app6.league.standings = {'Whole Club': {'W': 50, 'L': 30, 'OTL': 4},
                         'Short Club': {'W': 40, 'L': 38, 'OTL': 3}}
_raised = None
try:
    app6._handle_slate_shortfall(app6._audit_season_slate())
except main.SeasonIntegrityError as e:
    _raised = e
check("t5a: bulk mode raises SeasonIntegrityError", _raised is not None)
check("t5a: error names the short club and deficit",
      _raised is not None and 'Short Club' in str(_raised)
      and '81/84' in str(_raised),
      f"err={_raised}")
check("t5a: news log got the integrity banner",
      any('🚨' in s.get('story', '') and 'Short Club' in s.get('story', '')
          for s in app6.news_log))
check("t5a: inbox item created for the user",
      len(UT.inbox.messages) == 1
      and UT.inbox.messages[0].is_urgent
      and 'Short Club' in UT.inbox.messages[0].content,
      f"inbox={len(UT.inbox.messages)}")

# --- 5b. GUI mode: arm the day-blocker, no exception ------------------------
app7 = mkapp()
app7._bulk_simming = False
app7.league.teams = [T1, T2]
app7.league.standings = {'Whole Club': {'W': 50, 'L': 30, 'OTL': 4},
                         'Short Club': {'W': 40, 'L': 38, 'OTL': 3}}
try:
    app7._handle_slate_shortfall(app7._audit_season_slate())
    _gui_raised = False
except Exception as e:  # noqa: BLE001 -- must NOT raise in GUI mode
    _gui_raised = True
check("t5b: GUI mode does not raise", not _gui_raised)
check("t5b: blocker state armed",
      app7._season_integrity_shortfall
      == [('Short Club', 81, 84)],
      f"state={app7._season_integrity_shortfall}")
_label, _blockers = app7.get_continue_state()
_ids = [b.get('id') for b in _blockers]
check("t5b: 'season_integrity' blocker present", 'season_integrity' in _ids,
      f"ids={_ids}")
_b = next(b for b in _blockers if b.get('id') == 'season_integrity')
check("t5b: blocker names the short club + deficit",
      'Short Club' in _b.get('detail', '')
      and '81/84' in _b.get('detail', ''),
      f"detail={_b.get('detail', '')[:120]}")
check("t5b: blocker has no action jump (not user-resolvable)",
      'action' not in _b)

# No shortfall -> no blocker.
app8 = mkapp()
app8.league.teams = [T1]
app8.league.standings = {'Whole Club': {'W': 50, 'L': 30, 'OTL': 4}}
_label8, _blockers8 = app8.get_continue_state()
check("t5c: no blocker when slate is whole",
      'season_integrity' not in [b.get('id') for b in _blockers8])

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
