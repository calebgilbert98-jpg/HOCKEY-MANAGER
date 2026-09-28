"""QA: draft-day trading (draft_day_trades.py) -- the entry draft runs like a
trade deadline, while fantasy drafts never trade.

Covers: fantasy isolation (no trading path), goalie supply in generated
classes, trade-up targeting (position + known slot + franchise situation),
franchise pick weighting (contender readiness vs rebuilder ceiling),
negotiation correctness (waiver scrub on dead deals, pick ownership
propagating into get_draft_order), human-club protection, NHL-only dealing,
and bounded deal volume.
"""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
random.seed(20260928)

import game_classes as g
from game_classes import PlayerPosition
import trade_engine as te
import draft_day_trades as ddt
from ai_team_management import ManagementPriority
from qa_draft_common import (make_league, StubStrategy, StubAIMgr, StubApp,
                             mkprospect, boost)

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}")


# -- 1: fantasy drafts never trade -------------------------------------------
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "fantasy_draft.py")).read()
check("fantasy module never imports draft_day_trades",
      "draft_day_trades" not in _src)
check("stale trade_deadline_round config removed",
      "trade_deadline_round:" not in _src
      and "trade_deadline_round =" not in _src)
check("no pick-trading mechanic in fantasy draft manager",
      "trade_pick" not in _src.replace("no_trade_clause", ""))

# -- 2: goalie supply is realistic -------------------------------------------
from draft_generator import generate_draft_class
_goalie_counts = []
for _seed in (7, 21, 99):
    random.seed(_seed)
    _pros = generate_draft_class(num_prospects=224, quality="Normal")
    _n = sum(1 for p in _pros
             if getattr(p.primary_position, "value", "") == "G")
    _goalie_counts.append(_n)
check("goalie supply realistic (18-25 of 224)",
      all(18 <= n <= 25 for n in _goalie_counts), str(_goalie_counts))
random.seed(20260928)

# -- 3: trade-up targeting ----------------------------------------------------
_team = g.Team("Targeters", "T", "D", "C")
_team.league_name = "National Hockey League"
# Roster: strong everywhere except center -> top need is C.
for _pos in (PlayerPosition.LEFT_WING, PlayerPosition.RIGHT_WING,
             PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
             PlayerPosition.GOALIE):
    _pl = g.Player(first_name="S", last_name="S", age=27,
                   primary_position=_pos)
    _team.roster.append(boost(_pl, 90))
needs = te.team_needs(_team)
check("rigged roster: top need is center", needs[0] == "C", str(needs[:3]))

_board = [
    mkprospect(PlayerPosition.CENTER, 95, "A"),      # proj #1, need fit
    mkprospect(PlayerPosition.LEFT_WING, 90, "A"),    # proj #2
    mkprospect(PlayerPosition.RIGHT_WING, 85, "B+"),  # proj #3
    mkprospect(PlayerPosition.CENTER, 82, "B"),      # proj #4
    mkprospect(PlayerPosition.CENTER, 60, "C"),      # proj #5 (at slot)
]
_tgt = ddt._trade_up_target(_team, 5, _board, "rebuild")
check("trade-up targets need-fit prospect ahead",
      _tgt is not None and _tgt[0] == 1,
      str(None if _tgt is None else _tgt[0]))
# No need match -> no target.
_team2 = g.Team("NoNeed", "T", "D", "C")
for _pos in (PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
             PlayerPosition.RIGHT_WING, PlayerPosition.LEFT_DEFENSE,
             PlayerPosition.RIGHT_DEFENSE):
    _pl = g.Player(first_name="S", last_name="S", age=27,
                   primary_position=_pos)
    _team2.roster.append(boost(_pl, 95))
_g = g.Player(first_name="G", last_name="G", age=27,
              primary_position=PlayerPosition.GOALIE)
_team2.roster.append(boost(_g, 95))
_board_g = [mkprospect(PlayerPosition.GOALIE, 95, "A"),
            mkprospect(PlayerPosition.CENTER, 60, "C")]
# every skater elite -> weakest is goalie; board's best is a goalie at #1
# but the team picks at #2 with a C at need... construct the inverse:
_team3 = g.Team("SkaterNeed", "T", "D", "C")
_g2 = g.Player(first_name="G", last_name="G", age=27,
              primary_position=PlayerPosition.GOALIE)
_team3.roster.append(boost(_g2, 95))  # only a great goalie -> needs skaters
_board2 = [mkprospect(PlayerPosition.GOALIE, 95, "A"),
           mkprospect(PlayerPosition.GOALIE, 94, "A"),
           mkprospect(PlayerPosition.CENTER, 60, "C")]
_tgt2 = ddt._trade_up_target(_team3, 3, _board2, "rebuild")
check("no target when nobody ahead fits a need", _tgt2 is None,
      str(None if _tgt2 is None else _tgt2[0]))
# Rebuilder ceiling filter: only a C-grade ceiling ahead -> pass.
_board3 = [mkprospect(PlayerPosition.CENTER, 70, "C"),
           mkprospect(PlayerPosition.CENTER, 60, "C")]
_tgt3 = ddt._trade_up_target(_team, 2, _board3, "rebuild")
check("rebuilder won't move up for a low ceiling", _tgt3 is None)

# -- 4: franchise pick weighting ----------------------------------------------
_hi_ovr = mkprospect(PlayerPosition.CENTER, 80, "C",
                     ovr_attrs=None)
boost(_hi_ovr, 92)  # NHL-ready, low ceiling
_hi_ceiling = mkprospect(PlayerPosition.CENTER, 80, "A")
boost(_hi_ceiling, 55)  # raw, elite ceiling
check("contender tilts to readiness",
      ddt.franchise_pick_multiplier(_hi_ovr, ManagementPriority.CONTEND) >
      ddt.franchise_pick_multiplier(_hi_ceiling, ManagementPriority.CONTEND))
check("rebuilder tilts to ceiling",
      ddt.franchise_pick_multiplier(_hi_ceiling, ManagementPriority.REBUILD) >
      ddt.franchise_pick_multiplier(_hi_ovr, ManagementPriority.REBUILD))
check("neutral priority is 1.0",
      ddt.franchise_pick_multiplier(_hi_ovr, ManagementPriority.MAINTAIN) == 1.0)

# -- 5: pre-draft wave invariants ----------------------------------------------
lg, nhl = make_league()
lg.draft_prospects = generate_draft_class(num_prospects=224,
                                          quality="Normal")
_human = nhl[3]
_human.is_user_team = True
_mapping = {t.team_name: (ManagementPriority.REBUILD if i < 10
                          else ManagementPriority.CONTEND)
            for i, t in enumerate(nhl)}
app = StubApp(lg, _mapping)
app.user_team = _human
random.seed(11)
deals = ddt.run_draft_day_trading(lg, 2027, app=app)
random.seed(20260928)
check("wave bounded (<= 4 deals)", len(deals) <= 4, str(len(deals)))
_human_name = _human.team_name
_involved = set()
for _d in deals:
    _s = getattr(_d, "summary", "")
    _involved.add((_d.team_a, _d.team_b))
check("human club never dealt",
      all(_human_name not in (a, b) for a, b in _involved),
      str(_involved))
check("all deals NHL clubs",
      all(a in {t.team_name for t in nhl} and b in {t.team_name for t in nhl}
          for a, b in _involved))
check("deal feed recorded",
      len(getattr(lg, "draft_day_deals", [])) == len(deals),
      f"{len(getattr(lg, 'draft_day_deals', []))} vs {len(deals)}")
# Pick ownership visible to the draft board after every deal.
_order_ok = True
for _d in deals:
    for _a in list(getattr(_d, "a_gave", [])) + list(getattr(_d, "b_gave", [])):
        if isinstance(_a, g.DraftPick):
            _owner = next(
                (t for t in nhl if _a in t.get_picks_for_year(_a.year)), None)
            if _owner is None or _owner.team_name != _a.current_team:
                _order_ok = False
check("pick objects live with their current_team owner", _order_ok)

# -- 5b: deterministic accept through the real engine ---------------------------
# Overwhelming offer (1st + 2nd + 3rd for a one-slot move up) must clear
# AI evaluation, execute, record, and propagate ownership.
lg3, nhl3 = make_league()
_proposer = nhl3[5]   # slot 6
_holder = nhl3[4]     # slot 5
_p1 = next(p for p in _proposer.get_picks_for_year(2027)
           if p.round == 1 and p.current_team == _proposer.team_name)
_p2 = next(p for p in _proposer.get_picks_for_year(2027)
           if p.round == 2 and p.current_team == _proposer.team_name)
_p3 = next(p for p in _proposer.get_picks_for_year(2027)
           if p.round == 3 and p.current_team == _proposer.team_name)
_h1 = next(p for p in _holder.get_picks_for_year(2027)
           if p.round == 1 and p.current_team == _holder.team_name)
app3 = StubApp(lg3, {_proposer.team_name: ManagementPriority.REBUILD,
                     _holder.team_name: ManagementPriority.REBUILD})
random.seed(4)
_done = ddt._negotiate(te, _proposer, _holder, [_p1, _p2, _p3], [_h1],
                       lg3, app3)
random.seed(20260928)
check("real engine accepts overwhelming trade-up",
      _done is not None and not str(
          getattr(_done, "summary", "")).startswith("BLOCKED:"),
      str(getattr(_done, "summary", ""))[:80])
if _done is not None:
    check("acquired pick re-points to proposer",
          _h1.current_team == _proposer.team_name)
    _row3 = next(r for r in lg3.get_draft_order(2027) if r[2] is _h1)
    check("draft order shows proposer on the clock with it",
          _row3[1].team_name == _proposer.team_name)

# -- 6: waiver scrub on dead deals (stub engine) --------------------------------
class _Resp:
    def __init__(self, decision, want_added=None, will_add=None):
        self.decision = decision
        self.want_added = want_added or []
        self.will_add = will_add or []


class _StubTE:
    """Deterministic engine double: always counters, deal never closes."""
    def __init__(self, will_add):
        self._will_add = will_add

    def ai_consider_trade(self, *a, **k):
        return _Resp("counter", will_add=self._will_add)

    def execute_trade(self, *a, **k):
        raise AssertionError("should not execute a declined counter")


_tA = g.Team("ScrubA", "T", "D", "C")
_tB = g.Team("ScrubB", "T", "D", "C")
_victim = g.Player(first_name="V", last_name="V", age=30,
                   primary_position=PlayerPosition.CENTER)
_victim.contract.ntc_waiver_for = "ScrubA"  # engine-stamped for this table
_outsider = g.Player(first_name="O", last_name="O", age=30,
                     primary_position=PlayerPosition.CENTER)
_outsider.contract.ntc_waiver_for = "Elsewhere"  # pre-existing: hands off
_stub = _StubTE(will_add=[_victim, _outsider])
# _proposer_accepts_counter uses the real te.evaluate_trade via module te;
# with empty gives/gets the ratio math fails safe -> declines.
_r = ddt._negotiate(_stub, _tA, _tB, [], [], lg, app)
check("declined counter kills the deal", _r is None)
check("engine-stamped waiver scrubbed after decline",
      _victim.contract.ntc_waiver_for == "",
      repr(_victim.contract.ntc_waiver_for))
check("pre-existing waiver for elsewhere untouched",
      _outsider.contract.ntc_waiver_for == "Elsewhere")

# -- 6b: M3 call-dialog plumbing (headless-safe pieces) ------------------------
_src_ddt = open("draft_day_trades.py").read()
check("incoming call no longer uses askyesno",
      "messagebox.askyesno" not in _src_ddt)
check("call dialog offers Accept/Counter/Decline",
      all(s in _src_ddt for s in ("'accept'", "'counter'", "'decline'"))
      and "_incoming_call_dialog" in _src_ddt)

# Waiver scrub helper: stamped-for-negotiators cleared, elsewhere kept.
_w1 = g.Player(first_name="W", last_name="1", age=30,
               primary_position=PlayerPosition.CENTER)
_w1.contract.ntc_waiver_for = "ScrubA"
_w2 = g.Player(first_name="W", last_name="2", age=30,
               primary_position=PlayerPosition.CENTER)
_w2.contract.ntc_waiver_for = "ScrubB"
_w3 = g.Player(first_name="W", last_name="3", age=30,
               primary_position=PlayerPosition.CENTER)
_w3.contract.ntc_waiver_for = "Elsewhere"
ddt._scrub_call_waivers([_w1, _w2, _w3], {"ScrubA", "ScrubB"})
check("scrub clears waivers stamped for negotiators",
      _w1.contract.ntc_waiver_for == ""
      and _w2.contract.ntc_waiver_for == "")
check("scrub preserves waiver for uninvolved team",
      _w3.contract.ntc_waiver_for == "Elsewhere")

# Why-they're-calling bullets carry target, need fit, and direction.
lgw, nhlw = make_league()
lgw.draft_prospects = generate_draft_class(num_prospects=224,
                                           quality="Normal")
_board = ddt._draft_board(lgw)
_tprosp = _board[0]
_wcaller = nhlw[3]
_why = ddt._call_why_lines(te, _wcaller, _tprosp, _board, "rebuild")
_bullets = " ".join(_why.get("bullets", []))
check("why-bullets name the target",
      getattr(_tprosp, 'full_name', '') in _bullets)
check("why-bullets state the franchise direction",
      "Rebuilding" in _bullets)
check("why direction short label", _why.get("direction_short") == "Rebuilding")

# Counter flow with no later picks returns None without touching UI.
class _ViewStub:
    def __init__(self, league):
        self.app = app
        self.draft_order = []
        self.current_pick = 0
        self._ct = {}
_viewstub = _ViewStub(lgw)
check("counter with no later picks returns None headlessly",
      ddt._user_counter_flow(_viewstub, _wcaller, [], [], 1) is None)

# -- 7: _sync_pick_lists moves objects, keeps get_draft_order honest -----------
lg2, nhl2 = make_league()
_a2, _b2 = nhl2[0], nhl2[1]
_pa = next(p for p in _a2.get_picks_for_year(2027)
           if p.round == 1 and p.current_team == _a2.team_name)
te.execute_trade(_a2, _b2, [_pa], [], date_str="2027-06-01")
ddt._sync_pick_lists(_a2, _b2, [_pa], [])
_o2 = lg2.get_draft_order(2027)
_row = next(r for r in _o2 if r[2] is _pa)
check("synced pick resolves to new owner in draft order",
      _row[1].team_name == _b2.team_name,
      f"{_row[1].team_name} vs {_b2.team_name}")

# -- 8: M6/M7 hub structural checks ---------------------------------------------
_src_hub = open("event_day_hubs.py").read()
check("hub keeps a single draft-board action",
      '"Draft Board / War Room"' in _src_hub
      and '"War Room / Auto-Draft"' not in _src_hub)
check("hub routes Trade This Pick to live pick-swap first",
      "trade_current_pick" in _src_hub
      and "open_trade_window" in _src_hub)
check("hub refresh timer cancels on close",
      "_cancel_live_tick" in _src_hub
      and "def close_view" in _src_hub)
check("hub refreshes wire/deals/clock/prospects/snapshot",
      all(s in _src_hub for s in ("_feed_write(self.wire_box",
                                  "_feed_write(self.deals_box",
                                  "_clock_team_lbl", "_fill_prospect_cards",
                                  "_fill_snapshot")))
check("no duplicate draft-board action labels",
      _src_hub.count('"Open Draft Board"') == 0)
check("Frenzy hub untouched by M7",
      'class FreeAgencyFrenzy' in _src_hub)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)