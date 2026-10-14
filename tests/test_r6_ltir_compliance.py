"""R6: close the LTIR phantom-relief exploit.

Acceptance: when a player is healed but unaffordable, a day-advance
blocker forces compliance; in a season-long sim no healthy player remains
parked on LTIR -- the player must be ACTIVATED off LTIR (roster
compliant), not merely have relief zeroed. Headless runs use scripted
compliance (auto-shed lowest-value movable salary) so the blocker never
hangs the sim.

Each test is named for the invariant it asserts.
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_classes import Player, PlayerPosition, Contract, Team
import ir_system as irs
import salary_cap_system as scs

CAP = 104_000_000


def _mk(name, salary, term, ovr=80, age=20, pos=PlayerPosition.CENTER,
        two_way=True):
    p = Player("T", name, age, pos)
    p.overall_rating = lambda: ovr  # noqa: E731 -- deterministic test overall
    c = Contract(salary=salary, years_remaining=term)
    c.two_way = two_way
    c.ahl_salary = 900_000
    p.contract = c
    p.is_injured = False
    p.games_remaining_injured = 0
    p.ir_status = "None"
    p.ir_placed_date = ""
    return p


def _over_cap_team_with_parked_star():
    """23-man club, $111M charge, $9M star healed but parked on LTIR.

    Relief ($9M) lets the club sit over the cap; activating the star
    removes his relief, leaving a $7M shortfall -- the R6 exploit state.
    Two-way waiver-exempt fillers + AHL backfill make scripted compliance
    possible.
    """
    t = Team("Test Team", "Test City", "Div", "Conf")
    t.salary_cap = CAP
    star = _mk("Star", 9_000_000, 5, ovr=92, age=27, two_way=False)
    t.roster = ([_mk(f"Skater{i}", 4_800_000, 3, ovr=78) for i in range(20)]
                + [_mk("GoalieA", 3_000_000, 3, ovr=80,
                       pos=PlayerPosition.GOALIE),
                   _mk("GoalieB", 3_000_000, 3, ovr=80,
                       pos=PlayerPosition.GOALIE)]
                + [star])
    t.ahl_roster = [_mk(f"Farm{i}", 900_000, 2, ovr=70) for i in range(6)]
    star.is_injured = True
    star.games_remaining_injured = 30
    ok, _ = irs.place_on_ltir(t, star, "2026-10-01")
    assert ok, "test setup: LTIR placement must succeed"
    star.is_injured = False
    star.games_remaining_injured = 0
    return t, star


def test_r6_healed_ltir_parked_detected_with_shortfall():
    # Invariant: a healed player who cannot afford activation is reported
    # by healed_ltir_blocked with a positive dollar shortfall -- the
    # exploit state is observable, not silent.
    t, star = _over_cap_team_with_parked_star()
    blocked = irs.healed_ltir_blocked(t)
    assert len(blocked) == 1
    p, short = blocked[0]
    assert p is star
    assert short == 7_000_000, f"expected $7M shortfall, got ${short:,}"
    # Genuinely injured players are not the exploit.
    star.is_injured = True
    star.games_remaining_injured = 5
    assert irs.healed_ltir_blocked(t) == []


def test_r6_scripted_compliance_activates_healed_player_off_ltir():
    # Invariant: scripted compliance ACTIVATES the healed player off LTIR
    # (ir_status "None") with the club cap-compliant -- relief is not
    # merely zeroed. Only lowest-value movable salary is shed; the star
    # and every valuable contract are untouched.
    t, star = _over_cap_team_with_parked_star()
    before = {id(p): p.contract.salary for p in t.roster}
    ok, msg = irs.auto_activate_healed_ltir(t, star, date(2026, 11, 1))
    assert ok, f"scripted compliance must succeed: {msg}"
    assert irs.ir_status_of(star) == "None", "player must be OFF ltir"
    assert star in t.roster, "star stays on the NHL roster"
    assert irs.is_compliant_with_ltir(t), "club must be cap-compliant"
    assert scs.compliance_charge(t) <= CAP, "charge must fit under the cap"
    assert irs.healed_ltir_blocked(t) == [], "nothing parked afterwards"
    # The star's own deal is never the thing shed.
    assert star.contract.salary == 9_000_000
    # Nobody valuable was touched: every remaining rostered player keeps
    # his exact salary.
    for p in t.roster:
        assert p.contract.salary == before[id(p)]
    # The shed came from the low-value end (demoted fillers are gone from
    # the NHL roster or paper-swapped for cheaper AHL bodies).
    assert len(t.roster) < 23


def test_r6_no_safe_move_reports_instead_of_gambling():
    # Invariant: when every dollar is locked in valuable waiver-eligible
    # contracts, scripted compliance reports the constraint and does NOT
    # activate the player, does NOT touch valuable players (standing
    # auto-resolve rule: report why instead of gambling).
    # This is the ONE stated exception to "no healthy player remains
    # parked on LTIR": forcing the activation would break cap compliance
    # or waive a valuable player, both worse than a visible, reported
    # stuck state. (The report surfaces via ai_manage_ir's
    # ltir_still_parked -- see test_r6_no_safe_move_reports_through_ai_manage_ir.)
    t = Team("Locked Team", "Test City", "Div", "Conf")
    t.salary_cap = CAP
    star = _mk("Star", 9_000_000, 5, ovr=92, age=27, two_way=False)
    t.roster = ([_mk(f"Vet{i}", 4_800_000, 4, ovr=82, age=29, two_way=False)
                 for i in range(20)]
                + [_mk("GoalieA", 3_000_000, 4, ovr=82, age=29,
                       pos=PlayerPosition.GOALIE, two_way=False),
                   _mk("GoalieB", 3_000_000, 4, ovr=82, age=29,
                       pos=PlayerPosition.GOALIE, two_way=False)]
                + [star])
    t.ahl_roster = []
    star.is_injured = True
    star.games_remaining_injured = 30
    ok, _ = irs.place_on_ltir(t, star, "2026-10-01")
    assert ok
    star.is_injured = False
    star.games_remaining_injured = 0
    assert irs.healed_ltir_blocked(t), "exploit state must be detected"

    before_ids = {id(p) for p in t.roster}
    ok, msg = irs.auto_activate_healed_ltir(t, star, date(2026, 11, 1))
    assert not ok, "compliance must fail when no safe move exists"
    assert "Cannot free" in msg or "no safe move" in msg.lower() or \
        "locked" in msg.lower(), f"reason must name the constraint: {msg}"
    assert irs.ir_status_of(star) == "LTIR", "player stays parked"
    assert {id(p) for p in t.roster} == before_ids, \
        "no valuable player may be moved"


def test_r6_ai_manage_ir_activates_healed_ltir():
    # Invariant: the AI path (ai_manage_ir, used for all non-user clubs in
    # the daily sim) runs scripted compliance too -- a healed AI player is
    # activated off LTIR, not parked forever.
    t, star = _over_cap_team_with_parked_star()
    done = irs.ai_manage_ir(t, date(2026, 11, 1))
    assert done["activated"] == 1, f"AI must activate the healed player: {done}"
    assert irs.ir_status_of(star) == "None"
    assert irs.healed_ltir_blocked(t) == []
    assert irs.is_compliant_with_ltir(t)


def test_r6_day_advance_blocker_fires_for_user_team():
    # Invariant: the user club gets a day-advance blocker (id
    # 'ltir_compliance', mirroring the cap blocker shape) while a healed
    # player is parked on LTIR, and its auto_action -- the headless
    # scripted compliance -- clears it.
    from game_manager import GameManager
    t, star = _over_cap_team_with_parked_star()
    gm = GameManager.__new__(GameManager)
    gm.user_team = t
    gm.news_log = []
    gm.current_date = date(2026, 11, 1)

    blocker = gm._ltir_compliance_blocker()
    assert blocker is not None, "blocker must fire for the parked player"
    assert blocker["id"] == "ltir_compliance"
    assert "auto_action" in blocker, "headless sims need scripted compliance"

    label, cb = blocker["auto_action"]
    assert cb() is not False, "scripted compliance must make progress"
    assert gm._ltir_compliance_blocker() is None, "blocker must clear"
    assert irs.ir_status_of(star) == "None"
    assert irs.is_compliant_with_ltir(t)


def test_r6_blocker_auto_returns_affordable_healed_player():
    # Invariant: a healed LTIR player the club CAN already afford is
    # returned automatically at the day gate -- no blocker, no parking.
    from game_manager import GameManager
    t = Team("Room Team", "Test City", "Div", "Conf")
    t.salary_cap = CAP
    star = _mk("Star", 9_000_000, 5, ovr=92, age=27, two_way=False)
    t.roster = ([_mk(f"Skater{i}", 3_000_000, 3, ovr=76) for i in range(20)]
                + [_mk("GoalieA", 2_000_000, 3, ovr=78,
                       pos=PlayerPosition.GOALIE),
                   _mk("GoalieB", 2_000_000, 3, ovr=78,
                       pos=PlayerPosition.GOALIE)]
                + [star])
    t.ahl_roster = []
    star.is_injured = True
    star.games_remaining_injured = 30
    ok, _ = irs.place_on_ltir(t, star, "2026-10-01")
    assert ok
    star.is_injured = False
    star.games_remaining_injured = 0
    # Charge $73M: affordable even after the $9M relief comes off.
    assert scs.compliance_charge(t) < CAP

    gm = GameManager.__new__(GameManager)
    gm.user_team = t
    gm.news_log = []
    gm.current_date = date(2026, 11, 1)
    assert gm._ltir_compliance_blocker() is None, \
        "affordable player must auto-return, not block"
    assert irs.ir_status_of(star) == "None"


def test_r6_multi_parked_auto_action_reports_progress_per_player():
    # Invariant: with TWO healed players parked, the first blocker's
    # auto_action reports progress (True) once ITS player activates --
    # even though the second player remains blocked. The headless loop
    # must not strand a working fix behind a misleading False; the
    # second player gets his own fresh blocker round.
    from game_manager import GameManager
    t = Team("Two Parked", "Test City", "Div", "Conf")
    t.salary_cap = CAP
    star1 = _mk("Star1", 9_000_000, 5, ovr=92, age=27, two_way=False)
    star2 = _mk("Star2", 8_000_000, 5, ovr=90, age=28, two_way=False)
    t.roster = ([_mk(f"Skater{i}", 4_800_000, 3, ovr=78) for i in range(19)]
                + [_mk("GoalieA", 3_000_000, 3, ovr=80,
                       pos=PlayerPosition.GOALIE),
                   _mk("GoalieB", 3_000_000, 3, ovr=80,
                       pos=PlayerPosition.GOALIE)]
                + [star1, star2])
    t.ahl_roster = [_mk(f"Farm{i}", 900_000, 2, ovr=70) for i in range(8)]
    for star in (star1, star2):
        star.is_injured = True
        star.games_remaining_injured = 30
        ok, _ = irs.place_on_ltir(t, star, "2026-10-01")
        assert ok
        star.is_injured = False
        star.games_remaining_injured = 0
    assert len(irs.healed_ltir_blocked(t)) == 2

    gm = GameManager.__new__(GameManager)
    gm.user_team = t
    gm.news_log = []
    gm.current_date = date(2026, 11, 1)

    blocker = gm._ltir_compliance_blocker()
    assert blocker is not None and blocker["id"] == "ltir_compliance"
    _label, cb = blocker["auto_action"]
    assert cb() is True, \
        "auto_action must report progress once its player activates"
    # Exactly one parked player remains; a fresh blocker names him.
    remaining = irs.healed_ltir_blocked(t)
    assert len(remaining) == 1, \
        f"one player should remain parked, got {len(remaining)}"
    blocker2 = gm._ltir_compliance_blocker()
    assert blocker2 is not None
    _label2, cb2 = blocker2["auto_action"]
    assert cb2() is True
    assert irs.healed_ltir_blocked(t) == []
    assert irs.is_compliant_with_ltir(t)


def test_r6_get_continue_state_wires_ltir_blocker():
    # Invariant (integration -- reviewer C FAIL-2): the ltir_compliance
    # blocker reaches the day gate through its REAL production entry
    # point, get_continue_state(), not just the direct method call.
    # Deleting the wiring block in get_continue_state must fail this
    # test while the unit tests stay green.
    from game_manager import GameManager
    t, star = _over_cap_team_with_parked_star()
    gm = GameManager.__new__(GameManager)
    gm.user_team = t
    gm.news_log = []
    gm.current_date = date(2026, 11, 1)

    _label, blockers = gm.get_continue_state()
    ids = [b.get("id") for b in (blockers or [])]
    assert "ltir_compliance" in ids, (
        f"production day gate must surface the LTIR blocker, got {ids}")
    b = next(b for b in blockers if b.get("id") == "ltir_compliance")
    assert "auto_action" in b, "headless sims need the scripted auto_action"


def test_r6_dayloop_resolver_runs_scripted_compliance():
    # Invariant (integration -- reviewer C FAIL-2): the headless
    # harness resolves a REAL ltir_compliance blocker dict through the
    # production _RESOLVERS entry (the path the season probe uses), and
    # the player ends up ACTIVATED off LTIR, not merely unblocked.
    from types import SimpleNamespace
    from game_manager import GameManager
    from playthrough_harness_A.dayloop import _RESOLVERS
    t, star = _over_cap_team_with_parked_star()
    gm = GameManager.__new__(GameManager)
    gm.user_team = t
    gm.news_log = []
    gm.current_date = date(2026, 11, 1)

    blocker = gm._ltir_compliance_blocker()
    assert blocker is not None and blocker["id"] == "ltir_compliance"
    app = SimpleNamespace(game_manager=gm)
    logged = []
    how = _RESOLVERS["ltir_compliance"](app, app.game_manager, blocker,
                                        logged.append)
    assert "ltir_compliance" in how, f"resolver must report what it did: {how}"
    assert irs.ir_status_of(star) == "None", "player must be off LTIR"
    assert irs.is_compliant_with_ltir(t), "club must be cap-compliant"
    assert gm._ltir_compliance_blocker() is None, "blocker must clear"


def _locked_team_with_parked_star():
    """Two locked clubs worth of fixture: every dollar is in valuable
    waiver-eligible deals, so scripted compliance has no safe move."""
    t = Team("Locked Team", "Test City", "Div", "Conf")
    t.salary_cap = CAP
    star = _mk("Star", 9_000_000, 5, ovr=92, age=27, two_way=False)
    t.roster = ([_mk(f"Vet{i}", 4_800_000, 4, ovr=82, age=29, two_way=False)
                 for i in range(20)]
                + [_mk("GoalieA", 3_000_000, 4, ovr=82, age=29,
                       pos=PlayerPosition.GOALIE, two_way=False),
                   _mk("GoalieB", 3_000_000, 4, ovr=82, age=29,
                       pos=PlayerPosition.GOALIE, two_way=False)]
                + [star])
    t.ahl_roster = []
    star.is_injured = True
    star.games_remaining_injured = 30
    ok, _ = irs.place_on_ltir(t, star, "2026-10-01")
    assert ok
    star.is_injured = False
    star.games_remaining_injured = 0
    return t, star


def test_r6_no_safe_move_reports_through_ai_manage_ir():
    # Invariant (reviewer C FAIL-1): when scripted compliance finds no
    # safe move, the constraint is REPORTED through ai_manage_ir's
    # result (ltir_still_parked) instead of being swallowed -- the
    # standing auto-resolve rule says "reports why", so the why must
    # reach the caller. The tuple carries the player ref so the caller
    # can dedup on (player, team, reason).
    t, star = _locked_team_with_parked_star()

    done = irs.ai_manage_ir(t, date(2026, 11, 1))
    assert done["activated"] == 0
    stuck = done.get("ltir_still_parked") or []
    assert len(stuck) == 1, f"the stuck player must be reported: {done}"
    _p, _name, _why = stuck[0]
    assert _p is star, "report must carry the player ref for caller dedup"
    assert "Star" in _name and _why, "report must name the player and the why"


def test_r6_stuck_report_dedup_player_team_reason():
    # Invariant (reviewer C delta HOLE A/B/C): _report_ltir_stuck dedups
    # on (player, team, reason) and marks reported ONLY after successful
    # delivery.
    # - same player/team/reason twice -> one news item (no spam);
    # - player traded to a new club -> re-reports (HOLE A);
    # - changed shortfall -> re-reports (HOLE C);
    # - delivery failure -> not marked, retries (HOLE B).
    from game_manager import GameManager
    t, star = _locked_team_with_parked_star()
    gm = GameManager.__new__(GameManager)
    gm.news_log = []
    gm.current_date = date(2026, 11, 1)
    # add_news needs news_log + current_date; keep _ui_notify absent (ok).

    done = irs.ai_manage_ir(t, date(2026, 11, 1))
    stuck = done["ltir_still_parked"]
    gm._report_ltir_stuck(t, stuck)
    assert len(gm.news_log) == 1, "first report must land"
    assert "remains on LTIR" in gm.news_log[0]["story"]
    gm._report_ltir_stuck(t, stuck)
    assert len(gm.news_log) == 1, "same sig must not spam"

    # HOLE A: traded to a new (also locked) club -> re-report.
    t2, _ = _locked_team_with_parked_star()
    t2.team_name = "Other Club"
    t2.roster.remove(t2.roster[-1])  # drop t2's own star; use ours
    t2.roster.append(star)
    done2 = irs.ai_manage_ir(t2, date(2026, 11, 2))
    assert done2["ltir_still_parked"], "star is stuck on the new club too"
    gm._report_ltir_stuck(t2, done2["ltir_still_parked"])
    assert len(gm.news_log) == 2, "new club must re-report (HOLE A)"
    assert "Other Club" in gm.news_log[1]["story"]

    # HOLE C: changed reason -> re-report.
    _p, _name, _why = stuck[0]
    gm._report_ltir_stuck(t, [(_p, _name, _why + " (updated)")])
    assert len(gm.news_log) == 3, "changed reason must re-report (HOLE C)"

    # HOLE B: delivery failure -> not marked; retries after the fix.
    gm2 = GameManager.__new__(GameManager)
    gm2.current_date = date(2026, 11, 1)
    # no news_log: add_news raises AttributeError, swallowed by design.
    gm2._report_ltir_stuck(t, stuck)
    assert not hasattr(gm2, "_ltir_stuck_reported") or \
        len(gm2._ltir_stuck_reported) == 0, \
        "failed delivery must not be marked reported (HOLE B)"
    gm2.news_log = []
    gm2._report_ltir_stuck(t, stuck)
    assert len(gm2.news_log) == 1, "retry after fix must deliver"
