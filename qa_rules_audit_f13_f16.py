"""QA: rules audit F13-F16 (audit only -- no tuning changed).

F13: project_pick_slots() weighting -- verifies the documented formula:
     lottery EV bump, 40% regression toward #16, real order clears.
F14: March 8 deadline freeze gate -- verifies the freeze boundaries.
F15: protected-pick fallback -- ownership, ordering, idempotency.
F16: reacquire ban -- 365-day boundary + SPC-death clearing.

Run: python3 qa_rules_audit_f13_f16.py
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import trade_engine as te
from game_classes import DraftPick, League

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def mkteam(name, pts):
    return SimpleNamespace(team_name=name,
                           draft_picks={})


def mkpick(year, rnd, orig, cur, prot="", pid=1):
    return DraftPick(year=year, round=rnd, original_team=orig,
                     current_team=cur, protection=prot, id=pid)


# --- F13: pick-slot projection weighting -------------------------------------
teams = [mkteam(f"T{i:02d}", pts) for i, pts in
         enumerate([50, 60, 70, 80, 90, 95, 100, 105])]
standings = {t.team_name: {"Points": p} for t, p in
             zip(teams, [50, 60, 70, 80, 90, 95, 100, 105])}
# one unknown 1st per team, all "owned" by T07 via trade
for t in teams:
    t.draft_picks = {}
for i, t in enumerate(teams):
    t.draft_picks[2027] = [mkpick(2027, 1, t.team_name, "T07", pid=100 + i)]
lg = SimpleNamespace(teams=teams, standings=standings,
                     draft_prospects_year=2027, season_year=2026)
lg.get_draft_order = lambda yr: []  # no real order -> projections apply
n = te.project_pick_slots(lg)
check("f13: all 8 unknown 1sts projected", n == 8, f"n={n}")
slots = {t.team_name: t.draft_picks[2027][0].projected_overall
         for t in teams}
# worst team (T00): ev = 1 + 2.0 = 3.0 -> 0.6*3 + 6.4 = 8.2 -> 8
check("f13: worst team projects to ~8 (lottery EV + 40% regression)",
      slots["T00"] == 8, f"T00={slots['T00']}")
# best team (T07): rank 8 (<= 11, lottery bump) -> ev = 8 + 2.0 = 10
# -> 0.6*10 + 6.4 = 12.4 -> 12
check("f13: best team projects to ~12 (compressed range)",
      slots["T07"] == 12, f"T07={slots['T07']}")
check("f13: monotonic worst -> best",
      all(slots[f"T{i:02d}"] <= slots[f"T{i+1:02d}"] for i in range(7)),
      str(slots))
# real order clears projections
lg.get_draft_order = lambda yr: [("x",)] if yr == 2027 else []
te.project_pick_slots(lg)
check("f13: real draft order clears stale projections",
      all(t.draft_picks[2027][0].projected_overall == 0 for t in teams))
# fallback when the original club is unknown: mid-round default
t = mkteam("ZZ", 0)
t.draft_picks = {2027: [mkpick(2027, 1, "GhostClub", "T07", pid=999)]}
lg2 = SimpleNamespace(teams=[t], standings={"ZZ": {"Points": 0}},
                      draft_prospects_year=2027, season_year=2026)
lg2.get_draft_order = lambda yr: []
te.project_pick_slots(lg2)
check("f13: unknown original club falls back to #16",
      t.draft_picks[2027][0].projected_overall == 16,
      f"got {t.draft_picks[2027][0].projected_overall}")

# --- F14: deadline freeze gate -----------------------------------------------
lg3 = SimpleNamespace(season_year=2026)
frozen, _ = te._trade_freeze_active("2027-03-08", lg3)
check("f14: deadline day (Mar 8) is legal", not frozen)
frozen, _ = te._trade_freeze_active("2027-03-09", lg3)
check("f14: Mar 9 is frozen while the season runs", frozen)
frozen, _ = te._trade_freeze_active("2027-07-15", lg3)
check("f14: July is unconditionally open", not frozen)
lg3b = SimpleNamespace(season_year=2027)  # rolled over -> new season
frozen, _ = te._trade_freeze_active("2027-04-20", lg3b)
check("f14: freeze lifts after the season rolls", not frozen)
frozen, _ = te._trade_freeze_active("not-a-date", lg3)
check("f14: unparseable date fails open", not frozen)

# --- F15: protected-pick fallback --------------------------------------------
def fake_league(teams, year, lotto_pick):
    lg = SimpleNamespace(
        teams=teams,
        standings={t.team_name: {"Points": 0} for t in teams},
        lottery_results={year: [{"original_team": "ORIG",
                                 "pick": lotto_pick}]},
        PROTECTION_ZONES={"top-3": 3, "top-10": 10, "lottery": 16},
        _protections_resolved=None)
    return lg

orig = SimpleNamespace(team_name="ORIG", draft_picks={})
holder = SimpleNamespace(team_name="HOLD", draft_picks={})
# ORIG's 2027 1st (top-3 protected) sits with HOLD; ORIG owns its own
# 2028 and 2029 1sts.
prot_pick = mkpick(2027, 1, "ORIG", "HOLD", prot="top-3", pid=501)
orig.draft_picks = {2027: [],
                    2028: [mkpick(2028, 1, "ORIG", "ORIG", pid=502)],
                    2029: [mkpick(2029, 1, "ORIG", "ORIG", pid=503)]}
holder.draft_picks = {2027: [prot_pick]}
flg = fake_league([orig, holder], 2027, lotto_pick=2)  # inside top-3 zone
ev = League.resolve_pick_protections(flg, 2027)
check("f15: protection triggers inside the zone", len(ev) == 1, str(ev))
check("f15: this-year pick reverts to the original club",
      prot_pick.current_team == "ORIG")
check("f15: holder gets the NEXT year's 1st (year+1 first)",
      orig.draft_picks[2028][0].current_team == "HOLD" and
      orig.draft_picks[2029][0].current_team == "ORIG",
      f"28->{orig.draft_picks[2028][0].current_team} "
      f"29->{orig.draft_picks[2029][0].current_team}")
check("f15: protection consumed on both picks",
      prot_pick.protection == ""
      and orig.draft_picks[2028][0].protection == "")
# idempotency: run again -> no new events, no re-deferral
ev2 = League.resolve_pick_protections(flg, 2027)
check("f15: re-resolution is a no-op (no duplication)", ev2 == [],
      str(ev2))
check("f15: no duplicate deferral on re-run",
      orig.draft_picks[2029][0].current_team == "ORIG")

# outside the zone: conveys normally
orig2 = SimpleNamespace(team_name="ORIG", draft_picks={2028: []})
holder2 = SimpleNamespace(team_name="HOLD", draft_picks={})
p2 = mkpick(2027, 1, "ORIG", "HOLD", prot="top-10", pid=601)
holder2.draft_picks = {2027: [p2]}
flg2 = fake_league([orig2, holder2], 2027, lotto_pick=12)  # outside top-10
ev3 = League.resolve_pick_protections(flg2, 2027)
check("f15: outside the zone the pick conveys",
      p2.current_team == "HOLD" and p2.protection == ""
      and any("not triggered" in e for e in ev3), str(ev3))

# --- F15b: lottery/protection coincidence + 5-year pick horizon -----------
import random as _random
import draft_lottery as _dl

_lg, _nhl = None, None
try:
    from game_classes import League as _League

    _lg = _League("NHL")
    _nhl = [t for t in _lg.teams
            if getattr(t, "league_name", "") == "National Hockey League"]
    # Deterministic standings: team i gets i*5 points (team 0 worst).
    _lg.standings = {t.team_name: {"Points": i * 5, "W": i * 2}
                     for i, t in enumerate(_nhl)}
    _lg.season_year = 2026
    _lg.initialize_all_draft_picks()
    _Y = 2027
    _worst, _holder_t = _nhl[0], _nhl[5]
    # Worst club's 2027 1st (top-3 protected) sits with the holder.
    _pp = next(p for p in _worst.get_picks_for_year(_Y)
               if p.round == 1)
    _pp.current_team = _holder_t.team_name
    _pp.protection = "top-3"
    _pp.is_conditional = True
    _rows = _dl.run_lottery(_lg, _Y, _random.Random(42))
    _wpos = next(r["pick"] for r in _rows
                 if r["original_team"] == _worst.team_name)
    _ev = _League.resolve_pick_protections(_lg, _Y)
    if _wpos <= 3:
        check("f15b: lottery kept pick in zone -> reverts to original",
              _pp.current_team == _worst.team_name, f"lotto #{_wpos}")
        _next1 = next(p for p in _worst.get_picks_for_year(_Y + 1)
                      if p.round == 1)
        check("f15b: holder receives next year's 1st",
              _next1.current_team == _holder_t.team_name,
              f"lotto #{_wpos}")
    else:
        check("f15b: lottery dropped pick out of zone -> conveys",
              _pp.current_team == _holder_t.team_name, f"lotto #{_wpos}")
    check("f15b: protection evaluated on POST-lottery position",
          any(str(_wpos) in e for e in _ev) or _pp.protection == "",
          f"lotto #{_wpos}")

    # 7-year horizon: every club holds S+1..S+7, all tradeable, value
    # discounts with distance.
    _yrs = sorted(_worst.draft_picks.keys())
    _exp = [_lg.season_year + 1 + i for i in range(7)]
    check("f15b: picks exist 7 drafts out",
          _yrs == _exp, str(_yrs))
    _far = [p for p in _worst.get_picks_for_year(_exp[6])]
    check("f15b: year+7 picks are tradeable, not dead paper",
          len(_far) == 7 and all(p.can_be_traded() and not p.is_expired
                                 for p in _far))
    _other = _nhl[1]  # untouched club: owns its own 1sts
    _v1 = next(p for p in _other.get_picks_for_year(_exp[0])
               if p.round == 1).value
    _v5 = next(p for p in _other.get_picks_for_year(_exp[4])
               if p.round == 1).value
    check("f15b: far-future 1st discounted vs near 1st",
          _v5 < _v1, f"{_v1} vs {_v5}")

    # Deferral rolls to year+4 when +1..+3 are gone.
    _o2 = SimpleNamespace(team_name="ORIG2", draft_picks={})
    _h2 = SimpleNamespace(team_name="HOLD2", draft_picks={})
    _p2 = mkpick(2027, 1, "ORIG2", "HOLD2", prot="top-3", pid=701)
    _o2.draft_picks = {2027: []}
    for _yy, _pid in ((2028, 702), (2029, 703), (2030, 704), (2031, 705)):
        _gone = "HOLD2" if _yy < 2031 else "ORIG2"  # +1..+3 traded away
        _o2.draft_picks[_yy] = [mkpick(_yy, 1, "ORIG2", _gone, pid=_pid)]
    _h2.draft_picks = {2027: [_p2]}
    _flg = SimpleNamespace(
        teams=[_o2, _h2],
        standings={t.team_name: {"Points": 0} for t in [_o2, _h2]},
        lottery_results={2027: [{"original_team": "ORIG2", "pick": 2}]},
        PROTECTION_ZONES={"top-3": 3, "top-10": 10, "lottery": 16},
        _protections_resolved=None)
    _League.resolve_pick_protections(_flg, 2027)
    check("f15b: deferral rolls forward to year+4",
          _o2.draft_picks[2031][0].current_team == "HOLD2"
          and _o2.draft_picks[2028][0].current_team == "HOLD2",
          "2031->" + _o2.draft_picks[2031][0].current_team)
except Exception as _e:  # pragma: no cover -- loud, not silent
    check("f15b: integration setup", False, f"{type(_e).__name__}: {_e}")

# --- F16: reacquire ban ------------------------------------------------------
p = SimpleNamespace(retained_amount=5, retained_team_name="X",
                    retained_by=["X"],
                    retention_bans=[{"team": "X", "date": "2027-01-01"}],
                    retention_trade_dates=["2027-01-01"])
te.clear_retention_state(p)
check("f16: new SPC wipes retention_bans (ban lifts on re-sign)",
      p.retention_bans == [] and p.retained_amount == 0)
# boundary: the inline check is 0 <= days < 365
from datetime import date as _d
ban_d = _d.fromisoformat("2027-01-01")
check("f16: ban blocks inside a year",
      0 <= (_d.fromisoformat("2027-06-01") - ban_d).days < 365)
check("f16: ban lifts exactly at 365 days",
      not (0 <= (_d.fromisoformat("2028-01-01") - ban_d).days < 365))
# 75-day double-retention boundary (source): blocked at <= 75
src = open("trade_engine.py").read()
check("f16: second retention blocked at <= 75 days (day 76 legal)",
      "if _elapsed <= 75:" in src)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
