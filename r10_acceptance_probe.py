#!/usr/bin/env python3
"""R10 acceptance probe: adversarial verification of the three reviewer
blocking findings.

  FIX 1 -- rumor->traded detector vs real engine trade labels
  FIX 2 -- fired-then-rehired coach must resolve "fired", never "retained"
  FIX 3 -- media_engine narrative_spawn (hot_seat / trade_rumor) routed
           through route_events must open a story arc

HARDENING (the old fixtures masked the original bugs):
- Trade fixtures use REAL engine labels via trade_engine.asset_label
  (verified headless-importable): "Name (POS, Tier)", with optional
  " [$X.XXM retained]". asset_label's DraftPick branch also emits
  " [proj. Tier]" (trade_engine.py:1780-1794) -- covered as a
  non-matching entry inside the multi-asset deal.
- The oracle reimplements the FIXED detector semantics (exact name OR
  name+" (" prefix -- never substring) instead of trusting the detector.
- The probe NEVER imports tuning constants from story_arcs
  (HOT_SEAT_HEAT_WINDOW_DAYS / ARC_FOLLOWUP_WINDOW_DAYS would make the
  boundary checks circular). HEAT_WINDOW_DAYS / FOLLOWUP_WINDOW_DAYS
  below are probe-owned literals derived from the rigged fixture dates.
- Adversarial rigs: "Rory Rumor Jr" false positive, name-contained-but-
  not-prefixed entry, fired-then-rehired-same-day, media_engine-path
  initiation + dedup vs the daily_news bucket, 14-day follow-up
  boundary (day 13 delivers / day 15 does not), multi-player deal.

Writes r10_acceptance_results.json next to this file.
Exit 0 on ACCEPT, 1 on REJECT.
"""
import sys
import os
import types
import json
import random
from datetime import date, timedelta, datetime, timezone

_REPO = os.environ.get("R10_REPO", os.path.expanduser("~/workspace/hockey-manager-r10"))
sys.path.insert(0, _REPO)

# Stub dressing_room before story_arcs can lazily import it: the real
# module needs a UI toolkit (absent headless). The stub carries the
# engine's firing record in the exact shape fire_coach() writes.
_fake_dr = types.ModuleType("dressing_room")
_fake_dr.COACH_CAROUSEL = []
sys.modules["dressing_room"] = _fake_dr

import daily_news as dn
import story_arcs as sa
import media_engine as me
from narrative_ledger import get_ledger
from trade_engine import asset_label as _real_asset_label, CompletedTrade

# Probe-owned literals -- deliberately NOT imported from story_arcs
# (circular oracle). Derived from the rigged fixture dates below:
# arcs open on DAY; the retained verdict is asserted at DAY+21 and
# asserted absent at DAY+20; follow-ups must surface within 14 days of
# the resolving event.
HEAT_WINDOW_DAYS = 21
FOLLOWUP_WINDOW_DAYS = 14

DAY = date(2027, 1, 4)  # mid-season news day


def _pos(v):
    return types.SimpleNamespace(value=v)


def plabel(name, pos="C", retained=0):
    """A REAL engine asset label: trade_engine.asset_label() emits
    "Name (POS, Tier)" plus " [$X.XXM retained]" when retained > 0
    (trade_engine.py:1778-1810). This is what execute_trade writes
    into CompletedTrade a_gave/b_gave -- never a bare name."""
    return _real_asset_label(types.SimpleNamespace(
        full_name=name, primary_position=_pos(pos),
        retained_amount=retained))


# Sanity: the imported labeler really produces the engine formats.
assert plabel("Rory Rumor") == "Rory Rumor (C, Decent)", plabel("Rory Rumor")
assert plabel("Rory Rumor", retained=1500000) == \
    "Rory Rumor (C, Decent) [$1.50M retained]"


def oracle_names_player(entry, player):
    """The FIXED detector's semantics, reimplemented independently:
    exact name OR name followed by " (". Never substring -- the old
    probe oracle ("Rory Rumor" in gave) would match "Rory Rumor Jr" and
    any entry merely containing the name."""
    g = (entry or "").strip()
    if not g or not player:
        return False
    return g == player or g.startswith(player + " (")


def mkplayer(name, pos="C", ovr=80, gp=20, goals=0, assists=0, pid=None,
             **kw):
    parts = name.split()
    p = types.SimpleNamespace(first_name=parts[0],
                              last_name=" ".join(parts[1:]) or parts[0])
    p.id = pid if pid is not None else abs(hash(name)) % 10 ** 9
    p.primary_position = pos
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
                                     season_year=season_year,
                                     media_narratives=[]),
        _daily_news_recent={},
        trade_history=[],
        add_news=lambda s: surfaced.append(s))
    app._surfaced = surfaced
    return app


def arcs_of(app, kind=None):
    return get_ledger(app).open_arcs(kind)


def resolved_of(app):
    return get_ledger(app).resolved_arcs()


CHECKS = []


def check(name, cond):
    CHECKS.append({"name": name, "pass": bool(cond)})
    print(("PASS " if cond else "FAIL ") + name)


def rumor_app(player_name="Rory Rumor", pid=101, team_name="Avalanche"):
    """An app with a trade-rumor arc freshly opened by the daily_news
    bucket for a rigged underperforming star."""
    rp = mkplayer(player_name, pos="C", ovr=85, gp=20, goals=2, assists=3,
                  pid=pid)
    t = mkteam(team_name, [rp])
    app = mkapp(t)
    tapp = types.SimpleNamespace(
        league=types.SimpleNamespace(teams=[t]),
        _daily_news_recent={},
        narrative_ledger=get_ledger(app))
    stories = dn._controversies(tapp, DAY, random.Random(12))
    assert len(stories) == 1, "rumor story did not fire"
    assert len(arcs_of(app, "trade_rumor")) == 1, "rumor arc did not open"
    return app, rp, t


def hotseat_app(coach_name="Chip Chill", team_name="Frostbite"):
    """An app with a hot-seat arc freshly opened by the daily_news
    bucket on a rigged 2-8-0 / conf-30 team."""
    coach = mkcoach(coach_name)
    t = mkteam(team_name,
               [mkplayer("Fill Er", ovr=75, gp=10, goals=2, assists=2)],
               coach=coach, wins=2, losses=8, otl=0, conf=30.0)
    app = mkapp(t)
    stories = dn._coach_stories(app, DAY, random.Random(11))
    assert len(stories) == 1, "hot-seat story did not fire"
    assert len(arcs_of(app, "hot_seat")) == 1, "hot-seat arc did not open"
    return app, coach, t

# ===========================================================================
# FIX 1 -- trade detector reads real engine labels
# ===========================================================================

# A1: plain "Name (POS, Tier)" label resolves the arc.
app, rp, t = rumor_app()
t_wolves = mkteam("Wolves", [mkplayer("Fill Er", ovr=75, gp=20, goals=4,
                                      assists=4)])
app.league.teams.append(t_wolves)
gave_a1 = [plabel("Rory Rumor")]
app.trade_history.append(CompletedTrade(
    date="2027-01-21", team_a="Avalanche", team_b="Wolves",
    a_gave=gave_a1, b_gave=[plabel("Fill Er")],
    summary="Rory Rumor to Wolves"))
t.roster.remove(rp)
t_wolves.roster.append(rp)
check("F1 oracle: plain label matches fixed semantics",
      oracle_names_player(gave_a1[0], "Rory Rumor"))
n = sa.process_day(app, DAY + timedelta(days=18))
res = resolved_of(app)[0]["facts"] if resolved_of(app) else {}
check("F1a plain asset_label resolves 'traded'",
      n == 1 and res.get("resolution") == "traded"
      and res.get("new_team") == "Wolves"
      and res.get("old_team") == "Avalanche")

# A2: " [$X.XXM retained]" suffix variant resolves.
app, rp, t = rumor_app()
t_wolves = mkteam("Wolves", [mkplayer("Fill Er", ovr=75, gp=20, goals=4,
                                      assists=4)])
app.league.teams.append(t_wolves)
gave_a2 = [plabel("Rory Rumor", retained=1500000)]
app.trade_history.append(CompletedTrade(
    date="2027-01-21", team_a="Avalanche", team_b="Wolves",
    a_gave=gave_a2, b_gave=[plabel("Fill Er")],
    summary="Rory Rumor (retained) to Wolves"))
check("F1 oracle: retained-suffix label matches fixed semantics",
      oracle_names_player(gave_a2[0], "Rory Rumor"))
n = sa.process_day(app, DAY + timedelta(days=18))
res = resolved_of(app)[0]["facts"] if resolved_of(app) else {}
check("F1b retained-suffix label resolves 'traded'",
      n == 1 and res.get("resolution") == "traded"
      and res.get("new_team") == "Wolves")

# A3: multi-player deal -- rumor subject among several assets, including
# a DraftPick-format "[proj. Tier]" entry (must not confuse the matcher).
app, rp, t = rumor_app()
t_wolves = mkteam("Wolves", [mkplayer("Fill Er", ovr=75, gp=20, goals=4,
                                      assists=4)])
app.league.teams.append(t_wolves)
gave_a3 = [plabel("Grinder Guy", "LW"),
           plabel("Rory Rumor", retained=2000000),
           "2027 2nd round pick (unprotected) [proj. Star]",
           plabel("Third Wheel", "RD")]
for g in gave_a3:
    pass  # entries asserted as a group below
check("F1 oracle multi-deal: only the subject's own label matches",
      [oracle_names_player(g, "Rory Rumor") for g in gave_a3]
      == [False, True, False, False])
app.trade_history.append(CompletedTrade(
    date="2027-01-21", team_a="Avalanche", team_b="Wolves",
    a_gave=gave_a3, b_gave=[plabel("Fill Er")],
    summary="blockbuster"))
n = sa.process_day(app, DAY + timedelta(days=18))
res = resolved_of(app)[0]["facts"] if resolved_of(app) else {}
check("F1c multi-asset deal resolves 'traded' with the right club",
      n == 1 and res.get("resolution") == "traded"
      and res.get("new_team") == "Wolves"
      and res.get("old_team") == "Avalanche")

# A4: adversarial false positive -- "Rory Rumor Jr" must NOT match
# "Rory Rumor" (the old substring oracle would have matched).
jr_label = plabel("Rory Rumor Jr")
check("F1 oracle: 'Rory Rumor Jr (C, ...)' does not match 'Rory Rumor'",
      not oracle_names_player(jr_label, "Rory Rumor"))
app, rp, t = rumor_app()
t_wolves = mkteam("Wolves", [mkplayer("Fill Er", ovr=75, gp=20, goals=4,
                                      assists=4)])
app.league.teams.append(t_wolves)
app.trade_history.append(CompletedTrade(
    date="2027-01-21", team_a="Avalanche", team_b="Wolves",
    a_gave=[jr_label], b_gave=[plabel("Fill Er")],
    summary="Rory Rumor Jr to Wolves"))
n = sa.process_day(app, DAY + timedelta(days=18))
check("F1d similarly-named player does not resolve the arc "
      "(no false positive)",
      n == 0 and len(arcs_of(app, "trade_rumor")) == 1)

# A5: adversarial false positive -- entry merely CONTAINS the name but
# does not start with it (old substring oracle matched this too).
contained = "X Rory Rumor (C, Decent)"
check("F1 oracle: entry containing the name mid-string does not match",
      not oracle_names_player(contained, "Rory Rumor"))
app, rp, t = rumor_app()
t_wolves = mkteam("Wolves", [mkplayer("Fill Er", ovr=75, gp=20, goals=4,
                                      assists=4)])
app.league.teams.append(t_wolves)
app.trade_history.append(CompletedTrade(
    date="2027-01-21", team_a="Avalanche", team_b="Wolves",
    a_gave=[contained], b_gave=[plabel("Fill Er")],
    summary="weird entry"))
n = sa.process_day(app, DAY + timedelta(days=18))
check("F1e mid-string containment does not resolve the arc",
      n == 0 and len(arcs_of(app, "trade_rumor")) == 1)

# A6: legacy tolerance -- an exact bare-name entry still matches
# (asset_label's str(asset) fallback can emit one).
app, rp, t = rumor_app()
t_wolves = mkteam("Wolves", [mkplayer("Fill Er", ovr=75, gp=20, goals=4,
                                      assists=4)])
app.league.teams.append(t_wolves)
app.trade_history.append(CompletedTrade(
    date="2027-01-21", team_a="Avalanche", team_b="Wolves",
    a_gave=["Rory Rumor"], b_gave=[plabel("Fill Er")],
    summary="legacy format"))
check("F1 oracle: exact bare name still matches",
      oracle_names_player("Rory Rumor", "Rory Rumor"))
n = sa.process_day(app, DAY + timedelta(days=18))
check("F1f exact bare-name entry still resolves (legacy tolerance)",
      n == 1 and resolved_of(app)[0]["facts"].get("resolution")
      == "traded")

# ===========================================================================
# FIX 2 -- fired-then-rehired coach resolves "fired", never "retained"
# ===========================================================================

# B1: the reviewer's exact scenario -- firing recorded 2027-01-15, coach
# re-hired the same day (chair holds him again), scan runs at DAY+21.
# Old code fell through to the 21-day "retained" branch with text
# claiming "the board is standing by its coach". Fixed code resolves
# "fired" on the dated record regardless of the chair.
app, coach, t = hotseat_app()
_fake_dr.COACH_CAROUSEL.append({"coach": coach, "name": "Chip Chill",
                                "reason": "fired", "date": "2027-01-15"})
t.head_coach = coach          # re-hired the same day: chair holds him
t.staff.head_coach = coach
n = sa.process_day(app, DAY + timedelta(days=HEAT_WINDOW_DAYS))
res = resolved_of(app)[0]["facts"] if resolved_of(app) else {}
check("F2a fired-then-rehired resolves 'fired' at day 21",
      n == 1 and res.get("resolution") == "fired"
      and res.get("fired_date") == "2027-01-15")
d = sa.deliver_followups(app, DAY + timedelta(days=HEAT_WINDOW_DAYS))
check("F2b fired follow-up delivered, names coach and club",
      d == 1 and "Chip Chill" in app._surfaced[0]
      and "Frostbite" in app._surfaced[0])
check("F2c never 'retained': arc is closed as fired",
      len(arcs_of(app)) == 0
      and all(r["facts"].get("resolution") != "retained"
              for r in resolved_of(app)))
_fake_dr.COACH_CAROUSEL.clear()

# B2: control -- no firing record, coach survives: retained at the
# window, nothing before it. Probe-owned literal day counts only.
app, coach, t = hotseat_app()
n = sa.process_day(app, DAY + timedelta(days=HEAT_WINDOW_DAYS - 1))
check("F2d control: no verdict one day before the window",
      n == 0 and len(arcs_of(app, "hot_seat")) == 1)
n = sa.process_day(app, DAY + timedelta(days=HEAT_WINDOW_DAYS))
res = resolved_of(app)[0]["facts"] if resolved_of(app) else {}
check("F2e control: 'retained' at the window with no firing record",
      n == 1 and res.get("resolution") == "retained")

# ===========================================================================
# FIX 3 -- media_engine narrative_spawn opens arcs via route_events
# ===========================================================================

# C1: hot-seat narrative routed through route_events opens an arc.
coach = mkcoach("Chip Chill")
t = mkteam("Frostbite",
           [mkplayer("Fill Er", ovr=75, gp=10, goals=2, assists=2)],
           coach=coach, wins=2, losses=8, otl=0, conf=30.0)
app = mkapp(t)
title = "Chip Chill on the hot seat in Frostbite"
app.league.media_narratives.append(
    me.Narrative("hot_seat", "Frostbite", title, []))
ev = {"kind": "narrative_spawn", "team": "Frostbite", "narrative": title}
n = me.route_events(app, [ev], DAY)
check("C1a route_events delivers the narrative_spawn story",
      n == 1 and any("Media notebook:" in s for s in app._surfaced))
arcs = arcs_of(app, "hot_seat")
check("C1b media_engine hot-seat narrative opened an arc",
      len(arcs) == 1
      and arcs[0]["facts"].get("coach_name") == "Chip Chill"
      and arcs[0]["facts"].get("team_name") == "Frostbite"
      and arcs[0]["facts"].get("entity_key") == "coach:Chip Chill")

# C2: dedup -- a same-coach daily_news hot-seat story must NOT
# double-open (open_arc is idempotent per (kind, entity) while open).
dn._coach_stories(app, DAY + timedelta(days=1), random.Random(31))
check("C2 media_engine + daily_news hot-seat -> exactly one arc",
      len(arcs_of(app, "hot_seat")) == 1)

# C3: trade_rumor narrative routed through route_events opens an arc
# with the right player name + id + team.
rp = mkplayer("Rory Rumor", pos="C", ovr=85, gp=20, goals=2, assists=3,
              pid=101)
t2 = mkteam("Avalanche", [rp])
app2 = mkapp(t2)
rtitle = "Rory Rumor trade chatter"
app2.league.media_narratives.append(
    me.Narrative("trade_rumor", "Avalanche", rtitle, [101]))
me.route_events(app2, [{"kind": "narrative_spawn", "team": "Avalanche",
                        "narrative": rtitle}], DAY)
arcs = arcs_of(app2, "trade_rumor")
check("C3 media_engine trade-rumor narrative opened an arc",
      len(arcs) == 1
      and arcs[0]["facts"].get("player_name") == "Rory Rumor"
      and arcs[0]["facts"].get("player_id") == 101
      and arcs[0]["facts"].get("team_name") == "Avalanche"
      and arcs[0]["facts"].get("entity_key") == "player:101")

# C4: other narrative kinds (goalie) open no arc.
app3 = mkapp(t2)
app3.league.media_narratives.append(
    me.Narrative("goalie", "Avalanche", "Goalie controversy brewing", []))
me.route_events(app3, [{"kind": "narrative_spawn", "team": "Avalanche",
                        "narrative": "Goalie controversy brewing"}], DAY)
check("C4 non-arc narrative kind opens no arc",
      len(arcs_of(app3)) == 0)

# C5: orphan / malformed narrative_spawn events: no arc, never raises.
app4 = mkapp(t2)
me.route_events(app4, [{"kind": "narrative_spawn", "team": "Avalanche",
                        "narrative": "no such narrative"}], DAY)
me.route_events(app4, [{"kind": "narrative_spawn"}], DAY)
me.route_events(app4, [], DAY)
me.route_events(app4, None, DAY)
check("C5 orphan/malformed narrative_spawn: no arc, no raise",
      len(arcs_of(app4)) == 0)

# ===========================================================================
# 14-day follow-up boundary (probe-owned literal day counts)
# ===========================================================================

def fired_app():
    """Hot-seat arc resolved 'fired' on 2027-01-15."""
    app, coach, t = hotseat_app()
    _fake_dr.COACH_CAROUSEL.append({"coach": coach, "name": "Chip Chill",
                                    "reason": "fired",
                                    "date": "2027-01-15"})
    t.head_coach = None
    t.staff.head_coach = None
    n = sa.process_day(app, date(2027, 1, 15))
    assert n == 1, "firing did not resolve"
    _fake_dr.COACH_CAROUSEL.clear()
    return app


# D1: resolution delivered 13 days later -> follow-up surfaces.
app = fired_app()
d = sa.deliver_followups(app, date(2027, 1, 15)
                         + timedelta(days=FOLLOWUP_WINDOW_DAYS - 1))
check("D1 follow-up delivered 13 days after resolution",
      d == 1 and len(app._surfaced) == 1
      and "Chip Chill" in app._surfaced[0])

# D2: delivery impossible past day 14 -> no follow-up; the arc is
# handled gracefully (stays resolved, nothing delivered, no raise).
app = fired_app()
d = sa.deliver_followups(app, date(2027, 1, 15)
                         + timedelta(days=FOLLOWUP_WINDOW_DAYS + 1))
check("D2 no follow-up 15 days after resolution (past the window)",
      d == 0 and len(app._surfaced) == 0)
check("D2b arc handled gracefully: still resolved, not closed, no crash",
      len(resolved_of(app)) == 1
      and resolved_of(app)[0]["facts"].get("resolution") == "fired"
      and len(arcs_of(app)) == 0)

# ===========================================================================
# Verdict + results file
# ===========================================================================
failed = [c for c in CHECKS if not c["pass"]]
verdict = "REJECT" if failed else "ACCEPT"
results = {
    "probe": "r10_acceptance_probe.py",
    "verdict": verdict,
    "generated": datetime.now(timezone.utc).isoformat(),
    "checks": CHECKS,
    "failed": [c["name"] for c in failed],
}
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "r10_acceptance_results.json")
with open(out_path, "w") as fh:
    json.dump(results, fh, indent=2)
print()
print(f"{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
print(f"verdict: {verdict} -> {out_path}")
sys.exit(1 if failed else 0)
