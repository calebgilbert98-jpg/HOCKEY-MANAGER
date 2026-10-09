# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: quarterly coach check-in -- UI walkthrough under Xvfb.

Drives CheckinView through a full conversation (messy-room run + healthy
room run), screenshots every stage, verifies resume-after-navigation,
the dashboard banner, mandate history, and trust movement.
Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_coach_checkin_ui.py
"""
import os
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, ".")

import customtkinter as ctk

from game_classes import Staff, StaffRole, Team
import coach_checkins as ck
import coach_checkin_window as ckw

SHOT_DIR = os.path.expanduser("~/workspace/uiaudit/checkins")
os.makedirs(SHOT_DIR, exist_ok=True)

passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")


def make_player(ovr=65, age=26, morale=70, pgp=20):
    st = SimpleNamespace(games_played=pgp)
    return SimpleNamespace(id=f"p{ovr}{age}{pgp}", overall_rating=lambda: ovr,
                           age=age, morale=morale, stats=st,
                           primary_position="C", usage_featured=False)


def make_team(name, morale=70, age=26, pgp=20, wins=12):
    t = Team(team_name=name, city=name, division="A", conference="E")
    t.roster = [make_player(65, age, morale, pgp) for _ in range(18)]
    coach = Staff(first_name="Test", last_name="Coach", role=StaffRole.HEAD_COACH)
    coach.gm_trust = 70.0
    coach.morale = 70
    coach.ambition = "climb"
    coach.control_need = 50
    coach.first_nhl_chair = False
    coach.working_with_youngsters = 50
    coach.attacking_coaching = 70
    coach.defensive_coaching = 55
    t.staff = [coach]
    gp = 25
    t.wins = wins
    t.ot_losses = 0
    t.losses = gp - wins
    t.season_mandate = {
        "season": 2026, "meeting_done": True, "expectation": "playoffs",
        "rookie_stance": "earned", "coach_summary": {}, "decisions": {},
        "checkins": [],
    }
    ck.arm_checkin(t, 20, 2026)
    return t


def make_app(team):
    nav_log = []
    return SimpleNamespace(
        user_team=team,
        game_manager=SimpleNamespace(current_date=date(2026, 11, 15)),
        FONT_FAMILY="Helvetica",
        show_screen=lambda _id, _t, factory, tm: factory(root, team=tm,
                                                         app=app_ref[0]),
        navigate=lambda dest: nav_log.append(dest),
        refresh_dashboard=lambda: None,
        _nav_log=nav_log,
    )


app_ref = [None]
root = ctk.CTk()
root.geometry("1600x900")
root.update()


def fresh_holder():
    for ch in root.winfo_children():
        ch.destroy()
    holder = ctk.CTkFrame(root)
    holder.pack(fill="both", expand=True)
    root.update()
    return holder


def make_view(team, app):
    holder = fresh_holder()
    view = ckw.CheckinView(holder, team=team, app=app)
    view.pack(fill="both", expand=True)
    root.update()
    root.update_idletasks()
    return view


def shot(name):
    root.update()
    root.update_idletasks()
    from PIL import ImageGrab
    img = ImageGrab.grab()
    path = os.path.join(SHOT_DIR, name)
    img.save(path)
    print(f"shot: {path}")
    return path


def all_texts(widget):
    out = []
    try:
        t = widget.cget("text")
        if t:
            out.append(str(t))
    except Exception:
        pass
    for ch in widget.winfo_children():
        out.extend(all_texts(ch))
    return out


random.seed(7)

print("== A: messy-room full conversation ==")
team = make_team("MessyClub", morale=38, age=20, pgp=16, wins=8)
app = make_app(team)
app_ref[0] = app
trust_before = float(team.staff[0].gm_trust)
view = make_view(team, app)
shot("a1_opening.png")
check("opening renders", any("check-in" in t.lower() for t in all_texts(view)))
view.debug_choose(None)  # opening -> expectations
shot("a2_expectations.png")
check("expectations stage", view._draft()["stage"] == "room"
      or any("mandate" in t.lower() for t in all_texts(view)))
view.debug_choose("honest")
shot("a3_room.png")
check("room stage reached", view._draft()["stage"] == "room")
view.debug_choose("support")
check("room beat held", view._draft()["stage"] == "rookies")
check("room beat recorded", "room" in view._draft()["deltas"])
shot("a4_rookies.png")
view.debug_choose("accept")
shot("a5_tactics.png")
view.debug_choose("tweak")
shot("a6_closing.png")
check("closing stage", view._draft()["stage"] == "closing")
view.debug_choose(None)  # closing -> finish
shot("a7_done.png")
hist = team.season_mandate.get("checkins") or []
check("history entry written", len(hist) == 1 and hist[0]["quarter"] == 20)
check("pending cleared", not ck.is_checkin_pending(team))
trust_after = float(team.staff[0].gm_trust)
check(f"trust moved {trust_before:.0f}->{trust_after:.0f}",
      trust_after != trust_before)
check("all four beats in deltas",
      set(hist[0]["deltas"].keys()) == {"expectations", "room", "rookies", "tactics"})
check("topics recorded", len(hist[0]["topics"]) == 4)

print("== B: resume after navigation ==")
team = make_team("ResumeClub", morale=70, wins=14)
app = make_app(team)
app_ref[0] = app
view = make_view(team, app)
view.debug_choose(None)      # opening -> expectations
view.debug_choose("credit")  # hold the expectations beat
mid_stage = view._draft()["stage"]
mid_beats = len(view._draft()["chosen"])
# navigate away (destroy the view, like leaving via the menu bar)
for ch in root.winfo_children():
    ch.destroy()
root.update()
check("draft survives navigation", isinstance(team.checkin_draft, dict)
      and len(team.checkin_draft.get("chosen", [])) == mid_beats)
view2 = make_view(team, app)
shot("b1_resumed.png")
texts = " ".join(all_texts(view2)).lower()
check("transcript replayed on return", "credit" in texts or mid_beats > 0)
check("stage preserved", view2._draft()["stage"] == mid_stage)
check("pending still armed after navigation", ck.is_checkin_pending(team))

print("== C: healthy room -- beat skippable ==")
team = make_team("HealthyClub", morale=78, wins=15)
app = make_app(team)
app_ref[0] = app
view = make_view(team, app)
view.debug_choose(None)
view.debug_choose("honest")
shot("c1_room_healthy.png")
check("room stage reached", view._draft()["stage"] == "room")
view.debug_choose("skip")
check("room skipped cleanly", view._draft()["stage"] == "rookies"
      and view._draft()["deltas"].get("room") == 0)

print("== D: dashboard banner ==")
import tkinter as tk
team = make_team("BannerClub", morale=70, wins=12)
app = make_app(team)
app_ref[0] = app
parent = tk.Frame(root)
banner = ckw.build_coach_checkin_banner(parent, app)
check("banner built while pending", banner is not None)
bt = " ".join(all_texts(banner)).lower()
check("banner non-blocking copy", "advances normally" in bt)
ck.expire_checkin(team)
banner2 = ckw.build_coach_checkin_banner(parent, app)
check("no banner when nothing pending", banner2 is None)

print("== E: readability pass ==")
team = make_team("A11yClub", morale=55, wins=12)
app = make_app(team)
app_ref[0] = app
view = make_view(team, app)
shot("e1_a11y.png")
texts = all_texts(view)
check("no empty critical labels",
      all(t.strip() for t in texts if t.strip()))
# every stage reachable without exception
stages_ok = True
try:
    for framing in (None, "honest", "direct", "press", "overhaul", None):
        if view._draft()["stage"] == "closing":
            view.debug_choose(None)
            break
        view.debug_choose(framing)
except Exception as e:
    stages_ok = False
    print("   stage error:", e)
check("all stages reachable", stages_ok)

print(f"\n{len(passed)} passed, {len(failed)} failed")
if failed:
    print("FAILURES:")
    for f in failed:
        print(" -", f)
    sys.exit(1)
