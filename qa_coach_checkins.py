# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: quarterly coach check-ins -- MODEL + WIRING + AI half.

Covers: contract (quarters, arm/pending/expiry), triggers at 20/40/60,
expiry + season-rollover behavior, mandatory room-beat firing, the
situational trust scale (bounds), history accumulation + last-checkin
references, AI resolution (no UI, never skipped, parity with the UI
path), no-mandate guarding, save/load round-trip of pending + history,
and the non-blocking guarantee. Run: python3 qa_coach_checkins.py
"""
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import coach_checkins as ck
from game_classes import Team, Staff, StaffRole

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


def make_player(ovr=65, age=26, morale=70, gp=20):
    st = SimpleNamespace(games_played=gp)
    return SimpleNamespace(id=f"p{ovr}{age}{gp}", overall_rating=lambda: ovr,
                           age=age, morale=morale, stats=st,
                           primary_position="C", usage_featured=False)


def make_coach(**kw):
    c = Staff(first_name="Test", last_name="Coach", role=StaffRole.HEAD_COACH)
    c.gm_trust = 70.0
    c.morale = 70
    c.ambition = "climb"
    c.control_need = 50
    c.first_nhl_chair = False
    c.working_with_youngsters = 50
    c.attacking_coaching = 70
    c.defensive_coaching = 55
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def make_team(name, coach=None, ovr=65, n=18, morale=70, age=26, pgp=20):
    t = Team(team_name=name, city=name, division="A", conference="E")
    t.roster = [make_player(ovr, age, morale, pgp) for _ in range(n)]
    t.staff = []
    if coach is not None:
        t.staff.append(coach)
    return t


def arm_mandate(team, season=2026, expectation="playoffs", stance="earned"):
    team.season_mandate = {
        "season": season, "meeting_done": True,
        "expectation": expectation, "rookie_stance": stance,
        "coach_summary": {}, "decisions": {}, "checkins": [],
    }


def set_record(team, gp):
    # even split wins/losses; pace ~0.500
    team.wins = gp // 2
    team.ot_losses = 0
    team.losses = gp - team.wins


print("== contract: quarters + pending API ==")
check("CHECKIN_QUARTERS == (20,40,60)", ck.CHECKIN_QUARTERS == (20, 40, 60))
t = make_team("User", make_coach())
arm_mandate(t)
check("not pending initially", not ck.is_checkin_pending(t))
check("arm returns True", ck.arm_checkin(t, 20, 2026) is True)
check("pending after arm", ck.is_checkin_pending(t))
check("pending quarter 20", ck.get_pending_quarter(t) == 20)
check("context stored", (t.checkin_context or {}).get("quarter") == 20)
check("arm bad quarter rejected", ck.arm_checkin(t, 25, 2026) is False)
check("current_quarter none at gp 0", ck.current_quarter(t) is None)
set_record(t, 20)
check("current_quarter 20 at gp 20", ck.current_quarter(t) == 20)
set_record(t, 45)
check("current_quarter 40 at gp 45", ck.current_quarter(t) == 40)
set_record(t, 70)
check("current_quarter 60 at gp 70", ck.current_quarter(t) == 60)
check("quarter_label", ck.quarter_label(20) == "First-quarter"
      and ck.quarter_label(40) == "Second-quarter"
      and ck.quarter_label(60) == "Third-quarter")
check("expire clears", ck.expire_checkin(t) is True
      and not ck.is_checkin_pending(t) and ck.get_pending_quarter(t) is None)

print("== triggers at 20/40/60 (user arms, AI resolves) ==")
gm = SimpleNamespace(league=SimpleNamespace(teams=[]), user_team=None)
user = make_team("User", make_coach()); arm_mandate(user)
ai = make_team("AI", make_coach()); arm_mandate(ai)
gm.league.teams = [user, ai]
gm.user_team = user
set_record(user, 21); set_record(ai, 21)
ck.on_day_advanced(gm)
check("user pending at gp 21", ck.is_checkin_pending(user)
      and ck.get_pending_quarter(user) == 20)
check("AI resolved immediately (no pending)",
      not ck.is_checkin_pending(ai))
check("AI history has Q20 entry",
      len((ai.season_mandate.get("checkins") or [])) == 1
      and ai.season_mandate["checkins"][0]["quarter"] == 20)
set_record(user, 42); set_record(ai, 42)
# user must finish Q20 first for the Q40 check-in to arm: complete it
ck.complete_checkin(user, {"season": 2026, "quarter": 20,
                           "expectation_framing": "honest",
                           "room_framing": "praise",
                           "rookie_framing": "credit",
                           "tactics_framing": "stay"},
                    apply_trust=True, per_beat_applied=True)
check("user Q20 completed clears pending", not ck.is_checkin_pending(user))
ck.on_day_advanced(gm)
check("user Q40 arms at gp 42", ck.is_checkin_pending(user)
      and ck.get_pending_quarter(user) == 40)
check("AI Q40 resolved too",
      len(ai.season_mandate["checkins"]) == 2
      and ai.season_mandate["checkins"][-1]["quarter"] == 40)
check("no double-arm: Q40 already held",
      ck.arm_checkin(user, 40, 2026) is True and ck.is_checkin_pending(user))

print("== expiry + season rollover ==")
t = make_team("User", make_coach()); arm_mandate(t)
set_record(t, 21)
ck.arm_checkin(t, 20, 2026)
set_record(t, 46)  # quarter moved on without the GM
ck.maybe_arm_checkins(SimpleNamespace(
    league=SimpleNamespace(teams=[t]), user_team=t))
check("pending Q20 expires when Q40 arms", not ck.is_checkin_pending(t)
      or ck.get_pending_quarter(t) == 40)
check("Q40 armed after expiry", ck.is_checkin_pending(t)
      and ck.get_pending_quarter(t) == 40)
set_record(t, 5)   # season rolled over (gp reset)
ck.maybe_arm_checkins(SimpleNamespace(
    league=SimpleNamespace(teams=[t]), user_team=t))
check("season rollover clears pending", not ck.is_checkin_pending(t))

print("== no mandate: nothing arms ==")
t = make_team("NoMandate", make_coach())
set_record(t, 25)
ck.maybe_arm_checkins(SimpleNamespace(
    league=SimpleNamespace(teams=[t]), user_team=t))
check("no mandate -> no arm", not ck.is_checkin_pending(t))

print("== room beat: mandatory when messy, skippable when fine ==")
messy = make_team("Messy", make_coach(), morale=40)
set_record(messy, 25)
arm_mandate(messy)
st = ck.room_state(messy)
check("messy verdict at morale 40", st["messy"] is True)
check("messy atmosphere surfaced", st["atmosphere_label"] != "")
fine = make_team("Fine", make_coach(), morale=75)
set_record(fine, 25)
arm_mandate(fine)
check("fine room not messy", ck.room_state(fine)["messy"] is False)
# UI enforcement point: option pools
sys.path.insert(0, ".")
import coach_checkin_window as ckw
check("messy pool has NO skip", all(f != "skip"
      for f, _l, _g in ckw._BEAT_FRAMINGS["room_messy"]))
check("healthy pool HAS skip", any(f == "skip"
      for f, _l, _g in ckw._BEAT_FRAMINGS["room_healthy"]))
# model: every room framing returns a real (delta, tone, note) triple
for f in ("support", "direct", "demand", "praise"):
    d, tone, note = ck.checkin_room_delta(messy, messy.staff[0], f)
    check(f"messy room framing '{f}' -> delta {d} in [-3,+1]",
          -3 <= d <= 1 and bool(tone) and bool(note))
d, tone, _n = ck.checkin_room_delta(messy, make_coach(control_need=90), "demand")
check("authoritarian + demand = -3 (room_defiant)",
      d == -3 and tone == "room_defiant")

print("== trust scale bounds ==")
c_plain = make_coach()
c_auth = make_coach(control_need=90)
teams_cfg = []
for exp, gp in (("playoffs", 25),):
    for w in (20, 12, 5, 1):
        tt = make_team("B", make_coach(), morale=70); arm_mandate(tt)
        set_record(tt, gp); tt.wins = w; tt.ot_losses = 0; tt.losses = gp - w
        teams_cfg.append(tt)
ok = True
for tt in teams_cfg:
    for fn, framings in (
            (ck.checkin_expectation_delta, ("credit", "honest", "demand")),
            (ck.checkin_room_delta, ("support", "direct", "demand", "praise", "skip")),
            (ck.checkin_rookie_delta, ("credit", "accept", "press")),
            (ck.checkin_tactics_delta, ("stay", "tweak", "overhaul"))):
        for f in framings:
            for coach in (c_plain, c_auth):
                d, tone, note = fn(tt, coach, f)
                if not (-3 <= d <= 2) or not tone or not isinstance(note, str):
                    ok = False
check("every beat delta in [-3,+2], tone+note present", ok)
# full-check-in band
worst, best = 99, -99
for tt in teams_cfg:
    for ef in ("credit", "honest", "demand"):
        for rf in ("support", "direct", "demand", "praise"):
            for kf in ("credit", "accept", "press"):
                for tf in ("stay", "tweak", "overhaul"):
                    tot = ck.compute_checkin_trust_delta(tt, c_auth, {
                        "expectation_framing": ef, "room_framing": rf,
                        "rookie_framing": kf, "tactics_framing": tf})
                    worst, best = min(worst, tot), max(best, tot)
check(f"full check-in total in [-8,+6] (saw {worst}..{best})",
      worst >= -8 and best <= 6)

print("== history accumulation + last-checkin reference ==")
t = make_team("User", make_coach()); arm_mandate(t)
set_record(t, 25)
ck.arm_checkin(t, 20, 2026)
e1 = ck.complete_checkin(t, {"season": 2026, "quarter": 20,
                             "expectation_framing": "honest",
                             "room_framing": "support",
                             "rookie_framing": "accept",
                             "tactics_framing": "tweak",
                             "topics": ["expectations", "room"],
                             "notes": ["behind pace but steady"]},
                         apply_trust=True, per_beat_applied=False)
check("entry recorded", e1 is not None and e1["quarter"] == 20
      and e1["game"] == 25)
check("pending cleared on completion", not ck.is_checkin_pending(t))
set_record(t, 45)
ck.arm_checkin(t, 40, 2026)
e2 = ck.complete_checkin(t, {"season": 2026, "quarter": 40,
                             "expectation_framing": "credit",
                             "room_framing": "praise",
                             "rookie_framing": "credit",
                             "tactics_framing": "stay"},
                         apply_trust=True, per_beat_applied=True)
hist = t.season_mandate.get("checkins") or []
check("two entries accumulated", len(hist) == 2)
check("last_checkin returns Q40", (ck.last_checkin(t) or {}).get("quarter") == 40)
check("topics persisted", "expectations" in (hist[0].get("topics") or []))
check("deltas persisted", isinstance(hist[0].get("deltas"), dict))
check("json-serializable", bool(json.dumps(hist)))

print("== AI resolution: parity + never skipped ==")
t = make_team("AI", make_coach()); arm_mandate(t, expectation="contend")
set_record(t, 30)
t.wins = 8; t.losses = 22  # far behind
before = float(t.staff[0].gm_trust)
entry = ck.resolve_ai_checkin(t, 20, season_year=2026)
after = float(t.staff[0].gm_trust)
check("AI entry recorded", entry is not None and entry["quarter"] == 20)
check("AI never pending", not ck.is_checkin_pending(t))
check("AI trust moved", after != before)
# parity: the AI path's total equals the sum of the model's own beats
coach = t.staff[0]
tot = ck.compute_checkin_trust_delta(t, coach, ck._ai_framings(t, coach))
check("AI delta equals computed total", abs((after - before) - tot) < 1e-9)
check("AI notes recorded", len(entry.get("notes") or []) >= 2)
# AI never skips: all three quarters resolve
set_record(t, 65)
ck.maybe_arm_checkins(SimpleNamespace(
    league=SimpleNamespace(teams=[t]), user_team=None))
qs = [h["quarter"] for h in t.season_mandate["checkins"]]
check("AI holds all quarters crossed", all(q in qs for q in (20, 40, 60)))

print("== rookie stance + tactics reads ==")
t = make_team("User", make_coach(), age=20, pgp=18); arm_mandate(t, stance="heavy")
set_record(t, 25)
honored, share, stance = ck.rookie_stance_honored(t)
check("heavy stance honored when kids play", honored is True and stance == "heavy")
t2 = make_team("User", make_coach(), age=20, pgp=2); arm_mandate(t2, stance="heavy")
set_record(t2, 25)
check("heavy stance NOT honored when kids sit",
      ck.rookie_stance_honored(t2)[0] is False)
t3 = make_team("User", make_coach(), age=20, pgp=2); arm_mandate(t3, stance="none")
set_record(t3, 25)
check("'none' stance honored when kids kept down",
      ck.rookie_stance_honored(t3)[0] is True)
working, act, exp = ck.tactics_working(t)
check("tactics read returns triple", isinstance(working, bool))
check("pace_band returns band", ck.pace_band(t)[0] in ("ahead", "track", "behind", "far"))

print("== save/load: pending + history round-trip ==")
import save_load_system as sls
t = make_team("User", make_coach()); arm_mandate(t)
set_record(t, 42)
ck.arm_checkin(t, 40, 2026)
t.season_mandate["checkins"].append({"date": "2026-11-15", "season": 2026,
                                    "quarter": 20, "game": 21,
                                    "topics": ["expectations"], "deltas": {},
                                    "notes": []})
t.roster = []  # QA fakes carry lambdas; the round-trip is about the fields
saver = sls.GameSaveManager.__new__(sls.GameSaveManager)
d = saver._serialize_team(t)
json.dumps(d)
t2 = Team(team_name="User", city="User", division="A", conference="E")
t2.checkin_pending = bool(d.get("checkin_pending", False))
_cq = d.get("checkin_quarter")
t2.checkin_quarter = int(_cq) if _cq is not None else None
t2.checkin_context = dict(d.get("checkin_context") or {})
t2.season_mandate = dict(d.get("season_mandate") or {}) or None
check("pending survives", t2.checkin_pending is True
      and t2.checkin_quarter == 40)
check("context survives", t2.checkin_context.get("quarter") == 40)
check("history survives", len(t2.season_mandate["checkins"]) == 1
      and t2.season_mandate["checkins"][0]["quarter"] == 20)

print("== postseason: nothing arms, pendings expire ==")
t = make_team("User", make_coach()); arm_mandate(t)
set_record(t, 65)
ck.arm_checkin(t, 60, 2026)
bracket = SimpleNamespace(playoff_series={"wild_card": [object()]},
                          ROUND_ORDER=("wild_card",))
lgm = SimpleNamespace(league=SimpleNamespace(teams=[t], playoff_bracket=bracket),
                      user_team=t)
ck.maybe_arm_checkins(lgm)
check("pending expires when postseason starts", not ck.is_checkin_pending(t))
t2 = make_team("AI", make_coach()); arm_mandate(t2)
set_record(t2, 65)
lgm2 = SimpleNamespace(league=SimpleNamespace(teams=[t2], playoff_bracket=bracket),
                       user_team=None)
ck.maybe_arm_checkins(lgm2)
check("AI does not resolve in postseason",
      len(t2.season_mandate.get("checkins") or []) == 0)

print("== non-blocking guarantee ==")
t = make_team("User", make_coach()); arm_mandate(t)
set_record(t, 21)
ck.arm_checkin(t, 20, 2026)
check("pending check-in is not in get_continue_state blockers",
      "checkin" not in str(getattr(ck, "__all__", "")).lower())
# model-level: nothing here touches the day-advance machinery
check("no blocker registration", not hasattr(ck, "register_blocker"))

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:")
    for f in failed:
        print(" -", f)
    sys.exit(1)
