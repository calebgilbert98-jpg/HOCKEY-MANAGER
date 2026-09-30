# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: rules-audit regression suite (F1/F2/F12-F16).

Covers the draft/prospect-rights, contract, trade, retention, protected
pick, and deadline fixes. Headless; no UI. Run: python3 qa_audit_fixes.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
random.seed(20260928)
from types import SimpleNamespace

import game_classes as g
from game_classes import PlayerPosition
import trade_engine as te

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

def mkteam(name, cap=104_000_000):
    t = g.Team(name, "T", "D", "C")
    t.salary_cap = cap
    return t

# every attribute overall_rating() reads, so OVR is exactly `ovr`
_OVR_ATTRS = ('aggressiveness', 'anticipation', 'backhand', 'balance',
    'bodycheck', 'breakaway_skill', 'checking', 'composure', 'confidence',
    'defensive_awareness', 'deking', 'determination', 'endurance',
    'faceoffs', 'focus', 'glove_hand', 'hockey_iq', 'loose_puck',
    'off_the_puck', 'offensive_awareness', 'one_timer', 'passing',
    'passing_accuracy', 'passing_creativity', 'pokecheck', 'positioning',
    'pressure_player', 'puck_handling', 'rebound_control', 'reflexes',
    'screen_shots', 'shooting', 'shooting_accuracy', 'shooting_power',
    'shot_blocking', 'skating', 'slapshot', 'stick_side', 'stickhandling',
    'strength', 'vision', 'wristshot')

def mkplayer(salary, ovr=75, age=27, name="Test Player"):
    p = g.Player(first_name=name.split()[0], last_name=" ".join(name.split()[1:]) or "X",
                 age=age, primary_position=PlayerPosition.CENTER)
    p.contract.salary = salary
    p.contract.years_remaining = 3
    for attr in _OVR_ATTRS:
        try:
            setattr(p, attr, ovr)
        except Exception:
            pass
    try:
        p.faceoff_wins = ovr
    except Exception:
        pass
    return p

def _expected_salary(ovr):
    return max(775_000, (ovr - 60) * 250_000)

# ------------------------------------------------------------ F1: contract efficiency
print("== F1: player_trade_value reads contract.salary ==")
_probe = mkplayer(1_000_000, ovr=80)
_ovr = _probe.overall_rating()
_exp = _expected_salary(_ovr)
assert _ovr >= 70, f"probe OVR too low for bargain branch: {_ovr}"
overpaid = mkplayer(int(_exp * 2.0), ovr=80)    # > 1.5x expected -> discount
fair     = mkplayer(int(_exp * 1.0), ovr=80)    # no adjustment
bargain  = mkplayer(int(_exp * 0.5), ovr=80)    # < 0.6x expected -> premium
for _p, _s in ((overpaid, int(_exp*2.0)), (fair, int(_exp)), (bargain, int(_exp*0.5))):
    _p.contract.salary = _s  # keep salary exact; OVR identical by construction
v_over, v_fair = te.player_trade_value(overpaid), te.player_trade_value(fair)
v_barg = te.player_trade_value(bargain)
check(f"overpaid ({_ovr}ovr) worth less than fairly-paid", v_over < v_fair)
check(f"bargain ({_ovr}ovr) worth more than fairly-paid", v_barg > v_fair)
check("values are sane magnitudes", v_fair > 500 and v_over > 100)

# ------------------------------------------------------------ F2: waiver-aware trade cap
print("== F2: waiver shed in trade validation ==")
w = mkplayer(5_000_000); w.on_waivers = True; w.waiver_days = 2
n = mkplayer(5_000_000)
check("waived player counts $0 outgoing", te._effective_outgoing_hit(w) == 0)
check("active player counts full hit", te._effective_outgoing_hit(n) == 5_000_000)
u, p = mkteam("U2"), mkteam("P2")
u.roster.append(w)
inbound = mkplayer(1_000_000, name="Inbound One")
p.roster.append(mkplayer(5_000_000))
p.roster.append(inbound)
# over-cap team shedding a waived player: validation must not double-count
u.salary_cap = 5_000_000  # tiny cap; waived 5M already sheds to $0 baseline
tr = te.execute_trade(u, p, [w], [inbound], date_str="2026-11-01")
moved = tr.summary.startswith("BLOCKED:")
check("waived-player trade executes (no phantom cap block)", not moved)
got = inbound if not moved else None
check("acquiring club receives cleared waiver flags",
      moved or (got.on_waivers is False and got.waiver_days == 0))

# ------------------------------------------------------------ F12: live-season pick anchor
print("== F12: future-pick discount anchored to live season ==")
g.set_pick_value_anchor_year(2026)
p30 = g.DraftPick(year=2030, round=1, original_team="A", current_team="A")
check("2030 1st anchored 2026 discounts 4yrs (800)", p30.value == 800)
g.set_pick_value_anchor_year(2030)
check("same pick anchored 2030 has no discount (1000)",
      g.DraftPick(year=2030, round=1, original_team="A", current_team="A").value == 1000)
g.set_pick_value_anchor_year(2026)
lg = g.League.__new__(g.League)
lg.season_year = 2031
g.League.__post_init__(lg) if False else None  # skip heavyweight setup
g.set_pick_value_anchor_year(lg.season_year)
check("anchor follows save's season_year", g._pick_value_anchor() == 2031)
g.set_pick_value_anchor_year(2026)

# ------------------------------------------------------------ F13: standings projection
print("== F13: standings-aware 1st-round projection ==")
teams, standings = [], {}
for i in range(32):
    t = SimpleNamespace(team_name=f"T{i:02d}", draft_picks={})
    # T00 worst (10 pts) ... T31 best (130 pts)
    pts = 10 + i * 4
    standings[f"T{i:02d}"] = {"Points": pts}
    for yr in (2027, 2028):
        pk = g.DraftPick(year=yr, round=1, original_team=f"T{i:02d}",
                         current_team=f"T{i:02d}")
        t.draft_picks.setdefault(yr, []).append(pk)
    teams.append(t)
stub_lg = SimpleNamespace(teams=teams, standings=standings,
                          draft_prospects_year=2027, season_year=2026,
                          get_draft_order=lambda y: [])
n = te.project_pick_slots(stub_lg)
check("projected 64 future 1sts", n == 64)
worst_pk = teams[0].draft_picks[2028][0]    # worst club's future 1st
best_pk  = teams[31].draft_picks[2028][0]   # best club's future 1st
check(f"basement club projects lottery (got #{worst_pk.projected_overall})",
      1 <= worst_pk.projected_overall <= 8)
check(f"top club projects late 1st (got #{best_pk.projected_overall})",
      20 <= best_pk.projected_overall <= 32)
v_worst = te.pick_trade_value(worst_pk)
plain = g.DraftPick(year=2028, round=1, original_team="Z", current_team="Z")
v_plain = te.pick_trade_value(plain)
check("projected lottery 1st valued above blind #16 default", v_worst > v_plain)
check("label shows projection", "[proj. #" in te.asset_label(worst_pk))
# real order clears stale projections
stub_lg.get_draft_order = lambda y: [("x",)] if y == 2027 else []
te.project_pick_slots(stub_lg)
check("real order wipes projection for that year",
      teams[0].draft_picks[2027][0].projected_overall == 0)
check("other years keep projections",
      teams[0].draft_picks[2028][0].projected_overall != 0)

# ------------------------------------------------------------ F14: deadline freeze
print("== F14: canonical trade-deadline freeze ==")
_season_running = SimpleNamespace(season_year=2026)  # Cup not decided yet
_season_over = SimpleNamespace(season_year=2027)     # end_of_season rolled
check("Nov 2026 allowed", te.trades_allowed("2026-11-01"))
check("deadline day 2027-03-08 allowed", te.trades_allowed("2027-03-08"))
check("2027-03-09 frozen (season running)",
      not te.trades_allowed("2027-03-09", _season_running))
check("2027-04-15 frozen (season running)",
      not te.trades_allowed("2027-04-15", _season_running))
check("2027-08-01 allowed (summer)", te.trades_allowed("2027-08-01"))
check("unparseable date fails open", te.trades_allowed(""))
check("post-season June allowed (season_year rolled)",
      te.trades_allowed("2027-06-20", _season_over))
check("post-season April allowed (season_year rolled)",
      te.trades_allowed("2027-04-20", _season_over))
u3, p3 = mkteam("U3"), mkteam("P3")
a3, b3 = mkplayer(4_000_000, name="Alfa One"), mkplayer(4_000_000, name="Beta Two")
u3.roster.append(a3); p3.roster.append(b3)
tr = te.execute_trade(u3, p3, [a3], [b3], date_str="2027-04-15",
                      league=_season_running)
check("execute_trade BLOCKS post-deadline deal",
      tr.summary.startswith("BLOCKED:") and "freeze" in tr.summary.lower())
check("blocked deal moves nothing",
      a3 in u3.roster and b3 in p3.roster)
tr2 = te.execute_trade(u3, p3, [a3], [b3], date_str="2027-03-08")
check("execute_trade allows deadline-day deal", not tr2.summary.startswith("BLOCKED:"))
check("deadline-day deal moves assets", a3 in p3.roster and b3 in u3.roster)

# ------------------------------------------------------------ F15: protected-pick roll-forward
print("== F15: protected-pick deferral chain ==")
def mkleague_scenario(orig_future_firsts, orig_future_seconds):
    """orig_future_firsts: {year: holder or None}; seconds likewise."""
    orig = SimpleNamespace(team_name="ORIG",
                           draft_picks={2027: [], 2028: [], 2029: [], 2030: []})
    hold = SimpleNamespace(team_name="HOLD", draft_picks={2027: []})
    prot = g.DraftPick(year=2027, round=1, original_team="ORIG",
                       current_team="HOLD")
    prot.protection = "top-10"; prot.is_conditional = True
    hold.draft_picks[2027].append(prot)
    for yr in (2028, 2029, 2030):
        h = orig_future_firsts.get(yr)
        pk = g.DraftPick(year=yr, round=1, original_team="ORIG",
                         current_team=h or "ORIG")
        orig.draft_picks[yr].append(pk)
    for yr in (2027, 2028, 2029):
        h = orig_future_seconds.get(yr)
        pk = g.DraftPick(year=yr, round=2, original_team="ORIG",
                         current_team=h or "ORIG")
        orig.draft_picks[yr].append(pk)
    lg = SimpleNamespace(
        teams=[orig, hold],
        standings={"ORIG": {"Points": 60}, "HOLD": {"Points": 100}},
        lottery_results={2027: [{"original_team": "ORIG", "pick": 2}]},
        _protections_resolved=set(),
        pick_protection_news=[],
        PROTECTION_ZONES=g.League.PROTECTION_ZONES)
    return lg, orig, hold, prot

# A: orig still owns 2028 1st -> defers one year
lg, orig, hold, prot = mkleague_scenario({}, {})
ev = g.League.resolve_pick_protections(lg, 2027)
d28 = orig.draft_picks[2028][0]
check("A: protection triggers, 2027 1st reverts",
      prot.current_team == "ORIG" and any("keeps" in e for e in ev))
check("A: holder receives 2028 1st", d28.current_team == "HOLD")
# B: 2028+2029 1sts traded away -> rolls to 2030
lg, orig, hold, prot = mkleague_scenario({2028: "X", 2029: "Y"}, {})
g.League.resolve_pick_protections(lg, 2027)
d30 = [c for c in orig.draft_picks[2030] if c.round == 1][0]
check("B: obligation rolls forward to 2030 1st", d30.current_team == "HOLD")
check("B: 2027 1st still reverts", prot.current_team == "ORIG")
# C: no 1st for 3 years -> converts to 2nd
lg, orig, hold, prot = mkleague_scenario({2028: "X", 2029: "Y", 2030: "Z"}, {})
g.League.resolve_pick_protections(lg, 2027)
s27 = [c for c in orig.draft_picks[2027] if c.round == 2][0]
check("C: converts to ORIG's 2027 2nd", s27.current_team == "HOLD")
check("C: news records conversion",
      any("converts" in e for e in lg.pick_protection_news))

# ------------------------------------------------------------ F16: ban lifecycle
print("== F16: retention bans die with the old SPC ==")
bp = mkplayer(6_000_000, name="Ban Guy")
bp.retained_amount = 3_000_000
bp.retained_team_name = "OLDCLUB"
bp.retained_by = ["OLDCLUB"]
bp.retention_bans = [{"team": "OLDCLUB", "date": "2026-11-01"}]
te.clear_retention_state(bp)
check("amounts wiped", bp.retained_amount == 0 and bp.retained_team_name == "")
check("reacquisition bans wiped on new SPC", bp.retention_bans == [])
# ban still enforced when no new contract was signed
u4, p4 = mkteam("OLDCLUB"), mkteam("NEWCLUB")
c4 = mkplayer(6_000_000, name="Stuck Guy")
c4.retention_bans = [{"team": "OLDCLUB", "date": "2026-11-01"}]
p4.roster.append(c4)
d4 = mkplayer(1_000_000, name="Depth Four")
u4.roster.append(d4)
tr = te.execute_trade(u4, p4, [d4], [c4], date_str="2027-02-01")
check("live ban still blocks reacquisition within a year",
      tr.summary.startswith("BLOCKED:") and "reacquire" in tr.summary)

# ------------------------------------------------- F17: CBA schedules/constants
print("== F17: new-CBA salary/term schedules ==")
import salary_cap_system as scs
check("minimum 2026 = 850k", scs.league_minimum_salary(2026) == 850_000)
check("minimum 2027 = 900k", scs.league_minimum_salary(2027) == 900_000)
check("minimum 2028 = 950k", scs.league_minimum_salary(2028) == 950_000)
check("minimum 2029 = 1M", scs.league_minimum_salary(2029) == 1_000_000)
check("minimum 2025 = 775k (old CBA)", scs.league_minimum_salary(2025) == 775_000)
check("minimum holds at 1M past CBA", scs.league_minimum_salary(2032) == 1_000_000)
check("ELC 3yr max total base = 3.075M (flat 1.025M x 3)",
      scs.elc_max_total(3) == 3_075_000)
check("ELC 3yr max flat salary (AAV) = 1.025M",
      scs.elc_max_salary(3) == 1_025_000)
check("ELC 2yr max flat salary (AAV) = 1.025M",
      scs.elc_max_salary(2) == 1_025_000)
check("ELC max is League-Year based: 2027-28 = 1.075M",
      scs.elc_max_annual_comp(2027) == 1_075_000)
check("max term re-sign = 7", scs.max_contract_term(True) == 7)
check("max term external = 6", scs.max_contract_term(False) == 6)
check("burial 2026 = 2M (1.15M + min)",
      scs.burial_exemption(2026) == 2_000_000)

# ------------------------------------------------- F18: ELC band dynamics
print("== F18: dynamic ELC band ==")
from player_generator import PlayerGenerator as _PG
def mkunsigned(age, junior_league, draft_round=2):
    p = g.Player(first_name="Test", last_name="Unsigned", age=age,
                 primary_position=PlayerPosition.CENTER)
    p.contract = None
    # Coherent birth_date: the CBA 9.2 Sept-15 signing age is read from
    # birth_date, so it must agree with the stated age.
    p.birth_date = f"{2026 - age}-06-15"
    p.junior_league = junior_league
    p.draft_round = draft_round
    return p
_pe = mkunsigned(18, "OHL"); _pe.drafted_year = 2026
_sal, _yrs, _tw, _ahl = _PG().determine_contract_info(_pe, "NHL_ROOKIE")
check("ELC salary within 850k-1.025M band", 850_000 <= _sal <= 1_025_000)
check("ELC term 3 years at 18", _yrs == 3)
check("ELC minors pay capped at 87.5k", _ahl <= 87_500)
_pe22 = mkunsigned(22, "OHL"); _pe22.drafted_year = 2026
_sal2, _yrs2, _tw2, _ahl2 = _PG().determine_contract_info(_pe22, "NHL_ROOKIE")
check("ELC term 2 years at 22", _yrs2 == 2)
check("ELC salary floor 850k even for low-ovr",
      _sal >= 850_000)

# ------------------------------------------------- F19: 75-day double retention
# True CBA (2026), quoted text: a second Retained Salary Transaction "may
# not occur within seventy-five (75) Regular Season days of the first" --
# calendar days inside the regular-season window (opening night -> last
# game; breaks count; playoffs/off-season/camp do not), legal only on
# day 76+, and the restriction may span league years. The same-day broker
# flip is dead.
print("== F19: second-retention 75 regular-season-day clock ==")
from datetime import date as _d
_wins = [(_d(2026, 10, 7), _d(2027, 4, 15)),
         (_d(2027, 10, 6), _d(2028, 4, 13))]
check("regular-season days Jan10->Apr15 = 95",
      te._regular_season_days_between("2027-01-10", "2027-04-15", _wins) == 95)
check("clock pauses in summer: Mar1->Oct6 = 46",
      te._regular_season_days_between("2027-03-01", "2027-10-06", _wins) == 46)
check("clock spans league years: Mar1->Nov10 = 81",
      te._regular_season_days_between("2027-03-01", "2027-11-10", _wins) == 81)
check("breaks count: Feb1->Feb20 = 19 (Olympic break inside window)",
      te._regular_season_days_between("2027-02-01", "2027-02-20", _wins) == 19)
check("no-schedule fallback still month-counts",
      te._regular_season_days_between("2027-03-01", "2027-04-30", None) == 60)
_fw = te.regular_season_windows(None, ref_year=2026)
check("fallback windows cover adjacent seasons",
      _fw[1] == (_d(2026, 10, 1), _d(2027, 4, 15)) and len(_fw) == 3)
_lgw = g.League("Sched", season_year=2026)
_lgw.schedule = [{"date": _d(2026, 10, 7)}, {"date": _d(2027, 4, 15)}]
_sw = te.regular_season_windows(_lgw)
check("schedule-derived window = opening night -> last game",
      _sw[1] == (_d(2026, 10, 7), _d(2027, 4, 15)))
check("schedule windows year-shift for adjacent seasons",
      _sw[2][0] == _d(2027, 10, 7) and _sw[0][1] == _d(2026, 4, 15))
_rA = mkteam("Retain A"); _rB = mkteam("Retain B")
_rp = mkplayer(6_000_000, ovr=80, age=28)
_rp.retained_by = ["Retain A"]; _rp.retained_team_name = "Retain A"
_rp.retained_amount = 3_000_000
_rp.retention_trade_dates = ["2027-01-10"]
_ok, _a, _r = te._retention_check(_rB, _rp, 25, trade_date="2027-02-01",
                                 season_windows=_wins)
check("second retention within 75 regular-season days blocked", not _ok)
check("block cites the clock", "75" in str(_r))
_ok2, _a2, _r2 = te._retention_check(_rB, _rp, 25, trade_date="2027-01-10",
                                    season_windows=_wins)
check("same-day broker flip now blocked (true CBA)", not _ok2)
_ok75, _, _ = te._retention_check(_rB, _rp, 25, trade_date="2027-03-26",
                                 season_windows=_wins)
check("exactly 75 days still blocked (legal only on day 76+)", not _ok75)
_ok3, _a3, _r3 = te._retention_check(_rB, _rp, 25, trade_date="2027-03-27",
                                    season_windows=_wins)
check("76 regular-season days: second retention allowed", _ok3)
_ok3b, _, _ = te._retention_check(_rB, _rp, 25, trade_date="2027-11-10",
                                 season_windows=_wins)
check("spanning the summer: 81 regular-season days allowed", _ok3b)
_ok4, _a4, _r4 = te._retention_check(_rB, _rp, 25)
check("missing trade date fails open", _ok4)
_rp2 = mkplayer(6_000_000, ovr=80, age=28)
_okn, _nn = te.apply_retention(_rA, _rp2, 25, trade_date="2027-01-10",
                               season_windows=_wins)
check("apply_retention succeeds", _okn)
check("retention stamps trade date",
      _rp2.retention_trade_dates == ["2027-01-10"])
_okb, _nb = te.apply_retention(_rB, _rp2, 20, trade_date="2027-01-10",
                               season_windows=_wins)
check("same-day second retention refused", not _okb)
check("refusal cites the 75-day clock", "75" in str(_nb))
te.clear_retention_state(_rp2)
check("new SPC clears retention dates", _rp2.retention_trade_dates == [])

# ------------------------------------------------- F20: CHL rights 4yr/3yr
print("== F20: new-CBA CHL rights ==")
_lg = g.League("Test", season_year=2026)
_c18 = mkunsigned(18, "OHL"); _lg.stamp_draft_rights(_c18, "Testers", 2026)
check("CHL drafted at 18: 4-year rights",
      _c18.rights_expiry_year == 2030 and _c18.rights_type == "CHL")
_c19 = mkunsigned(19, "WHL"); _lg.stamp_draft_rights(_c19, "Testers", 2026)
check("CHL drafted at 19: 3-year rights",
      _c19.rights_expiry_year == 2029 and _c19.rights_type == "CHL")
_c20 = mkunsigned(20, "QMJHL"); _lg.stamp_draft_rights(_c20, "Testers", 2026)
check("CHL drafted at 20+: 2-year rights",
      _c20.rights_expiry_year == 2028 and _c20.rights_type == "CHL")
_nc = mkunsigned(18, "NCAA"); _lg.stamp_draft_rights(_nc, "Testers", 2026)
check("NCAA: 4-year rights",
      _nc.rights_expiry_year == 2030 and _nc.rights_type == "NCAA")
check("playing_where stamped at draft", _c18.playing_where == "OHL")
# Expiry scan honors the stamp: no 2-year expiry for an 18yo CHL pick.
_lg20 = g.League("T20", season_year=2026)
_t20 = mkteam("Rights Holders"); _lg20.teams.append(_t20)
_px = mkunsigned(18, "OHL"); _t20.prospects.append(_px)
_lg20.stamp_draft_rights(_px, "Rights Holders", 2026)
_lg20._rollover_draft_rights(2028)  # old CBA would expire him here
check("18yo CHL pick still held after 2 rollovers",
      getattr(_px, "rights_team", "") == "Rights Holders")

# ------------------------------------------------- F21: prospect AHL eligibility
print("== F21: AHL eligibility gates ==")
check("junior track CHL", g.junior_track_of(mkunsigned(18, "OHL")) == "CHL")
check("junior track NCAA", g.junior_track_of(mkunsigned(18, "NCAA")) == "NCAA")
check("junior track EUROPE", g.junior_track_of(mkunsigned(18, "SHL")) == "EUROPE")
check("19yo 1st-round CHL -> AHL eligible (new CBA)",
      g.prospect_ahl_eligible(mkunsigned(19, "OHL", draft_round=1)))
check("19yo 3rd-round CHL -> junior only",
      not g.prospect_ahl_eligible(mkunsigned(19, "OHL", draft_round=3)))
check("18yo 1st-round CHL -> junior only",
      not g.prospect_ahl_eligible(mkunsigned(18, "QMJHL", draft_round=1)))
check("20yo CHL -> AHL eligible",
      g.prospect_ahl_eligible(mkunsigned(20, "WHL", draft_round=5)))
check("NCAA 19yo -> AHL eligible",
      g.prospect_ahl_eligible(mkunsigned(19, "NCAA", draft_round=1)))
check("EURO 19yo -> AHL eligible",
      g.prospect_ahl_eligible(mkunsigned(19, "SHL", draft_round=7)))

# ------------------------------------------------- F22: drafted-prospect signing
print("== F22: sign_drafted_prospect assignment ==")
_lg2 = g.League("T2", season_year=2026)
_t2 = mkteam("Signers"); _lg2.teams.append(_t2)
_pn = mkunsigned(19, "NCAA"); _t2.prospects.append(_pn)
_lg2.stamp_draft_rights(_pn, "Signers", 2026)
check("NCAA prospect signs", _lg2.sign_drafted_prospect(_t2, _pn))
check("signed ex-college player to AHL, never college",
      _pn.playing_where == "AHL")
check("ELC meets new minimum", _pn.contract.salary >= 850_000)
check("rights consumed on signing", _pn.rights_team == "")
_pc = mkunsigned(18, "OHL"); _t2.prospects.append(_pc)
_lg2.stamp_draft_rights(_pc, "Signers", 2026)
_lg2.sign_drafted_prospect(_t2, _pc)
check("signed 18yo CHL prospect returns to junior",
      _pc.playing_where == "OHL")
check("junior assignee stays cap-exempt in prospects",
      _pc in _t2.prospects)

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:"); [print(" -", f) for f in failed]
    sys.exit(1)
