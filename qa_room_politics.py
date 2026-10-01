# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: room politics -- practice planner, captaincy crises, coaching carousel.

Even-playing-field checks: AI and user run the same functions; only the
choices differ (automated vs GM-made).
"""
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import dressing_room as dr


def make_player(name, morale=70, leadership=60, captaincy="", age=28,
                position="C"):
    return SimpleNamespace(
        id=f"p_{name}", name=name, morale=morale, leadership=leadership,
        captaincy=captaincy, age=age, position=position,
        team_tenure_years=2, discipline=60, composure=60, aggressiveness=50,
        teamwork=60, coach_bonds={},)


def make_coach(name, style_attrs):
    c = SimpleNamespace(id=f"c_{name}", name=name, gm_trust=70,
                        shelf_weeks=0, past_clubs=[],
                        motivating=65, man_management=65, discipline=65,
                        tactical_knowledge=65, game_preparation=65,
                        working_with_youngsters=65, player_development=65,
                        leadership=65, influence=70,
                        role=SimpleNamespace(value="Head Coach"))
    for k, v in style_attrs.items():
        setattr(c, k, v)
    return c


def demanding_coach():
    # drill_sergeant: discipline high, man_management low
    return make_coach("Torts", {"discipline": 95, "motivating": 75,
                                "man_management": 35})


def players_coach():
    # players_coach: man_management high, discipline low
    return make_coach("Teddy", {"discipline": 40, "motivating": 80,
                                "man_management": 95})


def make_team(coach=None, n=12):
    roster = [make_player(f"Player{i}") for i in range(n)]
    team = SimpleNamespace(
        team_name="Test Club", roster=roster, head_coach=coach,
        staff=[coach] if coach is not None else [],
        tactics_familiarity=80.0, is_user_team=False)
    return team


def make_league(team, losing_streak=0, win_pct=0.5):
    w = int(win_pct * 10)
    st = {"W": w, "L": 10 - w, "OTL": 0, "losing_streak": losing_streak}
    return SimpleNamespace(standings={team.team_name: st})


class T:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, name, cond):
        if cond:
            self.passed += 1
        else:
            self.failed += 1
            print(f"FAIL: {name}")

    def report(self, label):
        print(f"{label}: {self.passed} passed, {self.failed} failed")


def test_practice_basics(t):
    random.seed(7)
    team = make_team(coach=demanding_coach())
    for focus in dr.PRACTICE_FOCI:
        rec = dr.run_weekly_practice(team, focus=focus, intensity="moderate",
                                     date_str="2026-10-04")
        t.check(f"practice runs: {focus}", bool(rec) and rec["focus"] == focus)
        t.check(f"receipt has goal: {focus}", bool(rec.get("goal")))
    receipts = dr.ensure_dressing_room_fields(team)["practice_receipts"]
    t.check("receipts logged (5)", len(receipts) == 5)


def test_coach_style_effectiveness(t):
    random.seed(7)
    t1 = make_team(coach=demanding_coach())
    t2 = make_team(coach=players_coach())
    e_dem_cond = dr.practice_effectiveness(
        t1, t1.head_coach, "conditioning", "moderate")["effectiveness"]
    e_pc_cond = dr.practice_effectiveness(
        t2, t2.head_coach, "conditioning", "moderate")["effectiveness"]
    t.check("demanding > players-coach on conditioning",
            e_dem_cond > e_pc_cond)
    e_dem_rec = dr.practice_effectiveness(
        t1, t1.head_coach, "recovery", "moderate")["effectiveness"]
    e_pc_rec = dr.practice_effectiveness(
        t2, t2.head_coach, "recovery", "moderate")["effectiveness"]
    t.check("players-coach > demanding on recovery", e_pc_rec > e_dem_rec)
    t.check("demanding axis ~1.0",
            dr.coach_demanding_axis(t1.head_coach) >= 0.9)
    t.check("players-coach axis ~0.0",
            dr.coach_demanding_axis(t2.head_coach) <= 0.1)


def test_assistant_session_match(t):
    random.seed(7)
    asst = SimpleNamespace(id="a1", name="PP Guru", attacking_coaching=90,
                           defensive_coaching=50, coaching_goalies=40)
    asst.role = SimpleNamespace(value="Assistant Coach")
    team = make_team(coach=demanding_coach())
    team.staff = [team.head_coach, asst]
    matched = dr.assistant_session_match(team, "special_teams")
    t.check("assistant found", len(matched) == 1)
    t.check("session match on special teams", matched[0]["matched"] is True)
    e_with = dr.practice_effectiveness(
        team, team.head_coach, "special_teams", "moderate")["effectiveness"]
    team.staff = [team.head_coach]
    e_without = dr.practice_effectiveness(
        team, team.head_coach, "special_teams", "moderate")["effectiveness"]
    t.check("matched assistant adds effectiveness", e_with > e_without)


def test_bag_skate_costs(t):
    random.seed(7)
    team = make_team(coach=demanding_coach())
    coach = team.head_coach
    trust0 = coach.gm_trust
    dr.run_weekly_practice(team, focus="conditioning", intensity="hard",
                           bag_skate=True, date_str="2026-10-04")
    t.check("bag skate banks one-game edge",
            dr.ensure_dressing_room_fields(team).get("practice_edge") == 0.02)
    cost1 = trust0 - coach.gm_trust
    t.check("first bag skate costs trust", cost1 >= 3)
    dr.run_weekly_practice(team, focus="conditioning", intensity="hard",
                           bag_skate=True, date_str="2026-10-11")
    cost2 = cost1 + (trust0 - cost1 - coach.gm_trust)
    t.check("repeated punishment costs MORE trust", cost2 > cost1)
    receipts = dr.ensure_dressing_room_fields(team)["practice_receipts"]
    t.check("bag skate logged in receipt", receipts[-1]["bag_skate"] is True)


def test_practice_edge_consumed(t):
    random.seed(7)
    home = make_team(coach=demanding_coach())
    away = make_team(coach=players_coach())
    dr.run_weekly_practice(home, focus="conditioning", intensity="hard",
                           bag_skate=True, date_str="2026-10-04")
    nudges = []
    import impact_system as imp
    real = imp.nudge_momentum
    imp.nudge_momentum = lambda sim, team, strength=1.0: nudges.append(team)
    try:
        sim = SimpleNamespace(home_team=home, away_team=away)
        dr.apply_practice_edge(sim)
    finally:
        imp.nudge_momentum = real
    t.check("edge nudges the edged team", nudges == [home])
    t.check("edge zeroes after one game",
            dr.ensure_dressing_room_fields(home).get("practice_edge") == 0.0)


def test_receipt_goal_resolution(t):
    random.seed(7)
    team = make_team(coach=demanding_coach())
    team.tactics_familiarity = 70.0
    dr.run_weekly_practice(team, focus="systems", intensity="hard",
                           date_str="2026-10-04")
    first = dr.ensure_dressing_room_fields(team)["practice_receipts"][-1]
    t.check("systems goal pending", first["goal_met"] is None)
    # Familiarity rose from the practice itself; next week's planning scores it.
    dr.run_weekly_practice(team, focus="recovery", intensity="light",
                           date_str="2026-10-11")
    t.check("systems goal resolved met", first["goal_met"] is True)


def test_crisis_detection(t):
    random.seed(7)
    team = make_team(coach=demanding_coach())
    cap = team.roster[0]
    cap.captaincy = "C"
    cap.leadership = 30  # weak captain
    # D32: influence_of now delegates to hierarchy_score (canonical).
    # Give the mocks realistic reputation/tenure so the intended
    # weak-C vs strong-A dynamic holds on the canonical scale.
    cap.reputation = 20
    cap.team_tenure = "This season"
    alt = team.roster[1]
    alt.captaincy = "A"
    alt.leadership = 95  # the room's real voice
    alt.reputation = 65
    alt.team_tenure = "4+ years"
    for p in team.roster:
        p.morale = 35  # room sour
    league = make_league(team, losing_streak=4)
    crisis = dr.detect_captaincy_crisis(team, league)
    t.check("crisis triggers when all three agree", crisis is not None)
    t.check("crisis names captain",
            crisis["captain_name"] == cap.name if crisis else False)
    # Happy room -> no crisis
    for p in team.roster:
        p.morale = 75
    t.check("no crisis when room is fine",
            dr.detect_captaincy_crisis(team, league) is None)


def test_crisis_resolutions(t):
    random.seed(11)
    for choice in ("keep", "challenge", "strip", "reassign"):
        team = make_team(coach=demanding_coach())
        cap = team.roster[0]
        cap.captaincy = "C"
        cap.leadership = 30
        alt = team.roster[1]
        alt.captaincy = "A"
        alt.leadership = 95
        for p in team.roster:
            p.morale = 35
        lines = dr.resolve_captaincy_crisis(team, choice,
                                            new_captain=alt,
                                            date_str="2026-10-04")
        t.check(f"resolution runs: {choice}", bool(lines))
        receipts = dr.ensure_dressing_room_fields(team)["practice_receipts"]
        t.check(f"authority receipt logged: {choice}",
                receipts and receipts[-1]["kind"] == "authority")
    # Strip removes the C
    team = make_team(coach=demanding_coach())
    cap = team.roster[0]
    cap.captaincy = "C"
    dr.resolve_captaincy_crisis(team, "strip", date_str="2026-10-04")
    t.check("strip removes captaincy", cap.captaincy == "")
    # Reassign hands it over
    team = make_team(coach=demanding_coach())
    cap = team.roster[0]
    cap.captaincy = "C"
    alt = team.roster[1]
    alt.captaincy = "A"
    alt.leadership = 95
    dr.resolve_captaincy_crisis(team, "reassign", new_captain=alt,
                                date_str="2026-10-04")
    t.check("reassign sets new captain", alt.captaincy == "C")
    # Keep keeps the C
    team = make_team(coach=demanding_coach())
    cap = team.roster[0]
    cap.captaincy = "C"
    dr.resolve_captaincy_crisis(team, "keep", date_str="2026-10-04")
    t.check("keep keeps the C", cap.captaincy == "C")


def test_auto_resolve(t):
    random.seed(7)
    team = make_team(coach=demanding_coach())
    cap = team.roster[0]
    cap.captaincy = "C"
    cap.leadership = 30
    alt = team.roster[1]
    alt.captaincy = "A"
    alt.leadership = 95
    crisis = {"captain": cap, "captain_name": cap.name,
              "challengers": [alt], "challenger_names": [alt.name],
              "severity": 2}
    lines = dr.auto_resolve_crisis(team, crisis, date_str="2026-10-04")
    t.check("AI resolves crisis", bool(lines))
    # Same resolution functions as the user path
    t.check("AI path logged as authority",
            dr.ensure_dressing_room_fields(team)["practice_receipts"][-1][
                "kind"] == "authority")


def test_carousel(t):
    random.seed(7)
    dr.COACH_CAROUSEL.clear()
    team = make_team(coach=demanding_coach())
    coach = team.head_coach
    bonded = team.roster[0]
    bonded.coach_bonds = {coach.id: "forged in fire"}
    entry = dr.fire_coach(team, reason="fired", date_str="2026-10-04")
    t.check("fired coach joins carousel",
            any(e["coach"] is coach for e in dr.COACH_CAROUSEL))
    t.check("chair is empty", team.head_coach is None)
    t.check("bonds remembered", bonded.name in entry["bonds"])
    t.check("hot seat high after firing", entry["hot_seat"] >= 60)
    cands = dr.coaching_candidates(team)
    t.check("candidates include carousel coach",
            any(c["coach"] is coach for c in cands))
    # Rehire: the bond walks back through the door.
    m0 = bonded.morale
    cand = next(c for c in cands if c["coach"] is coach)
    lines = dr.hire_coach(team, cand, date_str="2026-10-11")
    t.check("hire fills the chair", team.head_coach is coach)
    t.check("hire lifts the bonded player", bonded.morale > m0)
    t.check("coach leaves carousel",
            not any(e["coach"] is coach for e in dr.COACH_CAROUSEL))
    t.check("hire logged", bool(lines))


def test_ai_tick(t):
    random.seed(7)
    dr.COACH_CAROUSEL.clear()
    team = make_team(coach=None)
    team.is_user_team = False
    old = make_coach("Fired Guy", {"discipline": 90, "motivating": 60,
                                   "man_management": 40})
    dr.remember_coach(old, team=None, reason="fired", date_str="2026-09-01")
    league = make_league(team, losing_streak=4)
    out = dr.ai_room_politics_tick(team, date_str="2026-10-04", league=league)
    t.check("AI tick runs practice", bool(out["practice"]))
    t.check("AI fills empty chair", team.head_coach is not None)


def test_user_tick(t):
    random.seed(7)
    team = make_team(coach=players_coach())
    team.is_user_team = True
    dr.ensure_dressing_room_fields(team)["practice_plan"] = {
        "focus": "recovery", "intensity": "light", "bag_skate": False}
    league = make_league(team)
    out = dr.user_room_politics_tick(team, date_str="2026-10-04",
                                     league=league)
    t.check("user tick executes stored plan",
            out["practice"].get("focus") == "recovery")
    t.check("no forced crisis flag", out["crisis"] is None)


def test_practice_idempotent(t):
    random.seed(7)
    team = make_team(coach=players_coach())
    team.is_user_team = True
    dr.ensure_dressing_room_fields(team)["practice_plan"] = {
        "focus": "conditioning", "intensity": "moderate", "bag_skate": False}
    league = make_league(team)
    # "Set & Run This Week" stamps the week (explicit runs always apply).
    rec = dr.run_weekly_practice(team, focus="conditioning",
                                 intensity="moderate", date_str="2026-10-04")
    t.check("explicit run applies", bool(rec))
    n_receipts = len(
        dr.ensure_dressing_room_fields(team)["practice_receipts"])
    # Sunday tick the same week must NOT double-apply.
    out = dr.user_room_politics_tick(team, date_str="2026-10-04",
                                     league=league)
    t.check("Sunday tick skips already-run week", out["practice"] == {})
    t.check("no second receipt",
            len(dr.ensure_dressing_room_fields(team)["practice_receipts"])
            == n_receipts)
    # Next week runs normally again.
    out2 = dr.user_room_politics_tick(team, date_str="2026-10-11",
                                      league=league)
    t.check("next week runs", bool(out2["practice"]))
    # AI tick obeys the same idempotency.
    ai = make_team(coach=demanding_coach())
    ai.is_user_team = False
    dr.run_weekly_practice(ai, date_str="2026-10-04")
    out3 = dr.ai_room_politics_tick(ai, date_str="2026-10-04", league=league)
    t.check("AI tick skips already-run week", out3["practice"] == {})


def test_fire_hire_update_staff(t):
    random.seed(7)
    dr.COACH_CAROUSEL.clear()
    coach = demanding_coach()
    team = make_team(coach=coach)
    t.check("coach starts on staff",
            any(getattr(s, "id", None) == coach.id for s in team.staff))
    dr.fire_coach(team, reason="fired", date_str="2026-10-04")
    t.check("fire removes coach from team.staff",
            not any(getattr(s, "id", None) == coach.id for s in team.staff))
    t.check("head-coach lookup empty after fire",
            dr._room_head_coach(team) is None)
    # Hire an outsider from the carousel.
    cands = dr.coaching_candidates(team)
    cand = next(c for c in cands if c["coach"] is coach)
    dr.hire_coach(team, cand, date_str="2026-10-11")
    t.check("hire adds coach to team.staff",
            any(getattr(s, "id", None) == coach.id for s in team.staff))
    t.check("hire sets Head Coach role",
            dr._is_head_coach_role(
                next(s for s in team.staff
                     if getattr(s, "id", None) == coach.id)))
    t.check("head-coach lookup finds hire",
            dr._room_head_coach(team) is coach)
    # Promote an in-house assistant: role updates, no duplicate entry.
    asst = SimpleNamespace(id="a9", name="In House",
                           attacking_coaching=90, defensive_coaching=80,
                           coaching_goalies=40, motivating=80)
    asst.role = SimpleNamespace(value="Assistant Coach")
    team2 = make_team(coach=coach)
    team2.staff = [coach, asst]
    dr.fire_coach(team2, reason="fired", date_str="2026-10-04")
    n_staff = len(team2.staff)
    dr.hire_coach(team2, {"coach": asst, "name": "In House",
                          "archetype": "fresh blood"},
                  date_str="2026-10-11")
    t.check("promotion adds no duplicate staff entry",
            len(team2.staff) == n_staff)
    t.check("promoted assistant has Head Coach role",
            dr._is_head_coach_role(asst))
    heads = [s for s in team2.staff if dr._is_head_coach_role(s)]
    nhl_heads = [s for s in heads
                 if getattr(s, "assignment", "nhl") != "ahl"]
    t.check("exactly one NHL head coach on staff", len(nhl_heads) == 1)


def test_is_user_team(t):
    random.seed(7)
    gm = SimpleNamespace(user_team=None)
    a = make_team()
    a.is_user_team = True
    t.check("flag True -> user team", dr.is_user_team(a, gm) is True)
    b = make_team()
    b.is_user_team = False
    gm.user_team = b  # old save: flag never stamped, gm knows the club
    t.check("gm identity backstop", dr.is_user_team(b, gm) is True)
    c = make_team()
    c.team_name = "Other Club"
    t.check("other club is not user team",
            dr.is_user_team(c, gm) is False)
    t.check("no gm, no flag -> False",
            dr.is_user_team(c, None) is False)


def test_carousel_persistence(t):
    random.seed(7)
    import pickle
    import save_load_system as sls
    dr.COACH_CAROUSEL.clear()
    coach = demanding_coach()
    team = make_team(coach=coach)
    dr.fire_coach(team, reason="fired", date_str="2026-10-04")
    stub = SimpleNamespace()  # the two methods don't touch self
    payload = sls.GameSaveManager._serialize_coach_carousel(stub)
    t.check("serialize captures carousel", len(payload) == 1)
    blob = pickle.dumps(payload)  # what the save file does
    dr.COACH_CAROUSEL.clear()
    sls.GameSaveManager._restore_coach_carousel(stub, pickle.loads(blob))
    t.check("carousel restored after save/load", len(dr.COACH_CAROUSEL) == 1)
    e = dr.COACH_CAROUSEL[0]
    t.check("coach object survives", e["coach"].name == coach.name)
    t.check("hot seat survives", e["hot_seat"] >= 60)
    t.check("style survives", e["style"] == "drill_sergeant")
    dr.COACH_CAROUSEL.clear()


def main():
    t = T()
    test_practice_basics(t)
    test_coach_style_effectiveness(t)
    test_assistant_session_match(t)
    test_bag_skate_costs(t)
    test_practice_edge_consumed(t)
    test_receipt_goal_resolution(t)
    test_crisis_detection(t)
    test_crisis_resolutions(t)
    test_auto_resolve(t)
    test_carousel(t)
    test_ai_tick(t)
    test_user_tick(t)
    test_practice_idempotent(t)
    test_fire_hire_update_staff(t)
    test_is_user_team(t)
    test_carousel_persistence(t)
    t.report("Room politics")


if __name__ == "__main__":
    main()
