# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: AI GM identity -- personality-driven behavior, job security, ELC signings.

Covers:
  1. Identity derives from the actual GM staff member (archetypes).
  2. Fallback identity when a team has no GM (old saves).
  3. Risk appetite: hot-seat GM > tenured Cup-winner, same personality.
  4. Board confidence moves with results; losing -> hot seat; champ -> floor.
  5. AI signs prospects who deserve it (top grades / NHL-ready) or need it
     (rights expiring); ignores low-grade prospects with years of rights left.
  6. Hot-seat GMs sign more eagerly than tenured winners.
  7. Promotion gating: unsigned never promoted; junior-track signed prospects
     stay out of the AHL; AHL-eligible signed prospects move up.
  8. Strategy reflects identity: aggressive GM -> aggressive trading;
     hot-seat rebuild roster -> win-now priority.
  9. process_daily_decisions runs headless end-to-end and executes signings.

Usage: python3 qa_ai_gm_identity.py
Exit code 0 = all pass.
"""

import random
import sys
from datetime import date

sys.path.insert(0, ".")

from game_classes import Player, Team, PlayerPosition, Staff, StaffRole
from ai_team_management import AITeamManager
from ai_gm_identity import (
    gm_identity_from_staff, GMJobSecurity, update_job_security,
    compute_risk_appetite, signing_urgency, expectation_from_strength,
)

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} -- {detail}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_gm(**over):
    g = Staff(first_name="Test", last_name="GM", role=StaffRole.GENERAL_MANAGER)
    for k, v in over.items():
        setattr(g, k, v)
    return g


def make_team(name, gm=None, roster_ovr=70, roster_age=27, n_prospects=0):
    t = Team(name, "Eastern", "Atlantic", "Test")
    t.roster = []
    for i in range(20):
        p = Player(first_name=f"R{i}", last_name="Player", age=roster_age,
                   primary_position=PlayerPosition.CENTER)
        for attr in ("skating", "shooting", "passing", "checking", "defense",
                     "hockey_iq"):
            setattr(p, attr, roster_ovr)
        p.contract = object()
        t.roster.append(p)
    t.ahl_roster = []
    t.prospects = []
    if gm is not None:
        t.staff = [gm]
    else:
        t.staff = []
    # A record the board can read.
    t.wins, t.losses, t.ot_losses = 0, 0, 0
    return t


def make_prospect(name, team_name, grade="B", age=19, ovr=68,
                  rights_years_left=3, junior_league="OHL",
                  draft_round=2, season_year=2026):
    p = Player(first_name=name, last_name="Prospect", age=age,
               primary_position=PlayerPosition.CENTER)
    for attr in ("skating", "shooting", "passing", "checking", "defense",
                 "hockey_iq"):
        setattr(p, attr, ovr)
    # Pin overall_rating: the real computation blends many attributes, so
    # pin it for exact test control.
    _ovr = ovr
    p.overall_rating = lambda: float(_ovr)
    p.potential_grade = grade
    p.contract = None
    p.rights_team = team_name
    p.rights_expiry_year = season_year + rights_years_left
    p.junior_league = junior_league
    p.draft_round = draft_round
    return p


class FakeLeague:
    def __init__(self, season_year=2026):
        self.season_year = season_year
        self._last_cup_champ = None
        self.signed = []

    def sign_drafted_prospect(self, team, player):
        player.contract = object()  # ELC issued
        self.signed.append((team.team_name, player.first_name))


# ---------------------------------------------------------------------------
# 1-2. Identity derivation + fallback
# ---------------------------------------------------------------------------

random.seed(7)

aggressor = make_gm(determination=95, ambition="stanley_cup", controversy=80,
                    adaptability=25, control_need=90,
                    working_with_youngsters=30, player_development=35)
ident = gm_identity_from_staff("Test Team", aggressor)
check("aggressor archetype", ident.archetype == "Win-Now Aggressor",
      f"got {ident.archetype}")
check("aggressor aggression high", ident.aggression >= 0.65,
      f"{ident.aggression:.2f}")

builder = make_gm(determination=55, ambition="developer", controversy=20,
                  adaptability=70, working_with_youngsters=95,
                  player_development=90)
ident_b = gm_identity_from_staff("Test Team", builder)
check("builder archetype", ident_b.archetype == "Patient Builder",
      f"got {ident_b.archetype}")
check("builder patience > aggressor patience",
      ident_b.patience > ident.patience,
      f"{ident_b.patience:.2f} vs {ident.patience:.2f}")

fallback = gm_identity_from_staff("No GM Team", None)
check("fallback identity sane",
      fallback.gm_name == "Interim GM" and fallback.archetype == "Pragmatist",
      fallback.describe())

# ---------------------------------------------------------------------------
# 3. Risk appetite: hot seat vs tenured winner
# ---------------------------------------------------------------------------

sec_hot = GMJobSecurity(team_name="T", expectation="contend",
                        confidence=20.0, hot_seat=True)
sec_champ = GMJobSecurity(team_name="T", expectation="win_cup",
                          confidence=85.0, tenured_winner=True)
sec_mid = GMJobSecurity(team_name="T", expectation="playoffs", confidence=60.0)

risk_hot = compute_risk_appetite(ident, sec_hot)
risk_champ = compute_risk_appetite(ident, sec_champ)
risk_mid = compute_risk_appetite(ident, sec_mid)
check("hot seat riskier than stable", risk_hot > risk_mid,
      f"{risk_hot:.2f} vs {risk_mid:.2f}")
check("tenured winner more conservative", risk_champ < risk_mid,
      f"{risk_champ:.2f} vs {risk_mid:.2f}")
check("hot seat beats champ comfortably", risk_hot - risk_champ >= 0.3,
      f"{risk_hot:.2f} vs {risk_champ:.2f}")

# ---------------------------------------------------------------------------
# 4. Board confidence dynamics
# ---------------------------------------------------------------------------

team_lose = make_team("Losers", aggressor)
team_lose.wins, team_lose.losses, team_lose.ot_losses = 10, 35, 5  # .250 pace
sec = GMJobSecurity(team_name="Losers", expectation="contend", confidence=60.0)
for _ in range(10):  # ten weekly reviews
    update_job_security(sec, ident, team_lose, None, 2027)
check("losing erodes confidence", sec.confidence < 40.0,
      f"{sec.confidence:.1f}")
check("sustained losing -> hot seat", sec.hot_seat,
      f"conf={sec.confidence:.1f}")

team_win = make_team("Winners", builder)
team_win.wins, team_win.losses, team_win.ot_losses = 40, 8, 2  # .820 pace
sec_w = GMJobSecurity(team_name="Winners", expectation="contend", confidence=60.0)
for _ in range(10):
    update_job_security(sec_w, ident_b, team_win, None, 2027)
check("winning builds confidence", sec_w.confidence > 65.0,
      f"{sec_w.confidence:.1f}")
check("winner not on hot seat", not sec_w.hot_seat)

# Defending champ gets a floor even with a mediocre record.
team_champ = make_team("Champs", builder)
team_champ.wins, team_champ.losses, team_champ.ot_losses = 20, 25, 5
sec_c = GMJobSecurity(team_name="Champs", expectation="win_cup", confidence=60.0)
update_job_security(sec_c, ident_b, team_champ, "Champs", 2027)
check("champ confidence floor", sec_c.confidence >= 75.0,
      f"{sec_c.confidence:.1f}")

check("expectation_from_strength bands",
      expectation_from_strength(75) == "win_cup"
      and expectation_from_strength(65) == "contend"
      and expectation_from_strength(55) == "playoffs"
      and expectation_from_strength(45) == "rebuild")

# ---------------------------------------------------------------------------
# 5-6. Prospect signing evaluation
# ---------------------------------------------------------------------------

mgr = AITeamManager()
league = FakeLeague(season_year=2026)
mgr._league_ref = league

team = make_team("Signers", aggressor)
team.prospects = [
    make_prospect("Expiring", "Signers", grade="C", age=21, ovr=66,
                  rights_years_left=1),          # need it: rights almost gone
    make_prospect("Bluechip", "Signers", grade="A", age=19, ovr=72,
                  rights_years_left=3),          # deserve it: top grade
    make_prospect("Filler", "Signers", grade="C", age=19, ovr=62,
                  rights_years_left=3),          # neither: leave unsigned
]
mgr.initialize_team_strategies([team])
strategy = mgr.team_strategies["Signers"]
identity = mgr.gm_identities["Signers"]
sec = mgr.gm_security["Signers"]

signings = mgr._evaluate_prospect_signings(team, strategy, identity, sec,
                                           date(2026, 10, 15))
signed_names = {d.target_player.first_name for d in signings
                if d.decision_type == "sign_prospect"}
check("expiring rights get signed", "Expiring" in signed_names, str(signed_names))
check("blue-chip gets signed", "Bluechip" in signed_names, str(signed_names))
check("filler stays unsigned", "Filler" not in signed_names, str(signed_names))

# NHL-ready prospect on his own club (avoids the 2/week signing cap).
team_ready = make_team("ReadyClub", aggressor)
team_ready.prospects = [make_prospect("Ready", "ReadyClub", grade="B", age=21,
                                      ovr=76, rights_years_left=3)]
mgr.initialize_team_strategies([team_ready])
ready_signs = mgr._evaluate_prospect_signings(
    team_ready, mgr.team_strategies["ReadyClub"],
    mgr.gm_identities["ReadyClub"], mgr.gm_security["ReadyClub"],
    date(2026, 10, 15))
check("NHL-ready gets signed",
      any(d.target_player.first_name == "Ready" for d in ready_signs),
      str([d.target_player.first_name for d in ready_signs]))

# Hot-seat GM signs more eagerly than a tenured winner (same roster) --
# but only a GM wired to bend under pressure. The aggressor rushes the
# bubble prospect; the patient builder trusts his vision and waits.
sec_hot2 = GMJobSecurity(team_name="Signers", expectation="contend",
                         confidence=20.0, hot_seat=True)
sec_champ2 = GMJobSecurity(team_name="Signers", expectation="win_cup",
                           confidence=90.0, tenured_winner=True)
team2 = make_team("Signers", aggressor)
team2.prospects = [make_prospect("Bubble", "Signers", grade="B-", age=20,
                                 ovr=70, rights_years_left=3)]
mgr.initialize_team_strategies([team2])
strategy2 = mgr.team_strategies["Signers"]
identity2 = mgr.gm_identities["Signers"]
hot_signs = mgr._evaluate_prospect_signings(team2, strategy2, identity2,
                                            sec_hot2, date(2026, 10, 15))
champ_signs = mgr._evaluate_prospect_signings(team2, strategy2, identity2,
                                              sec_champ2, date(2026, 10, 15))
check("hot seat signs the bubble prospect", len(hot_signs) == 1,
      f"hot={[d.target_player.first_name for d in hot_signs]}")
check("tenured winner waits on the bubble prospect", len(champ_signs) == 0,
      f"champ={[d.target_player.first_name for d in champ_signs]}")
# The patient builder on the hot seat does NOT panic-sign the bubble kid --
# the seat changes nothing for him (stable builder wouldn't sign either).
team2b = make_team("PatientSigners", builder)
team2b.prospects = [make_prospect("BubbleJr", "PatientSigners", grade="B-",
                                  age=20, ovr=69, rights_years_left=3)]
mgr.initialize_team_strategies([team2b])
sec_mid2 = GMJobSecurity(team_name="PatientSigners", expectation="contend",
                         confidence=60.0)
builder_hot_signs = mgr._evaluate_prospect_signings(
    team2b, mgr.team_strategies["PatientSigners"],
    mgr.gm_identities["PatientSigners"], sec_hot2, date(2026, 10, 15))
builder_mid_signs = mgr._evaluate_prospect_signings(
    team2b, mgr.team_strategies["PatientSigners"],
    mgr.gm_identities["PatientSigners"], sec_mid2, date(2026, 10, 15))
check("hot seat changes nothing for the builder's signings",
      len(builder_hot_signs) == 0 and len(builder_mid_signs) == 0,
      f"hot={len(builder_hot_signs)} stable={len(builder_mid_signs)}")

# ---------------------------------------------------------------------------
# 7. Promotion gating
# ---------------------------------------------------------------------------

team3 = make_team("Promoters", aggressor)
unsigned_junior = make_prospect("Unsigned", "Promoters", grade="B", age=20,
                                ovr=74, rights_years_left=3)   # no contract
signed_junior = make_prospect("JuniorKid", "Promoters", grade="B", age=19,
                              ovr=74, rights_years_left=3)     # CHL 19yo, r2
signed_junior.contract = object()
signed_ahl = make_prospect("AhlReady", "Promoters", grade="B", age=20,
                           ovr=74, rights_years_left=3,
                           junior_league="NCAA")
signed_ahl.contract = object()
team3.prospects = [unsigned_junior, signed_junior, signed_ahl]
mgr.initialize_team_strategies([team3])

promote_decisions = [
    type("D", (), {"decision_type": "promote_prospect",
                   "target_player": p})()
    for p in team3.prospects
]
mgr._execute_decisions(team3, promote_decisions)
ahl_names = {p.first_name for p in team3.ahl_roster}
prospect_names = {p.first_name for p in team3.prospects}
check("unsigned prospect NOT promoted", "Unsigned" not in ahl_names,
      str(ahl_names))
check("junior-track signed prospect NOT sent to AHL",
      "JuniorKid" not in ahl_names and "JuniorKid" in prospect_names,
      f"ahl={ahl_names}")
check("AHL-eligible signed prospect promoted",
      "AhlReady" in ahl_names, str(ahl_names))

# ---------------------------------------------------------------------------
# 8. Strategy reflects identity
# ---------------------------------------------------------------------------

mgr4 = AITeamManager()
mgr4._league_ref = FakeLeague()
hot_gm_team = make_team("HotGMs", aggressor, roster_ovr=68, roster_age=31)
mgr4.initialize_team_strategies([hot_gm_team])
# Force the hot seat, then refresh.
sec_h = mgr4.gm_security["HotGMs"]
sec_h.confidence = 20.0
sec_h.hot_seat = True
mgr4.team_strategies["HotGMs"] = mgr4._generate_team_strategy(
    hot_gm_team, mgr4.gm_identities["HotGMs"], sec_h)
strat_h = mgr4.team_strategies["HotGMs"]
from ai_team_management import ManagementPriority, TradePreference
check("aggressive GM trades aggressively",
      strat_h.trade_preference in (TradePreference.AGGRESSIVE,
                                   TradePreference.MODERATE),
      str(strat_h.trade_preference))
check("hot-seat old roster goes win-now, not rebuild",
      strat_h.priority != ManagementPriority.REBUILD,
      str(strat_h.priority))
check("strategy risk follows identity, not random",
      abs(strat_h.risk_tolerance - compute_risk_appetite(
          mgr4.gm_identities["HotGMs"], sec_h)) < 1e-6,
      f"{strat_h.risk_tolerance}")

# ---------------------------------------------------------------------------
# 9. End-to-end headless run executes signings
# ---------------------------------------------------------------------------

mgr5 = AITeamManager()
fl = FakeLeague(season_year=2026)
mgr5._league_ref = fl
team5 = make_team("EndToEnd", aggressor)
team5.prospects = [make_prospect("SignMe", "EndToEnd", grade="A-", age=20,
                                 ovr=73, rights_years_left=1)]
mgr5.initialize_team_strategies([team5])
mgr5.last_decision_date = date(2026, 10, 1)
decisions = mgr5.process_daily_decisions([team5], [], date(2026, 10, 15))
sign_types = [d.decision_type for d in decisions]
check("end-to-end produced a signing decision", "sign_prospect" in sign_types,
      str(sign_types))
check("signing actually executed via league",
      any(n == "SignMe" for _, n in fl.signed),
      str(fl.signed))
check("signed prospect now has a contract",
      team5.prospects[0].contract is not None)

# ---------------------------------------------------------------------------
# 10. Hot-seat behavior is the GM's own, not one-size-fits-all
# ---------------------------------------------------------------------------
# pressure_response calibration: the aggressor panics, the builder trusts
# his vision, the fallback sits in the middle.
check("aggressor pressure_response high", ident.pressure_response >= 0.7,
      f"{ident.pressure_response:.2f}")
check("builder pressure_response low", ident_b.pressure_response <= 0.2,
      f"{ident_b.pressure_response:.2f}")
check("fallback pressure_response middle",
      fallback.pressure_response == 0.5,
      f"{fallback.pressure_response:.2f}")

# Same hot seat, different men: the aggressor's risk jumps, the builder's
# barely moves.
risk_hot_builder = compute_risk_appetite(ident_b, sec_hot)
check("hot-seat aggressor riskier than hot-seat builder",
      risk_hot > risk_hot_builder + 0.15,
      f"{risk_hot:.2f} vs {risk_hot_builder:.2f}")
check("hot-seat builder barely above his stable self",
      risk_hot_builder - compute_risk_appetite(ident_b, sec_mid) < 0.08,
      f"{risk_hot_builder:.2f}")

# signing_urgency likewise: the builder doesn't rush his kids.
u_hot_b = signing_urgency(ident_b, sec_hot)
u_mid_b = signing_urgency(ident_b, sec_mid)
u_hot_a = signing_urgency(ident, sec_hot)
u_mid_a = signing_urgency(ident, sec_mid)
check("builder signing urgency barely moves on hot seat",
      u_hot_b - u_mid_b < 0.05, f"{u_hot_b:.2f} vs {u_mid_b:.2f}")
check("aggressor signing urgency jumps on hot seat",
      u_hot_a - u_mid_a > 0.08, f"{u_hot_a:.2f} vs {u_mid_a:.2f}")

# Strategy: the builder on the hot seat keeps rebuilding (trusts his
# vision); the aggressor flips to win-now.
mgr10 = AITeamManager()
mgr10._league_ref = FakeLeague()
old_builder_team = make_team("OldBuilders", builder, roster_ovr=68,
                             roster_age=31)
mgr10.initialize_team_strategies([old_builder_team])
sec_ob = mgr10.gm_security["OldBuilders"]
sec_ob.confidence = 25.0
sec_ob.hot_seat = True
strat_ob = mgr10._generate_team_strategy(
    old_builder_team, mgr10.gm_identities["OldBuilders"], sec_ob)
check("patient builder on hot seat keeps building",
      strat_ob.priority == ManagementPriority.REBUILD,
      str(strat_ob.priority))
check("builder does not trade prospects in panic",
      not strat_ob.will_trade_prospects)

# Owner warning: the leash comes from the owner, never from a stat line.
# Confidence sinks into the danger zone -> the owner issues the ultimatum:
# win 3 of the next 5 or you're done. Only then is the GM leashed.
team_w = make_team("Warned", aggressor, roster_ovr=68, roster_age=31)
team_w.wins, team_w.losses, team_w.ot_losses = 5, 40, 5
sec_w2 = GMJobSecurity(team_name="Warned", expectation="contend",
                       confidence=12.0)
update_job_security(sec_w2, ident, team_w, None, 2027)
check("cratered confidence -> owner warning", sec_w2.owner_warning,
      sec_w2.describe())
# A merely bad GM gets leash: no warning at 20.
team_ok = make_team("Mediocre", aggressor, roster_ovr=68, roster_age=31)
team_ok.wins, team_ok.losses, team_ok.ot_losses = 12, 30, 5
sec_ok = GMJobSecurity(team_name="Mediocre", expectation="contend",
                       confidence=20.0)
update_job_security(sec_ok, ident, team_ok, None, 2027)
check("bad-but-not-cratered GM gets leash", not sec_ok.owner_warning,
      sec_ok.describe())
check("warning terms are 3 wins in 5 games",
      sec_w2.warning_wins_needed == 3 and sec_w2.warning_games_left == 5,
      sec_w2.describe())
check("warned GM still flagged hot seat", sec_w2.hot_seat)
check("warned risk capped despite panic wiring",
      compute_risk_appetite(ident, sec_w2) <= 0.45,
      f"{compute_risk_appetite(ident, sec_w2):.2f}")
mgr10.gm_identities["Warned"] = ident
mgr10.gm_security["Warned"] = sec_w2
strat_w = mgr10._generate_team_strategy(team_w, ident, sec_w2)
check("warned GM cannot trade picks", not strat_w.will_trade_picks)
check("warned GM cannot trade prospects", not strat_w.will_trade_prospects)
check("warned GM does not flip rebuild to win-now",
      strat_w.priority == ManagementPriority.REBUILD,
      str(strat_w.priority))

# No warning without the owner: a rebuild board stays patient even when
# confidence craters.
team_rb = make_team("Rebuilders", aggressor, roster_ovr=60, roster_age=24)
team_rb.wins, team_rb.losses, team_rb.ot_losses = 5, 40, 5
sec_rb = GMJobSecurity(team_name="Rebuilders", expectation="rebuild",
                       confidence=10.0)
update_job_security(sec_rb, ident, team_rb, None, 2027)
check("rebuild expectation -> no owner warning", not sec_rb.owner_warning,
      sec_rb.describe())

# Surviving the warning: win 3 of the next 5 -> the owner backs off.
team_w.wins, team_w.losses = 8, 42  # 3-2 since the warning
update_job_security(sec_w2, ident, team_w, None, 2027)
check("surviving the warning lifts it", not sec_w2.owner_warning,
      sec_w2.describe())
check("surviving the warning rebuilds confidence",
      sec_w2.confidence > 12.0, f"{sec_w2.confidence:.1f}")

# Failing the warning: lose out -> you're done. The manager installs an
# interim GM and resets the seat.
team_f = make_team("Fired", aggressor, roster_ovr=68, roster_age=31)
team_f.wins, team_f.losses, team_f.ot_losses = 5, 40, 5
sec_f = GMJobSecurity(team_name="Fired", expectation="contend",
                      confidence=12.0)
update_job_security(sec_f, ident, team_f, None, 2027)
check("warning issued before the slide", sec_f.owner_warning)
team_f.wins, team_f.losses = 5, 45  # 0-5 since the warning: failed
update_job_security(sec_f, ident, team_f, None, 2027)
check("failed warning -> gm_fired", sec_f.gm_fired, sec_f.describe())
check("failed warning clears the warning", not sec_f.owner_warning)
mgr10.gm_identities["Fired"] = ident
mgr10.gm_security["Fired"] = sec_f
mgr10.team_strategies["Fired"] = mgr10._generate_team_strategy(
    team_f, ident, sec_f)
mgr10._sec_flags["Fired"] = (True, False, False)
mgr10._weekly_board_review(team_f, date(2026, 11, 1))
check("fired GM replaced by interim",
      mgr10.gm_identities["Fired"].gm_name == "Interim GM",
      mgr10.gm_identities["Fired"].describe())
check("seat resets to honeymoon after firing",
      mgr10.gm_security["Fired"].confidence == 55.0
      and not mgr10.gm_security["Fired"].hot_seat)

# Mathematically eliminated early: 3 losses in the first 3 -> done now,
# not in 2 more games.
team_e = make_team("Eliminated", aggressor, roster_ovr=68, roster_age=31)
team_e.wins, team_e.losses, team_e.ot_losses = 5, 40, 5
sec_e = GMJobSecurity(team_name="Eliminated", expectation="contend",
                      confidence=12.0)
update_job_security(sec_e, ident, team_e, None, 2027)
team_e.losses = 43  # 0-3 since the warning: can't reach 3 wins in 2 games
update_job_security(sec_e, ident, team_e, None, 2027)
check("elimination fires immediately", sec_e.gm_fired, sec_e.describe())

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

print(f"\n{'='*60}\nQA ai_gm_identity: {PASS} passed, {FAIL} failed")
for f in FAILURES:
    print(f"  FAIL: {f}")
sys.exit(1 if FAIL else 0)
