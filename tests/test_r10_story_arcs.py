#!/usr/bin/env python3
"""R10: multi-day story arcs (M item).

Conventions: synthetic SimpleNamespace app/team/player fixtures (same shape
as the R8a-h/R9 tests); assertions on premises and ledger state, not
phrasing. dressing_room can't be imported headless (module-level
customtkinter import), so the coach-firing record (COACH_CAROUSEL) is
stubbed via sys.modules -- the detector reads only the record's
name/reason/date fields, the same fields the real fire_coach() writes.

Covered:
  1. initiation is independent of resolvability (arcs open even when the
     resolution never comes: retained coach, untraded player)
  2. hot-seat -> fired (carousel record) -> one-shot follow-up
  3. hot-seat -> retained past the 21-day heat window
  4. rumor -> traded (real CompletedTrade log) -> follow-up names new club
  5. rumor -> deadline passes, player still on club -> stayed follow-up
  6. milestone countdown -> career total reaches the mark -> achieved
  7. injury -> engine healed state -> returned follow-up
  8. arc dedup: re-firing the initiating story opens no second arc
  9. fail-closed: junk identities open no arcs; unprovable resolutions
     emit no follow-ups
 10. determinism: same date -> same follow-up text
 11. crash battery: None/junk inputs never raise
"""
import sys
import os
import types
import random
from datetime import date, timedelta

_REPO = os.environ.get(
    "R10_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

# Stub dressing_room before story_arcs can lazily import it: the real
# module needs customtkinter (absent headless). The stub carries the
# engine's firing record in the exact shape remember_coach() writes.
_fake_dr = types.ModuleType("dressing_room")
_fake_dr.COACH_CAROUSEL = []
sys.modules["dressing_room"] = _fake_dr

import daily_news as dn
import story_arcs as sa
from narrative_ledger import get_ledger, NarrativeLedger
import trade_engine as te


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed += 1
check.failed = 0


DAY = date(2027, 1, 4)  # mid-season news day


def mkplayer(name, pos="C", ovr=80, gp=20, goals=0, assists=0, pid=None,
             **kw):
    parts = name.split()
    p = types.SimpleNamespace(first_name=parts[0],
                              last_name=" ".join(parts[1:]) or parts[0])
    p.id = pid if pid is not None else abs(hash(name)) % 10 ** 9
    p.primary_position = pos  # plain string: _pos falls back to str(pp)
    p.overall = float(ovr)
    p.stats = types.SimpleNamespace(games_played=gp, goals=goals,
                                    assists=assists, save_percentage=None)
    p.contract = types.SimpleNamespace(years_remaining=3)
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def mkcoach(name):
    return types.SimpleNamespace(name=name,
                                 id=abs(hash(name)) % 10 ** 9)


def _pos(v):
    return types.SimpleNamespace(value=v)


def mklabel(name, pos="C", retained=0):
    """A REAL engine asset label via trade_engine.asset_label -- "Name
    (POS, Tier)" with optional " [$X.XXM retained]" -- never a bare
    name, matching what execute_trade writes into CompletedTrade
    a_gave/b_gave."""
    return te.asset_label(types.SimpleNamespace(
        full_name=name, primary_position=_pos(pos),
        retained_amount=retained))


def mkteam(name, players, coach=None, wins=5, losses=5, otl=0, conf=70.0):
    t = types.SimpleNamespace(team_name=name, roster=list(players),
                              wins=wins, losses=losses, ot_losses=otl,
                              board_confidence=conf)
    if coach is not None:
        t.head_coach = coach
        t.staff = types.SimpleNamespace(head_coach=coach)
    return t


def mkapp(*teams, season_year=2026):
    surfaced = []
    app = types.SimpleNamespace(
        league=types.SimpleNamespace(teams=list(teams),
                                     season_year=season_year),
        _daily_news_recent={},
        trade_history=[],
        add_news=lambda s: surfaced.append(s))
    app._surfaced = surfaced
    return app


def arcs_of(app, kind=None):
    return get_ledger(app).open_arcs(kind)


def arc_facts(app, kind):
    a = arcs_of(app, kind)
    return a[0]["facts"] if a else None


# ---------------------------------------------------------------------------
# 1. Initiation is independent of resolvability
# ---------------------------------------------------------------------------
coach = mkcoach("Chip Chill")
t_hot = mkteam("Frostbite", [mkplayer("Fill Er", ovr=75, gp=10,
                                      goals=2, assists=2)],
               coach=coach, wins=2, losses=8, otl=0, conf=30.0)
app = mkapp(t_hot)
stories = dn._coach_stories(app, DAY, random.Random(11))
check("1a hot-seat story fires on rigged 2-8-0/conf-30 team",
      len(stories) == 1)
f = arc_facts(app, "hot_seat")
check("1b hot-seat story opened an arc (no resolvability consulted)",
      f is not None and f.get("coach_name") == "Chip Chill"
      and f.get("team_name") == "Frostbite"
      and f.get("status") == "open")
# The coach is NEVER fired: the arc must still be open just before the
# heat window closes (initiation didn't depend on resolvability).
n = sa.process_day(app, DAY + timedelta(days=sa.HOT_SEAT_HEAT_WINDOW_DAYS - 1))
check("1c retained coach: no resolution before the heat window "
      "(arc untouched)", n == 0 and len(arcs_of(app)) == 1)

# Rumor arc opens even though no trade will ever happen.
rp = mkplayer("Rory Rumor", pos="C", ovr=85, gp=20, goals=2, assists=3,
              pid=101)
t_rumor = mkteam("Avalanche", [rp])
app2 = mkapp(t_rumor)
tapp = types.SimpleNamespace(
    league=types.SimpleNamespace(teams=[t_rumor]),
    _daily_news_recent={},
    narrative_ledger=get_ledger(app2))
stories = dn._controversies(tapp, DAY, random.Random(12))
check("1d rumor story fires", len(stories) == 1)
f = arc_facts(app2, "trade_rumor")
check("1e rumor arc opened with zero trades on the log",
      f is not None and f.get("player_name") == "Rory Rumor"
      and len(app2.trade_history) == 0)

# ---------------------------------------------------------------------------
# 2. hot-seat -> fired
# ---------------------------------------------------------------------------
_fake_dr.COACH_CAROUSEL.append({"coach": coach, "name": "Chip Chill",
                                "reason": "fired", "date": "2027-01-15"})
t_hot.head_coach = None
t_hot.staff.head_coach = None
n = sa.process_day(app, DAY + timedelta(days=12))
check("2a firing detected from the carousel record", n == 1)
check("2b arc moved to resolved/fired",
      len(arcs_of(app)) == 0
      and get_ledger(app).resolved_arcs()[0]["facts"]["resolution"]
      == "fired")
d = sa.deliver_followups(app, DAY + timedelta(days=12))
check("2c fired follow-up delivered via add_news",
      d == 1 and len(app._surfaced) == 1
      and "Chip Chill" in app._surfaced[0]
      and "Frostbite" in app._surfaced[0])
check("2d follow-up burned a per-arc one-shot mark",
      any(k[0] == "coach:Chip Chill" and k[1].startswith("arc_hot_seat#")
          for k in app._daily_news_recent))
d2 = sa.deliver_followups(app, DAY + timedelta(days=13))
check("2e one-shot: no second delivery", d2 == 0
      and len(app._surfaced) == 1)
_fake_dr.COACH_CAROUSEL.clear()

# ---------------------------------------------------------------------------
# 3. hot-seat -> retained past the heat window
# ---------------------------------------------------------------------------
coach2 = mkcoach("Gus Glacial")
t_hot2 = mkteam("Blizzards",
                [mkplayer("Fill Er", ovr=75, gp=10, goals=2, assists=2)],
                coach=coach2, wins=2, losses=8, otl=0, conf=30.0)
app3 = mkapp(t_hot2)
dn._coach_stories(app3, DAY, random.Random(13))
d21 = DAY + timedelta(days=sa.HOT_SEAT_HEAT_WINDOW_DAYS)
n = sa.process_day(app3, d21)
check("3a retained: resolution fires at the heat-window boundary", n == 1)
res = get_ledger(app3).resolved_arcs()[0]["facts"]
check("3b resolution is 'retained' with the coach named",
      res["resolution"] == "retained" and res["coach_name"] == "Gus Glacial")
d = sa.deliver_followups(app3, d21)
check("3c retained follow-up delivered",
      d == 1 and "Gus Glacial" in app3._surfaced[0]
      and "Blizzards" in app3._surfaced[0])
# Just before the window: no resolution.
coach3 = mkcoach("Pete Patient")
t_hot3 = mkteam("Chillers",
                [mkplayer("Fill Er", ovr=75, gp=10, goals=2, assists=2)],
                coach=coach3, wins=2, losses=8, otl=0, conf=30.0)
app3b = mkapp(t_hot3)
dn._coach_stories(app3b, DAY, random.Random(14))
n = sa.process_day(app3b, DAY + timedelta(
    days=sa.HOT_SEAT_HEAT_WINDOW_DAYS - 1))
check("3d no retained verdict one day before the window", n == 0)

# ---------------------------------------------------------------------------
# 4. rumor -> traded
# ---------------------------------------------------------------------------
t_wolves = mkteam("Wolves", [mkplayer("Fill Er", ovr=75, gp=20, goals=4,
                                      assists=4)])
app2.league.teams.append(t_wolves)
app2.trade_history.append(te.CompletedTrade(
    date="2027-01-21", team_a="Avalanche", team_b="Wolves",
    a_gave=[mklabel("Rory Rumor", "C")],
    b_gave=[mklabel("Fill Er", "C")],
    summary="Rory Rumor to Wolves"))
t_rumor.roster.remove(rp)
t_wolves.roster.append(rp)
n = sa.process_day(app2, DAY + timedelta(days=18))
check("4a trade detected from the completed-trade log", n == 1)
res = get_ledger(app2).resolved_arcs()[0]["facts"]
check("4b resolution names the destination club",
      res["resolution"] == "traded" and res["new_team"] == "Wolves"
      and res["old_team"] == "Avalanche")
d = sa.deliver_followups(app2, DAY + timedelta(days=18))
check("4c traded follow-up delivered",
      d == 1 and "Rory Rumor" in app2._surfaced[0]
      and "Wolves" in app2._surfaced[0])

# Stale trade (before the arc opened) must NOT resolve it.
rp2 = mkplayer("Sam Spec", pos="C", ovr=84, gp=20, goals=2, assists=2,
               pid=102)
t_storm = mkteam("Storm", [rp2])
app4 = mkapp(t_storm)
tapp4 = types.SimpleNamespace(
    league=types.SimpleNamespace(teams=[t_storm]),
    _daily_news_recent={},
    narrative_ledger=get_ledger(app4))
dn._controversies(tapp4, DAY, random.Random(15))
app4.trade_history.append(te.CompletedTrade(
    date="2026-12-20", team_a="Storm", team_b="Wolves",
    a_gave=[mklabel("Sam Spec", "C")],
    b_gave=[mklabel("Fill Er", "C")], summary="old deal"))
n = sa.process_day(app4, DAY + timedelta(days=5))
check("4d pre-arc trade does not resolve the arc", n == 0
      and len(arcs_of(app4, "trade_rumor")) == 1)

# ---------------------------------------------------------------------------
# 5. rumor -> deadline passes, player stays
# ---------------------------------------------------------------------------
# season_year=2026 -> fallback deadline 2027-03-08 (no schedule).
n = sa.process_day(app4, date(2027, 3, 10))
check("5a stayed: deadline passed with the player still on the club",
      n == 1)
res = get_ledger(app4).resolved_arcs()[0]["facts"]
check("5b resolution is 'stayed'",
      res["resolution"] == "stayed" and res["player_name"] == "Sam Spec")
d = sa.deliver_followups(app4, date(2027, 3, 10))
check("5c stayed follow-up delivered within the window",
      d == 1 and "Sam Spec" in app4._surfaced[0])

# ---------------------------------------------------------------------------
# 6. milestone countdown -> achieved
# ---------------------------------------------------------------------------
mp = mkplayer("Marty Marks", pos="C", ovr=88, gp=20, goals=10, assists=10,
              pid=103, career_goals=497)
t_ms = mkteam("Comets", [mp])
app5 = mkapp(t_ms)
tapp5 = types.SimpleNamespace(
    league=types.SimpleNamespace(teams=[t_ms]),
    _daily_news_recent={},
    narrative_ledger=get_ledger(app5))
stories = dn._milestone_watch(tapp5, DAY, random.Random(16))
check("6a milestone countdown fires at 497/500", len(stories) == 1)
f = arc_facts(app5, "milestone_countdown")
check("6b countdown arc stores the mark",
      f is not None and f.get("mark") == 500)
n = sa.process_day(app5, DAY + timedelta(days=3))
check("6c no resolution at 497", n == 0)
mp.career_goals = 500
n = sa.process_day(app5, DAY + timedelta(days=4))
check("6d achieved detected from the career total", n == 1)
res = get_ledger(app5).resolved_arcs()[0]["facts"]
check("6e resolution carries mark and total",
      res["resolution"] == "achieved" and res["mark"] == 500
      and res["total"] == 500)
d = sa.deliver_followups(app5, DAY + timedelta(days=4))
check("6f milestone follow-up delivered",
      d == 1 and "Marty Marks" in app5._surfaced[0]
      and "500" in app5._surfaced[0])

# ---------------------------------------------------------------------------
# 7. injury -> returned
# ---------------------------------------------------------------------------
ip = mkplayer("Ivan Injured", pos="LW", ovr=82, gp=20, goals=6, assists=6,
              pid=104, is_injured=True, games_remaining_injured=6,
              injury_type="Sprained knee", ir_status="")
t_inj = mkteam("Quakes", [ip])
app6 = mkapp(t_inj)
tapp6 = types.SimpleNamespace(
    league=types.SimpleNamespace(teams=[t_inj]),
    _daily_news_recent={},
    narrative_ledger=get_ledger(app6))
stories = dn._injury_stories(tapp6, DAY, random.Random(17))
check("7a injury story fires with a return estimate", len(stories) == 1
      and "6 games" in stories[0])
f = arc_facts(app6, "injury")
check("7b injury arc opened",
      f is not None and f.get("games_out") == 6
      and f.get("injury_type") == "Sprained knee")
n = sa.process_day(app6, DAY + timedelta(days=5))
check("7c still injured: no resolution", n == 0)
ip.is_injured = False
ip.games_remaining_injured = 0
ip.ir_status = ""
n = sa.process_day(app6, DAY + timedelta(days=6))
check("7d return detected from the healed flags", n == 1)
d = sa.deliver_followups(app6, DAY + timedelta(days=6))
check("7e returned follow-up delivered",
      d == 1 and "Ivan Injured" in app6._surfaced[0])

# Injury bucket gates: no estimate / career-ending / unknown name.
ip2 = mkplayer("Day To Day", pos="C", ovr=82, gp=20, goals=6, assists=6,
               pid=105, is_injured=True, games_remaining_injured=0,
               injury_type="Bruise")
t_inj2 = mkteam("Quakes2", [ip2])
app7f = mkapp(t_inj2)
check("7f no estimate (0 games): no story, no arc",
      dn._injury_stories(app7f, DAY, random.Random(18)) == []
      and len(arcs_of(app7f, "injury")) == 0)
ip3 = mkplayer("Done Deal", pos="C", ovr=82, gp=20, goals=6, assists=6,
               pid=106, is_injured=True, games_remaining_injured=40,
               injury_type="Knee", career_ending_injury=True)
t_inj3 = mkteam("Quakes3", [ip3])
app7 = mkapp(t_inj3)
check("7g career-ending: no story, no arc",
      dn._injury_stories(app7, DAY, random.Random(19)) == []
      and len(arcs_of(app7, "injury")) == 0)

# ---------------------------------------------------------------------------
# 8. arc dedup: re-firing the initiating story opens no second arc
# ---------------------------------------------------------------------------
coach8 = mkcoach("Dan Dup")
t_dup = mkteam("Dupes", [mkplayer("Fill Er", ovr=75, gp=10, goals=2,
                                  assists=2)],
               coach=coach8, wins=2, losses=8, otl=0, conf=30.0)
app8 = mkapp(t_dup)
dn._coach_stories(app8, DAY, random.Random(20))
dn._coach_stories(app8, DAY + timedelta(days=11), random.Random(21))
check("8a two hot-seat stories, one arc",
      len(arcs_of(app8, "hot_seat")) == 1)
check("8b ledger holds exactly one arc event",
      len([e for e in get_ledger(app8).events
           if e.get("kind") == "story_arc"]) == 1)

# ---------------------------------------------------------------------------
# 9. fail-closed
# ---------------------------------------------------------------------------
check("9a unknown arc kind -> no arc",
      sa.note_story_fired(app8, "nope", "k", {}, DAY) is None)
check("9b placeholder coach name -> no arc",
      sa.note_story_fired(app8, "hot_seat", "coach:Unknown Player",
                          {"coach_name": "Unknown Player",
                           "team_name": "Dupes"}, DAY) is None
      and len(arcs_of(app8, "hot_seat")) == 1)
check("9c rumor without player_id -> no arc",
      sa.note_story_fired(app8, "trade_rumor", "player:9",
                          {"player_name": "Ghost G",
                           "team_name": "Dupes"}, DAY) is None)
# Unprovable firing (undated carousel entry) + turned-over chair: expire,
# never a "fired" follow-up.
coach9 = mkcoach("Una Dated")
t_ud = mkteam("Udates", [mkplayer("Fill Er", ovr=75, gp=10, goals=2,
                                  assists=2)],
              coach=coach9, wins=2, losses=8, otl=0, conf=30.0)
app9 = mkapp(t_ud)
dn._coach_stories(app9, DAY, random.Random(22))
_fake_dr.COACH_CAROUSEL.append({"coach": coach9, "name": "Una Dated",
                                "reason": "fired", "date": ""})
t_ud.head_coach = None
t_ud.staff.head_coach = None
n = sa.process_day(app9, DAY + timedelta(days=5))
check("9d undated firing record: no resolution, arc expired silently",
      n == 0 and len(arcs_of(app9)) == 0
      and len(get_ledger(app9).resolved_arcs()) == 0)
_fake_dr.COACH_CAROUSEL.clear()
# Render with unusable names -> None (never surfaced).
bad_arc = {"facts": {"arc_kind": "hot_seat", "resolution": "fired",
                     "coach_name": "Unknown Player",
                     "team_name": "Dupes"}}
check("9e follow-up render fails closed on placeholder names",
      sa._render_followup(bad_arc, random.Random(1)) is None)

# ---------------------------------------------------------------------------
# 10. determinism: same date -> same follow-up text
# ---------------------------------------------------------------------------
def _retained_app(seed_note):
    c = mkcoach("Det Terry")
    t = mkteam("Terms", [mkplayer("Fill Er", ovr=75, gp=10, goals=2,
                                  assists=2)],
               coach=c, wins=2, losses=8, otl=0, conf=30.0)
    a = mkapp(t)
    dn._coach_stories(a, DAY, random.Random(23))
    sa.process_day(a, DAY + timedelta(days=sa.HOT_SEAT_HEAT_WINDOW_DAYS))
    sa.deliver_followups(a, DAY + timedelta(
        days=sa.HOT_SEAT_HEAT_WINDOW_DAYS))
    return a._surfaced[0]

s1 = _retained_app(1)
s2 = _retained_app(2)
check("10a identical rigs on the same date render identical follow-ups",
      s1 == s2)

# ---------------------------------------------------------------------------
# 11. crash battery: never raises
# ---------------------------------------------------------------------------
check("process_day(None) -> 0", sa.process_day(None, DAY) == 0)
check("deliver_followups(None) -> 0", sa.deliver_followups(None, DAY) == 0)
check("note_story_fired(None app) is None or arc",
      sa.note_story_fired(None, "hot_seat", "k",
                          {"coach_name": "", "team_name": ""}, DAY) is None)
check("note_story_fired junk date ok",
      sa.note_story_fired(app8, "hot_seat", "coach:Zed Zed",
                          {"coach_name": "Zed Zed",
                           "team_name": "Dupes"}, "not-a-date") is not None)
bare = types.SimpleNamespace()
check("bare app process_day -> 0", sa.process_day(bare, DAY) == 0)
check("bare app deliver -> 0", sa.deliver_followups(bare, DAY) == 0)

def test_script_checks_all_pass():
    """Aggregate: every module-level check() above recorded zero failures.

    The file's historical script convention runs its checks at import; this
    test makes the result visible to pytest instead of only to the script's
    exit code.
    """
    assert check.failed == 0, f"{check.failed} check(s) failed"


if __name__ == "__main__":
    print()
    if check.failed:
        print(f"{check.failed} FAILURES")
        sys.exit(1)
    print("ALL CHECKS PASSED")
