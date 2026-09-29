"""QA: trade deadline derived from the schedule (audit only -- no tuning changed).

Real NHL rule (CBA 13.12(j)): the deadline falls on the 40th day before
the final day of the regular season. The game derives it as:
    last NHL regular-season game date - 40 days
with a March-8 fallback when the schedule can't answer.

Checks:
  D1: derivation = last RS game - 40 days on a synthetic schedule
  D2: preseason / playoff / non-NHL / NHL_EVENT entries never move it
  D3: fallback Mar 8 (no league; league with season_year but no schedule)
  D4: freeze gate honors the DERIVED date (deadline day legal, day after
      frozen while the season runs)
  D5: TradeDeadlineManager.is_deadline_day matches the derived date
  D6: League._derive_trade_deadline repoints the schedule's deadline event
  D7: automated-season-flow milestone uses the derived date

Run: python3 qa_trade_deadline_derived.py
"""
import sys
from datetime import date, datetime
from types import SimpleNamespace

sys.path.insert(0, ".")

from trade_deadline_manager import (
    trade_deadline_date, TRADE_DEADLINE_LEAD_DAYS,
    TradeDeadlineManager, get_deadline_manager,
)
import trade_engine as te
from game_classes import League
from automated_season_flow import _derived_trade_deadline_date

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def rs_game(day, league="NHL", **kw):
    e = {"date": day, "home_team": "A", "away_team": "B", "league": league}
    e.update(kw)
    return e


check("lead days constant is 40 (CBA)", TRADE_DEADLINE_LEAD_DAYS == 40)

# --- D1: basic derivation ----------------------------------------------------
sched = [rs_game(date(2027, 4, d)) for d in (1, 5, 12)]
lg = SimpleNamespace(schedule=sched, season_year=2026)
dd = trade_deadline_date(lg)
check("D1: deadline = last RS game - 40d",
      dd == date(2027, 4, 12) - __import__("datetime").timedelta(days=40),
      f"got {dd}")
check("D1: Apr 12 2027 -> Mar 3 2027", dd == date(2027, 3, 3), f"got {dd}")

# --- D2: exclusions ----------------------------------------------------------
sched2 = (sched
          + [rs_game(date(2027, 4, 20), preseason=True)]      # later preseason
          + [rs_game(date(2027, 5, 1), playoff={"round": 1})]  # playoff
          + [rs_game(date(2027, 4, 25), league="AHL")]         # other league
          + [(date(2027, 4, 28), "NHL_EVENT",                 # event tuple
              {"type": "trade_deadline"})])
lg2 = SimpleNamespace(schedule=sched2, season_year=2026)
check("D2: preseason/playoff/AHL/event entries don't move it",
      trade_deadline_date(lg2) == date(2027, 3, 3),
      f"got {trade_deadline_date(lg2)}")

# --- D3: fallbacks -----------------------------------------------------------
check("D3: no league -> Mar 8 of deadline year",
      trade_deadline_date(None, deadline_year=2027) == date(2027, 3, 8))
check("D3: league w/ season_year, no schedule -> Mar 8",
      trade_deadline_date(SimpleNamespace(season_year=2026, schedule=[]))
      == date(2027, 3, 8))
check("D3: empty schedule, no year hint -> Mar 8 (some year)",
      trade_deadline_date(SimpleNamespace(schedule=[])).month == 3
      and trade_deadline_date(SimpleNamespace(schedule=[])).day == 8)

# --- D4: freeze gate honors the derived date ---------------------------------
lg3 = SimpleNamespace(schedule=sched, season_year=2026)
frozen, _ = te._trade_freeze_active("2027-03-03", lg3)
check("D4: derived deadline day (Mar 3) is legal", not frozen)
frozen, _ = te._trade_freeze_active("2027-03-04", lg3)
check("D4: day after derived deadline is frozen", frozen)
frozen, _ = te._trade_freeze_active("2027-03-08", lg3)
check("D4: old Mar-8 constant no longer the gate (frozen now)", frozen)
# no-schedule league keeps the Mar-8 fallback gate
lg4 = SimpleNamespace(season_year=2026)
frozen, _ = te._trade_freeze_active("2027-03-08", lg4)
check("D4: fallback gate still Mar 8 without a schedule", not frozen)

# --- D5: manager -------------------------------------------------------------
gm = SimpleNamespace(league=lg3)
mgr = TradeDeadlineManager(gm)
check("D5: manager.deadline_date() is derived",
      mgr.deadline_date() == date(2027, 3, 3), f"got {mgr.deadline_date()}")
check("D5: is_deadline_day true on derived date",
      mgr.is_deadline_day(date(2027, 3, 3)))
check("D5: is_deadline_day false on Mar 8 now",
      not mgr.is_deadline_day(date(2027, 3, 8)))
check("D5: is_trade_deadline_day(datetime) true on derived date",
      mgr.is_trade_deadline_day(datetime(2027, 3, 3, 12, 0)))
mgr_noleague = TradeDeadlineManager(None)
check("D5: manager without league falls back to Mar 8",
      mgr_noleague.deadline_date().month == 3
      and mgr_noleague.deadline_date().day == 8)
check("D5: get_deadline_manager singleton ok",
      get_deadline_manager(gm).deadline_date() == date(2027, 3, 3))

# --- D6: League._derive_trade_deadline repoints the event --------------------
fake_league = SimpleNamespace(
    schedule=list(sched) + [(date(2027, 3, 8), "NHL_EVENT",
                             {"type": "trade_deadline",
                              "title": "deadline"})])
League._derive_trade_deadline(fake_league)
ev = [e for e in fake_league.schedule
      if isinstance(e, tuple) and e[2].get("type") == "trade_deadline"]
check("D6: deadline event repointed to derived date",
      len(ev) == 1 and ev[0][0] == date(2027, 3, 3),
      f"got {ev[0][0] if ev else None}")
check("D6: league.trade_deadline_date stamped",
      getattr(fake_league, "trade_deadline_date", None) == date(2027, 3, 3))

# --- D7: automation milestone -------------------------------------------------
gm2 = SimpleNamespace(league=lg3)
check("D7: milestone date uses derived deadline",
      _derived_trade_deadline_date(2026, gm2) == date(2027, 3, 3))
check("D7: milestone falls back to Mar 8 without league",
      _derived_trade_deadline_date(2026, None) == date(2027, 3, 8))

# --- D4b: stale schedule (previous season) falls back cleanly ----------------
# League still on its 2026-27 schedule (last game Apr 2027 -> derived
# Mar 2027) but the game date faces the 2027-28 season: the gate must
# NOT freeze October on last season's deadline.
lg_stale = SimpleNamespace(schedule=sched, season_year=2026)
frozen, _ = te._trade_freeze_active("2027-10-15", lg_stale)
check("D4b: stale schedule doesn't freeze the next October", not frozen)
frozen, _ = te._trade_freeze_active("2028-01-15", lg_stale)
check("D4b: stale schedule leaves Jan open (falls back to Mar 8 gate)",
      not frozen)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
