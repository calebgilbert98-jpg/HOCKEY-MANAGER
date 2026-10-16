#!/usr/bin/env python3
"""R12: date-aware gates (Phase 2) tests.

Bucket under test: daily_news.BUCKET_WINDOWS + the _w_* window predicates,
the _generate dispatch gate, and the best_team tied-vs-leading split.
Conventions: synthetic SimpleNamespace app/team fixtures (same shape as the
R8 tests); assertions on premises, not phrasing.
"""
import sys
import os
import types
import random
import inspect
from datetime import date, datetime, timedelta

_REPO = os.environ.get(
    "R12_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import daily_news as dn

FAILED = []


def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond:
        FAILED.append(label)


def mkteam(name, w, l, otl, league_name="National Hockey League",
           conference="Eastern", roster=None):
    return types.SimpleNamespace(
        team_name=name, conference=conference,
        league_name=league_name, wins=w, losses=l, ot_losses=otl,
        roster=list(roster or []))


def mkapp(teams, season_year=2026, season_len=82, schedule=None):
    lg = types.SimpleNamespace(teams=list(teams), season_year=season_year)
    if schedule is not None:
        lg.schedule = schedule
    return types.SimpleNamespace(league=lg, season_games_count=season_len,
                                 _daily_news_recent={})


def nhl_pool(gps, names=None):
    """Teams with ~1.0 pt pace at the given GPs (all Eastern)."""
    names = names or [f"Team{i}" for i in range(len(gps))]
    out = []
    for n, gp in zip(names, gps):
        pts = gp  # 1.0 pace
        w, otl = pts // 2, pts % 2
        out.append(mkteam(n, w, gp - w - otl, otl))
    return out


def mkgoalie(fn="Net", ln="Minder"):
    return types.SimpleNamespace(
        first_name=fn, last_name=ln,
        primary_position=types.SimpleNamespace(value="G"),
        stats=types.SimpleNamespace(games_played=20))


# ---------------------------------------------------------------------------
# 1. Registry: complete, and every generator references its declared window
# ---------------------------------------------------------------------------

gen_names = {name for name, _fn, _w in dn._GENERATORS}
check("registry covers every generator",
      set(dn.BUCKET_WINDOWS) == gen_names)
check("registry has 19 entries", len(dn.BUCKET_WINDOWS) == 19)

for _name, fn, _weight in dn._GENERATORS:
    wname = dn.BUCKET_WINDOWS[_name]["window"].__name__
    src = inspect.getsource(fn)
    check(f"generator {_name} references its window {wname}", wname in src)

for _name, entry in dn.BUCKET_WINDOWS.items():
    check(f"window entry {_name} has a derivation note",
          bool(entry.get("derivation")))

# ---------------------------------------------------------------------------
# 2. Calendar predicates: month boundaries
# ---------------------------------------------------------------------------

check("in_season: Oct 15 true", dn._w_in_season(None, date(2026, 10, 15)))
check("in_season: Apr 30 true", dn._w_in_season(None, date(2027, 4, 30)))
check("in_season: Jul 15 false", not dn._w_in_season(None, date(2027, 7, 15)))
check("in_season: Sep 30 false", not dn._w_in_season(None, date(2026, 9, 30)))
check("in_season: May 1 false", not dn._w_in_season(None, date(2027, 5, 1)))

check("draft: Mar 1 true", dn._w_draft(None, date(2027, 3, 1)))
check("draft: Jun 30 true", dn._w_draft(None, date(2027, 6, 30)))
check("draft: Jul 1 false", not dn._w_draft(None, date(2027, 7, 1)))
check("draft: Oct 1 false", not dn._w_draft(None, date(2026, 10, 1)))

check("offseason: Jul 1 true", dn._w_offseason(None, date(2027, 7, 1)))
check("offseason: May 1 true", dn._w_offseason(None, date(2027, 5, 1)))
check("offseason: Oct 1 false", not dn._w_offseason(None, date(2026, 10, 1)))
check("offseason: Apr 30 false", not dn._w_offseason(None, date(2027, 4, 30)))

check("prospect: always open (Jan)", dn._w_prospect(None, date(2027, 1, 15)))
check("prospect: always open (Jul)", dn._w_prospect(None, date(2027, 7, 15)))
check("extension: always open (Jan, R8g design kept)",
      dn._w_extension(None, date(2027, 1, 15)))
check("extension: always open (Jul, R8g design kept)",
      dn._w_extension(None, date(2027, 7, 15)))

# ---------------------------------------------------------------------------
# 3. _w_as_date coercions
# ---------------------------------------------------------------------------

check("as_date: date passthrough",
      dn._w_as_date(date(2027, 1, 15)) == date(2027, 1, 15))
check("as_date: datetime -> date",
      dn._w_as_date(datetime(2027, 1, 15, 12, 30)) == date(2027, 1, 15))
check("as_date: None -> None", dn._w_as_date(None) is None)
check("as_date: garbage -> None", dn._w_as_date("2027-01-15") is None)

# ---------------------------------------------------------------------------
# 4. GP-bound windows: playoff race / award races
# ---------------------------------------------------------------------------

# 8-team Eastern pool, GP 68-72: median 70 >= 60, spread 4 <= 10.
late = mkapp(nhl_pool([68, 69, 70, 70, 71, 71, 72, 72]))
check("playoff_race: stretch run true", dn._w_playoff_race(late, date(2027, 3, 1)))
early = mkapp(nhl_pool([18, 19, 20, 20, 21, 21, 22, 22]))
check("playoff_race: October false",
      not dn._w_playoff_race(early, date(2026, 11, 1)))
check("playoff_race: offseason false",
      not dn._w_playoff_race(late, date(2027, 7, 1)))
done = mkapp(nhl_pool([82] * 8))
check("playoff_race: schedule exhausted false",
      not dn._w_playoff_race(done, date(2027, 4, 12)))

mid = mkapp(nhl_pool([44, 45, 45, 46, 46, 47, 47, 48]))
check("award_races: second half true",
      dn._w_award_races(mid, date(2027, 1, 15)))
check("award_races: first half false",
      not dn._w_award_races(early, date(2026, 11, 15)))

# ---------------------------------------------------------------------------
# 5. Deadline window boundaries (schedule: last game 2027-04-10 ->
#    deadline 2027-03-01, 40 days prior per trade_deadline_date)
# ---------------------------------------------------------------------------

sched = [{"league": "NHL", "date": date(2027, 4, 10)}]
dl_app = mkapp(nhl_pool([64, 66, 66, 68, 68, 68, 70, 70, 70]),
               schedule=sched)
DEADLINE = date(2027, 3, 1)
check("trade_deadline: deadline-8 silent",
      not dn._w_trade_deadline(dl_app, DEADLINE - timedelta(days=8)))
check("trade_deadline: deadline-7 fires",
      dn._w_trade_deadline(dl_app, DEADLINE - timedelta(days=7)))
check("trade_deadline: deadline day fires",
      dn._w_trade_deadline(dl_app, DEADLINE))
check("trade_deadline: deadline+1 silent",
      not dn._w_trade_deadline(dl_app, DEADLINE + timedelta(days=1)))
check("trade_deadline: offseason silent",
      not dn._w_trade_deadline(dl_app, date(2027, 7, 1)))

# ---------------------------------------------------------------------------
# 6. Regular-season game-day window (heroics / debuts)
# ---------------------------------------------------------------------------

g_app = mkapp([], schedule=sched)
check("game_day: Sep 30 preseason silent",
      not dn._w_regular_season_game_day(g_app, date(2026, 10, 1)))
check("game_day: Jan 14 regular season true",
      dn._w_regular_season_game_day(g_app, date(2027, 1, 15)))
check("game_day: Apr 9 (last game Apr 10) true",
      dn._w_regular_season_game_day(g_app, date(2027, 4, 10)))
check("game_day: Apr 11 (past last game) silent",
      not dn._w_regular_season_game_day(g_app, date(2027, 4, 12)))
# No schedule at all: underivable season end fails open (month is the bound)
nosched = mkapp([])
check("game_day: no schedule fails open in-season",
      dn._w_regular_season_game_day(nosched, date(2027, 1, 15)))
check("game_day: no schedule still silent in September",
      not dn._w_regular_season_game_day(nosched, date(2026, 10, 1)))

# ---------------------------------------------------------------------------
# 7. best_team tied-vs-leading split
# ---------------------------------------------------------------------------

def league_notes_stories(teams, day=date(2027, 2, 1), seed=3):
    # Goalie-only rosters: _all_players is non-empty (so the bucket runs),
    # but the scoring race finds no qualified skaters.
    for t in teams:
        t.roster = [mkgoalie()]
    app = mkapp(teams)
    return dn._league_notes(app, day, random.Random(seed))


# Two teams tied on win pct (.667): 10-5-0 and 8-4-0.
tied_teams = [mkteam("Alpha", 10, 5, 0), mkteam("Beta", 8, 4, 0),
              mkteam("Gamma", 1, 14, 0), mkteam("Delta", 2, 13, 0)]
sts = league_notes_stories(tied_teams)
pr = [s for s in sts if "POWER RANKINGS" in s]
check("best_team: tied pair produces a story", len(pr) == 1)
if pr:
    s = pr[0]
    check("best_team: tied story names BOTH teams",
          "Alpha" in s and "Beta" in s)
    check("best_team: tied story uses tie framing",
          any(k in s for k in ("share", "tied", "dead heat", "dead even",
                               "Co-owners", "No sole owner")))
    check("best_team: tied story shows both records",
          "10-5-0" in s and "8-4-0" in s)

# Sole leader: no tie framing, one team named.
sole_teams = [mkteam("Alpha", 12, 3, 0), mkteam("Beta", 8, 4, 0),
              mkteam("Gamma", 1, 14, 0), mkteam("Delta", 2, 13, 0)]
sts = league_notes_stories(sole_teams)
pr = [s for s in sts if "POWER RANKINGS" in s]
check("best_team: sole leader produces a story", len(pr) == 1)
if pr:
    s = pr[0]
    check("best_team: sole story names the leader", "Alpha" in s)
    check("best_team: sole story does not name the runner-up",
          "Beta" not in s)
    check("best_team: sole story has no tie framing",
          not any(k in s for k in ("share the league", "tied for",
                                   "dead heat", "Co-owners")))

# Three-way tie: all three named.
three = [mkteam("Alpha", 10, 5, 0), mkteam("Beta", 8, 4, 0),
         mkteam("Gamma", 6, 3, 0), mkteam("Delta", 1, 14, 0)]
sts = league_notes_stories(three)
pr = [s for s in sts if "POWER RANKINGS" in s]
check("best_team: three-way tie names all three",
      len(pr) == 1 and all(n in pr[0] for n in ("Alpha", "Beta", "Gamma")))

# Tied but unnameable: fail closed (no false sole-leader claim).
bad = [types.SimpleNamespace(team_name="", league_name="National Hockey League",
                             wins=10, losses=5, ot_losses=0, roster=[]),
       mkteam("Beta", 8, 4, 0),
       mkteam("Gamma", 1, 14, 0), mkteam("Delta", 2, 13, 0)]
sts = league_notes_stories(bad)
pr = [s for s in sts if "POWER RANKINGS" in s]
check("best_team: unnameable tie stays silent", pr == [])

# _best_team_tied_str: 4-way tie collapses to "N more".
four = [mkteam("A", 10, 5, 0), mkteam("B", 8, 4, 0),
        mkteam("C", 6, 3, 0), mkteam("D", 4, 2, 0)]
rows = [(2 / 3, t, t.wins, t.losses, t.ot_losses) for t in four]
tstr = dn._best_team_tied_str(rows)
check("best_team: 4-way tie collapses extras",
      tstr is not None and "1 more" in tstr and "A (10-5-0)" in tstr)

# ---------------------------------------------------------------------------
# 8. Dispatch gate: _window_allows + _generate integration
# ---------------------------------------------------------------------------

check("dispatch: unknown bucket name fails open",
      dn._window_allows("gen0", None, date(2027, 7, 15)))
coach_app = mkapp(nhl_pool([40] * 8))
check("dispatch: coach blocked in July",
      not dn._window_allows("coach", coach_app, date(2027, 7, 15)))
check("dispatch: coach allowed in January",
      dn._window_allows("coach", coach_app, date(2027, 1, 15)))
check("dispatch: offseason allowed in July",
      dn._window_allows("offseason", coach_app, date(2027, 7, 15)))
check("dispatch: controversy blocked in July",
      not dn._window_allows("controversy", coach_app, date(2027, 7, 15)))
check("dispatch: controversy allowed in May (holdout season)",
      dn._window_allows("controversy", coach_app, date(2027, 5, 15)))
check("dispatch: controversy allowed in January",
      dn._window_allows("controversy", coach_app, date(2027, 1, 15)))


def test_controversy_split_window():
    _failed_before = len(FAILED)

    def fresh_app():
        p = types.SimpleNamespace(
            first_name="Hold", last_name="Out",
            primary_position=types.SimpleNamespace(value="C"),
            overall=85,
            stats=types.SimpleNamespace(games_played=80, goals=30,
                                        assists=40),
            contract=types.SimpleNamespace(years_remaining=1),
            id=999)
        t = mkteam("Holdouts", 40, 30, 12, roster=[p])
        return mkapp([t])

    may = dn._controversies(fresh_app(), date(2027, 5, 15),
                            random.Random(11))
    check("controversy: holdout fires in May",
          any("Hold Out" in s for s in may))
    check("controversy: no scratch/rumor framing in May",
          not any("SCRATCH" in s or "RUMOR" in s for s in may))
    jul = dn._controversies(fresh_app(), date(2027, 7, 15),
                            random.Random(11))
    check("controversy: silent in July", jul == [])
    jan = dn._controversies(fresh_app(), date(2027, 1, 15),
                            random.Random(11))
    check("controversy: holdout fires in January",
          any("Hold Out" in s for s in jan))
    assert len(FAILED) == _failed_before, \
        f"failing checks: {FAILED[_failed_before:]}"


def test_generate_dispatch_blocks():
    _failed_before = len(FAILED)
    calls = []

    def fake_coach(app, game_date, rng):
        calls.append(game_date)
        return ["COACH: fake story"]

    old = dn._GENERATORS
    dn._GENERATORS = [("coach", fake_coach, 1.0)]
    try:
        app = types.SimpleNamespace(
            league=types.SimpleNamespace(teams=[]),
            _daily_news_recent={}, add_news=lambda s: None)
        n = dn._generate(app, date(2027, 7, 15))
    finally:
        dn._GENERATORS = old
    check("generate: coach generator not called in July", calls == [])
    check("generate: no stories added in July", n == 0)
    assert len(FAILED) == _failed_before, \
        f"failing checks: {FAILED[_failed_before:]}"


def test_generate_dispatch_allows():
    _failed_before = len(FAILED)
    calls = []

    def fake_prospect(app, game_date, rng):
        calls.append(game_date)
        return ["PROSPECT: fake story"]

    old = dn._GENERATORS
    dn._GENERATORS = [("prospect", fake_prospect, 1.0)]
    try:
        added = []
        app = types.SimpleNamespace(
            league=types.SimpleNamespace(teams=[]),
            _daily_news_recent={}, add_news=added.append)
        n = dn._generate(app, date(2027, 7, 15))
    finally:
        dn._GENERATORS = old
    check("generate: always-open generator called in July", calls != [])
    check("generate: its story added", n >= 1)
    assert len(FAILED) == _failed_before, \
        f"failing checks: {FAILED[_failed_before:]}"


def test_script_checks_all_pass():
    """Aggregate for the check() calls that run at module import time.

    Each test_* function above asserts the checks in its own body; this
    test covers the remaining module-level checks, whose failures would
    otherwise be visible only via the script's exit code.
    """
    assert not FAILED, f"{len(FAILED)} check(s) failed: {FAILED[:10]}"


if __name__ == "__main__":
    for _tname in sorted(globals()):
        _tfn = globals()[_tname]
        if (_tname.startswith("test_")
                and _tname != "test_script_checks_all_pass"
                and callable(_tfn)):
            _tfn()
    print(f"FAILED: {len(FAILED)}")
    sys.exit(1 if FAILED else 0)
