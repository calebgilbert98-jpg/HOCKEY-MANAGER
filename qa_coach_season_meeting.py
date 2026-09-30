"""QA: pre-season coach expectations meeting -- MODEL + WIRING + AI half.

Covers the shared contract (mandate model, arm/pending API, normalizer),
coach assessment shading, store_mandate (validation, trust scale,
downstream gates), AI resolution (no UI, never skipped), trigger hooks,
the advance blocker, carousel/rookie-stance wiring, and save/load
round-trip. Run: python3 qa_coach_season_meeting.py
"""
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import coach_season_meeting as csm
from game_classes import Team, Staff, StaffRole

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


def make_player(ovr=65, age=26):
    return SimpleNamespace(id=f"p{ovr}{age}", overall_rating=lambda: ovr,
                           age=age, usage_featured=False)


def make_coach(**kw):
    c = Staff(first_name="Test", last_name="Coach", role=StaffRole.HEAD_COACH)
    c.gm_trust = 70
    c.morale = 70
    c.ambition = "climb"
    c.control_need = 50
    c.first_nhl_chair = False
    c.working_with_youngsters = 50
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def make_team(name, coach=None, ovr=65, n=18, board="playoffs"):
    t = Team(team_name=name, city=name, division="A", conference="E")
    t.roster = [make_player(ovr) for _ in range(n)]
    t.board_expectation = board
    t.staff = []
    if coach is not None:
        t.staff.append(coach)
    return t


print("== contract: keys + normalizer ==")
check("SEASON_EXPECTATIONS", csm.SEASON_EXPECTATIONS == ["win_cup", "contend", "playoffs", "rebuild"])
check("normalize cup->win_cup", csm.normalize_expectation("cup") == "win_cup")
check("normalize contender->contend", csm.normalize_expectation("contender") == "contend")
check("normalize playoffs identity", csm.normalize_expectation("playoffs") == "playoffs")
check("normalize competitive->playoffs", csm.normalize_expectation("competitive") == "playoffs")
check("normalize rebuild identity", csm.normalize_expectation("rebuild") == "rebuild")
check("normalize ai keys identity", csm.normalize_expectation("win_cup") == "win_cup"
      and csm.normalize_expectation("contend") == "contend")
check("normalize junk->None", csm.normalize_expectation("bogus") is None
      and csm.normalize_expectation(None) is None
      and csm.normalize_expectation("bubble_team") is None)

print("== arm / pending / get_head_coach ==")
t = make_team("User", make_coach())
check("not pending initially", not csm.is_meeting_pending(t))
check("arm returns True", csm.arm_season_meeting(t, reason="new_save", season_year=2026) is True)
check("pending after arm", csm.is_meeting_pending(t))
check("context stored", (t.season_meeting_context or {}).get("reason") == "new_save")
check("arm idempotent (still pending)", csm.arm_season_meeting(t, reason="training_camp", season_year=2026) is True
      and csm.is_meeting_pending(t))
check("get_head_coach via get_staff_by_role", csm.get_head_coach(t) is t.staff[0])
t2 = make_team("NoCoach")
check("get_head_coach None when vacant", csm.get_head_coach(t2) is None)
check("arm with no coach still arms", csm.arm_season_meeting(t2, season_year=2026) is True)

print("== coach_season_assessment shading ==")
strong = make_team("Strong", make_coach(), ovr=75)   # win_cup band (>=72)
mid = make_team("Mid", make_coach(), ovr=60)         # playoffs band
weak = make_team("Weak", make_coach(), ovr=45)       # rebuild band
check("strong base win_cup", csm.coach_season_assessment(strong, strong.staff[0]) == "win_cup")
cup_coach = make_coach(ambition="stanley_cup")
check("stanley_cup ambition +1 notch", csm.coach_season_assessment(mid, cup_coach) == "contend")
check("stanley_cup clamped at top", csm.coach_season_assessment(strong, cup_coach) == "win_cup")
dev_coach = make_coach(ambition="developer")
check("developer ambition -1 notch", csm.coach_season_assessment(mid, dev_coach) == "rebuild")
check("developer clamped at bottom", csm.coach_season_assessment(weak, dev_coach) == "rebuild")
sad_coach = make_coach(morale=30)
check("low morale -1 notch", csm.coach_season_assessment(mid, sad_coach) == "rebuild")
check("no coach -> strength read", csm.coach_season_assessment(mid, None) == "playoffs")

print("== store_mandate: validation, trust, downstream ==")
t = make_team("User", make_coach())
csm.arm_season_meeting(t, reason="new_save", season_year=2026)
m = csm.store_mandate(t, {
    "season": 2026, "expectation": "cup", "coach_assessment": "contender",
    "rookie_stance": "heavy", "tactical_approach": "chaos_pressure",
    "lines_owner": "gm", "tactics_owner": "gm", "deployer_notes": "run it",
})
check("mandate stored", isinstance(t.season_mandate, dict) and t.season_mandate["meeting_done"] is True)
check("expectation normalized cup->win_cup", m["expectation"] == "win_cup")
check("aligned derived False (win_cup vs contend)", m["aligned"] is False)
check("pending cleared", not csm.is_meeting_pending(t))
check("trust dented on disagreement", t.staff[0].gm_trust == 70 + csm.TRUST_MISALIGNED_DENT)
check("lines gate written", t.line_control == "gm")
import tactics as _tx
check("tactics gate written", _tx.get_tactics_control(t) == "gm")
check("identity preset applied", _tx.team_tactics(t)["forecheck"] == "forecheck_212_swarm")
check("mandate keys complete",
      all(k in m for k in ("season", "expectation", "coach_assessment", "aligned",
                           "rookie_stance", "tactical_approach", "lines_owner",
                           "tactics_owner", "deployer_notes", "meeting_done")))

t = make_team("User2", make_coach())
csm.arm_season_meeting(t, season_year=2026)
m2 = csm.store_mandate(t, {"season": 2026, "expectation": "playoffs",
                           "coach_assessment": "playoffs",
                           "rookie_stance": "bogus", "tactical_approach": "bogus",
                           "lines_owner": "gm", "tactics_owner": "coach"})
check("aligned True bumps trust", t.staff[0].gm_trust == 70 + csm.TRUST_ALIGNED_BUMP)
check("bad rookie_stance -> none", m2["rookie_stance"] == "none")
check("bad preset -> None", m2["tactical_approach"] is None)
check("coach keeps lines default path", t.line_control == "gm" and _tx.get_tactics_control(t) == "coach")

print("== resolve_ai_season_meeting ==")
ai = make_team("AI", make_coach(ambition="developer", control_need=90), ovr=60)
m = csm.resolve_ai_season_meeting(ai, season_year=2026)
check("ai mandate stored + done", ai.season_mandate is not None and ai.season_mandate["meeting_done"])
check("ai never left pending", not csm.is_meeting_pending(ai))
check("ai mandate keys complete",
      all(k in m for k in ("season", "expectation", "coach_assessment", "aligned",
                           "rookie_stance", "tactical_approach", "lines_owner",
                           "tactics_owner", "deployer_notes", "meeting_done")))
check("ai developer coach -> heavy rookies", m["rookie_stance"] == "heavy")
check("ai high control_need keeps lines", m["lines_owner"] == "coach" and m["tactics_owner"] == "coach")
check("ai downstream gates match", ai.line_control == "coach"
      and _tx.get_tactics_control(ai) == "coach")
check("ai approach is a real preset", m["tactical_approach"] in _tx.IDENTITY_PRESETS)
check("ai notes mention club", "AI" in (m["deployer_notes"] or ""))

rookie = make_team("AIRook", make_coach(first_nhl_chair=True, control_need=95), ovr=45)
m = csm.resolve_ai_season_meeting(rookie, season_year=2026)
check("first_nhl_chair defers to GM", m["lines_owner"] == "gm" and m["tactics_owner"] == "gm")
check("weak roster reads rebuild", m["expectation"] == "rebuild")

collab = make_team("AICollab", make_coach(control_need=25), ovr=66)
m = csm.resolve_ai_season_meeting(collab, season_year=2026)
check("low control_need cedes to GM", m["lines_owner"] == "gm")

cup_ai = make_team("AICup", make_coach(ambition="stanley_cup"), ovr=75)
m = csm.resolve_ai_season_meeting(cup_ai, season_year=2026)
check("cup ambition lifts strong roster to win_cup", m["expectation"] == "win_cup")

# Board tension: board wants the Cup, roster says playoffs -> GM bends one notch.
tense = make_team("AITense", make_coach(), ovr=60, board="cup")
m = csm.resolve_ai_season_meeting(tense, season_year=2026)
check("far-apart board bends one notch (playoffs->contend)",
      m["expectation"] == "contend")

print("== trigger hooks ==")
# The daily-advance Sept-1 hook must exist in the universal advance path
# (simulate_day), so camp re-arms even without the automated flow.
import inspect as _inspect
import main as _main_mod
_src = _inspect.getsource(_main_mod)
check("sept-1 camp hook in daily advance",
      "on_training_camp" in _src
      and "self.current_date.month == 9 and self.current_date.day == 1" in _src)
gm = SimpleNamespace(league=SimpleNamespace(teams=[], season_year=2026),
                     user_team=None, pending_fantasy_draft=False,
                     startup_settings={})
ut = make_team("User", make_coach()); ut.is_user_team = True
ai1 = make_team("AI1", make_coach(ambition="developer"), ovr=60)
gm.league.teams = [ut, ai1]; gm.user_team = ut
csm.on_new_save(gm, ut)
check("new save arms user", csm.is_meeting_pending(ut))
check("new save resolves AI", ai1.season_mandate is not None and not csm.is_meeting_pending(ai1))
check("new save idempotent", csm.on_new_save(gm, ut) is None and csm.is_meeting_pending(ut))

gm2 = SimpleNamespace(league=SimpleNamespace(teams=[], season_year=2026),
                      user_team=None, pending_fantasy_draft=True, startup_settings={})
ut2 = make_team("User2", make_coach()); ut2.is_user_team = True
ai2 = make_team("AI2", make_coach(), ovr=60)
gm2.league.teams = [ut2, ai2]; gm2.user_team = ut2
csm.on_new_save(gm2, ut2)
check("fantasy pending defers arming", not csm.is_meeting_pending(ut2) and ai2.season_mandate is None)
csm.on_fantasy_draft_complete(gm2)
check("draft completion arms user", csm.is_meeting_pending(ut2))
check("draft completion resolves AI", ai2.season_mandate is not None)

csm.on_training_camp(gm)
check("camp re-arm keeps user pending", csm.is_meeting_pending(ut))
# Simulate a completed season then next camp with a rolled season_year.
csm.store_mandate(ut, {"season": 2026, "expectation": "playoffs",
                       "coach_assessment": "playoffs"})
gm.league.season_year = 2027
csm.on_training_camp(gm)
check("camp re-arms next season", csm.is_meeting_pending(ut))

ut3 = make_team("User3", make_coach()); ut3.is_user_team = True
csm.store_mandate(ut3, {"season": 2026, "expectation": "playoffs",
                        "coach_assessment": "playoffs"})
csm.on_coach_hired(ut3, gm)
check("new coach re-arms mid-season", csm.is_meeting_pending(ut3))
ai3 = make_team("AI3", make_coach(), ovr=60)
csm.resolve_ai_season_meeting(ai3, season_year=2026)
old_coach_id = ai3.season_mandate["coach_id"]
new_coach = make_coach(ambition="stanley_cup")
ai3.staff = [new_coach]
csm.on_coach_hired(ai3, gm)
check("AI new coach re-resolves", ai3.season_mandate["coach_id"] == new_coach.id
      and ai3.season_mandate["coach_id"] != old_coach_id)

print("== advance blocker ==")
app = SimpleNamespace(game_manager=gm)
gm.user_team = ut  # pending from the camp re-arm above
b = csm.season_meeting_blocker(app)
check("blocker dict when pending",
      b is not None and b["id"] == "season_meeting"
      and b["action"][0] == "Open Season Meeting" and callable(b["action"][1]))
check("blocker detail names coach", "Test Coach" in b["detail"])
csm.store_mandate(ut, {"season": 2027, "expectation": "playoffs",
                       "coach_assessment": "playoffs"})
check("no blocker when done", csm.season_meeting_blocker(app) is None)
app2 = SimpleNamespace(game_manager=SimpleNamespace(user_team=None))
check("no blocker without user team", csm.season_meeting_blocker(app2) is None)

# Sibling delegation: the blocker action calls the REAL sibling entry
# point coach_meeting_window.open_season_meeting(app) (monkeypatched to
# record -- the real one needs a live GUI).
import coach_meeting_window as _cmw
_calls = []
_real_open = _cmw.open_season_meeting
_cmw.open_season_meeting = lambda app: _calls.append(app)
try:
    ut4 = make_team("User4", make_coach()); ut4.is_user_team = True
    app4 = SimpleNamespace(game_manager=SimpleNamespace(user_team=ut4),
                           user_team=ut4)
    csm.arm_season_meeting(ut4, reason="training_camp", season_year=2027)
    b = csm.season_meeting_blocker(app4)
    b["action"][1]()
    check("action delegates to sibling surface", _calls == [app4])
finally:
    _cmw.open_season_meeting = _real_open

# Missing/broken sibling: the action must degrade to a warning, never raise.
_cmw.open_season_meeting = lambda app: (_ for _ in ()).throw(RuntimeError("boom"))
try:
    import popup_system
    seen = []
    popup_system.messagebox.showwarning = lambda t, m: seen.append((t, m))
    b = csm.season_meeting_blocker(app4)
    try:
        b["action"][1]()
        degraded_ok = True
    except Exception:
        degraded_ok = False
    check("broken sibling degrades gracefully", degraded_ok and seen
          and csm.is_meeting_pending(ut4))
finally:
    _cmw.open_season_meeting = _real_open

print("== downstream: carousel trust bar ==")
import dressing_room as dr
t = make_team("CarouselU", make_coach(), ovr=60)
exp, pace = dr._coach_board_expectation(t)
check("no mandate -> strength bar (playoffs 0.55)", exp == "playoffs" and pace == 0.55)
csm.store_mandate(t, {"season": 2026, "expectation": "win_cup",
                      "coach_assessment": "win_cup"})
exp2, pace2 = dr._coach_board_expectation(t)
check("mandate -> agreed bar (win_cup 0.65)", exp2 == "win_cup" and abs(pace2 - 0.65) < 1e-9)

print("== downstream: rookie stance via deployment_policy ==")
import deployment_policy as dp
t = make_team("Rook", make_coach(), ovr=60)
t.dynamics_log = []
t.season_mandate = {"season": 2026, "expectation": "playoffs",
                    "coach_assessment": "playoffs", "aligned": True,
                    "rookie_stance": "heavy", "tactical_approach": None,
                    "lines_owner": "coach", "tactics_owner": "coach",
                    "deployer_notes": "", "meeting_done": True}
check("heavy stance -> play_the_kids key",
      "play_the_kids" in dp._honored_advice(t)["keys"])
t.season_mandate["rookie_stance"] = "sheltered"
check("sheltered stance -> shorten_bench key",
      "shorten_bench" in dp._honored_advice(t)["keys"])
t.season_mandate["rookie_stance"] = "earned"
check("earned stance -> no nudge",
      "play_the_kids" not in dp._honored_advice(t)["keys"]
      and "shorten_bench" not in dp._honored_advice(t)["keys"])
t.season_mandate = None
check("no mandate -> no nudge", dp._honored_advice(t)["keys"] == set())

print("== save/load round-trip ==")
from save_load_system import GameSaveManager
# Note: empty roster here -- the QA's lambda-based fake players are not
# what the real serializer sees (real Player objects save fine today).
t = make_team("SaveT", make_coach(), ovr=60)
t.roster = []
csm.arm_season_meeting(t, reason="training_camp", season_year=2026)
csm.store_mandate(t, {"season": 2026, "expectation": "contend",
                      "coach_assessment": "playoffs", "rookie_stance": "earned",
                      "tactical_approach": "hybrid_transition",
                      "lines_owner": "coach", "tactics_owner": "coach",
                      "deployer_notes": "notes"})
t.season_meeting_pending = True  # still pending: the interesting case
# Re-arm context for the pending state (store_mandate clears it by design).
csm.arm_season_meeting(t, reason="training_camp", season_year=2026)
mgr = GameSaveManager(SimpleNamespace())
data = mgr._serialize_team(t)
check("save carries mandate", data.get("season_mandate", {}).get("expectation") == "contend")
check("save carries pending", data.get("season_meeting_pending") is True)
check("save carries context", isinstance(data.get("season_meeting_context"), dict))
blob = json.loads(json.dumps(data))  # save/load safe: JSON round-trip
t2 = mgr._restore_team(blob)
check("load restores mandate", (t2.season_mandate or {}).get("expectation") == "contend"
      and (t2.season_mandate or {}).get("tactical_approach") == "hybrid_transition")
check("load restores pending", t2.season_meeting_pending is True)
check("load restores context", (t2.season_meeting_context or {}).get("reason") == "training_camp")
# Old save: keys absent.
t3 = mgr._restore_team({"team_name": "OldT", "city": "Old", "division": "A", "conference": "E"})
check("old save -> no mandate, not pending",
      t3.season_mandate is None and t3.season_meeting_pending is False)

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:", failed)
    sys.exit(1)
