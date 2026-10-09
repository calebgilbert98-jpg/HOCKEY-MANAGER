# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA walkthrough of the pre-season coach expectations meeting UI.

Run: xvfb-run -a -s "-screen 0 1680x1050x24" python3 qa_coach_meeting.py
Drives the FULL meeting (all beats incl. the deployer beat) across three
coach archetypes, checks disagreement/trust paths, leave-and-return, the
pending banner, degraded (coach-less) mode, and a11y probes. Screenshots go
to ~/workspace/coach-meeting-qa/ for Chris's pre-push review.
"""
import os
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from game_classes import Staff, StaffRole, Team
import coach_meeting_window as cmw

PASS, FAIL = [], []
SHOT_DIR = os.path.expanduser("~/workspace/coach-meeting-qa")
os.makedirs(SHOT_DIR, exist_ok=True)


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}"
          + (f" -- {extra}" if extra and not cond else ""))


class FakePlayer:
    def __init__(self, ovr):
        self._ovr = ovr

    def overall_rating(self):
        return self._ovr


def make_coach(**kw):
    coach = Staff("Test", "Coach", StaffRole.HEAD_COACH)
    for k, v in kw.items():
        setattr(coach, k, v)
    return coach


def make_team(strength, coach, board_exp="contend"):
    team = Team("Test Team", "Testville", "Atlantic", "Eastern")
    team.roster = [FakePlayer(strength) for _ in range(20)]
    team.staff = [coach] if coach is not None else []
    team.season_meeting_pending = True
    return team


def make_app(team, board_exp="contend"):
    return SimpleNamespace(
        user_team=team,
        career=SimpleNamespace(board=SimpleNamespace(expectation=board_exp)),
        game_manager=SimpleNamespace(current_date=date(2026, 9, 30)),
        FONT_FAMILY="Helvetica",
    )


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
    view = cmw.SeasonMeetingView(holder, team=team, app=app)
    view.pack(fill="both", expand=True)
    root.update()
    root.update_idletasks()
    return view


def shot(name, view):
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
    try:
        t = widget.cget("textvariable")
    except Exception:
        t = None
    if t is not None:
        try:
            out.append(str(t.get()))
        except Exception:
            pass
    for ch in widget.winfo_children():
        out.extend(all_texts(ch))
    return out


def all_widgets(widget):
    out = [widget]
    for ch in widget.winfo_children():
        out.extend(all_widgets(ch))
    return out


random.seed(11)

# ---------------------------------------------------------------- A: menu gating
t = make_team(78, make_coach())
opts = cmw.expectation_options(t, "contend")
check("A1 78-strength roster offers win_cup", "win_cup" in opts, opts)
check("A2 78-strength offers win_cup/contend/playoffs",
      opts == ["win_cup", "contend", "playoffs"], opts)

t50 = make_team(50, make_coach())
opts50 = cmw.expectation_options(t50, "contend")
check("A3 50-strength roster never offers win_cup", "win_cup" not in opts50,
      opts50)
check("A4 50-strength offers playoffs/rebuild",
      opts50 == ["playoffs", "rebuild"], opts50)

t64 = make_team(64, make_coach())
opts64 = cmw.expectation_options(t64, "rebuild")
check("A5 board rebuild unions in (64 roster + rebuild board)",
      opts64 == ["contend", "playoffs", "rebuild"], opts64)
check("A6 win_cup gated even when board is ambitious (64 roster)",
      "win_cup" not in opts64, opts64)

# ------------------------------------------------- B: full walkthrough (ambitious vet)
coach_b = make_coach(ambition="stanley_cup", control_need=80, morale=70,
                     working_with_youngsters=45, gm_trust=70,
                     attacking_coaching=80, defensive_coaching=45)
team_b = make_team(76, coach_b)
app_b = make_app(team_b)
view = make_view(team_b, app_b)
check("B1 opens at opening stage", view.draft["stage"] == "opening")
check("B2 coach opening line logged",
      len(view.draft["log"]) == 1 and view.draft["log"][0]["speaker"] == "coach")
shot("01_opening.png", view)

view.debug_choose("opening", "begin")
check("B3 opening -> expectations", view.draft["stage"] == "expectations")
assessed = view.draft["coach_assessment"]
check("B4 ambitious coach assesses win_cup for 76 roster",
      assessed == "win_cup", assessed)
shot("02_expectations.png", view)

view.debug_choose("expectations", "contend")  # below his read -> pushback
check("B5 expectations -> rookies", view.draft["stage"] == "rookies")
# Situational: ambition the roster can't cash back down -- an ambitious
# coach pushed one notch below his read: patient_pushback -2 (70->68).
check("B6 ambitious coach pushed back on lower mandate (trust 70->68)",
      coach_b.gm_trust == 68, coach_b.gm_trust)
check("B7 disagreement note recorded",
      any("push" in n or "uneasy" in n or "patient" in n or "lowered" in n
          for n in view.draft["notes"]),
      view.draft["notes"])

view.debug_choose("rookies", "heavy")  # win-now + low youngsters -> resist
check("B8 rookies -> tactics", view.draft["stage"] == "tactics")
# Heavy minutes on a prime roster chasing contention: mild friction -1.
check("B9 win-now coach resisted heavy minutes (68->67)",
      coach_b.gm_trust == 67, coach_b.gm_trust)

view.debug_choose("tactics", "stranglehold")  # attack-style coach -> misfit
check("B10 tactics -> lines", view.draft["stage"] == "lines")
check("B11 authoritarian bristled at style clash (67->65)",
      coach_b.gm_trust == 65, coach_b.gm_trust)

view.debug_choose("lines", "gm")
check("B12 lines -> tactics_own", view.draft["stage"] == "tactics_own")
# Taking the lineup scales with control_need: -(1+round(80/50)) = -3.
check("B13 authoritarian lost the lineup (65->62)",
      coach_b.gm_trust == 62, coach_b.gm_trust)

view.debug_choose("tactics_own", "gm")
check("B14 BOTH gm -> deployer beat mandatory",
      view.draft["stage"] == "deployer", view.draft["stage"])
shot("03_deployer.png", view)

view.debug_choose("deployer", "reassure")
check("B15 deployer -> closing", view.draft["stage"] == "closing")
# Live chain: 70 -2 -1 -2 -3 -3 +1 = 60; seal adds only the misaligned
# handshake (-2) since the beats already landed live -> 58.
check("B16 reassure moved trust (59->60)", coach_b.gm_trust == 60,
      coach_b.gm_trust)
check("B17 deployer note recorded", bool(view.draft.get("deployer_note")),
      view.draft.get("deployer_note"))
shot("04_closing.png", view)

mandate = cmw.build_mandate(team_b, view.draft, 2026)
check("B18 mandate shape matches contract",
      set(mandate) == {"season", "expectation", "coach_assessment", "aligned",
                       "rookie_stance", "tactical_approach", "lines_owner",
                       "tactics_owner", "deployer_choice", "deployer_notes",
                       "meeting_done"},
      sorted(mandate))
check("B19 mandate values",
      mandate["expectation"] == "contend"
      and mandate["rookie_stance"] == "heavy"
      and mandate["tactical_approach"] == "stranglehold"
      and mandate["lines_owner"] == "gm"
      and mandate["tactics_owner"] == "gm"
      and mandate["meeting_done"] is True, mandate)
check("B20 canonical aligned=False (contend != coach's win_cup)",
      mandate.get("aligned") is False, mandate.get("aligned"))

view._seal(mandate)
stored = getattr(team_b, "season_mandate", {}) or {}
check("B20b store_mandate extras written (real completion path)",
      stored.get("meeting_done") is True
      and "coach_name" in stored and "reason" in stored,
      [k for k in ("coach_name", "reason") if k in stored])
check("B20c downstream wiring: line_control follows mandate",
      getattr(team_b, "line_control", None) == "gm",
      getattr(team_b, "line_control", None))
check("B21 pending cleared on seal", team_b.season_meeting_pending is False)
check("B21b seal applied only the handshake (60->58, no double-count)",
      coach_b.gm_trust == 58, coach_b.gm_trust)
check("B22 mandate written to team",
      getattr(team_b, "season_mandate", {}).get("expectation") == "contend")
check("B23 draft dropped after seal",
      not hasattr(team_b, "season_meeting_draft"))
check("B24 view shows done state", view.draft["stage"] == "done")
shot("05_sealed.png", view)
# re-opening a sealed meeting shows the agreement, not a fresh meeting
view_re = make_view(team_b, app_b)
check("B24b re-open after seal shows done state",
      view_re.draft["stage"] == "done")

# no system-speak in coach voice
coach_lines = [e["text"] for e in view.draft["log"] if e["speaker"] == "coach"]
check("B25 coach never breaks into system-speak",
      not any("Trust " in t or "mandate" in t.lower() for t in coach_lines))

# ------------------------------------------------- C: authoritarian tank refusal
coach_c = make_coach(ambition="stanley_cup", control_need=95, morale=60,
                     working_with_youngsters=30, gm_trust=70)
team_c = make_team(76, coach_c)
view_c = make_view(team_c, make_app(team_c))
view_c.debug_choose("opening", "begin")
view_c.debug_choose("expectations", "rebuild")
# Tank demand on a contend roster from an ambitious authoritarian:
# outright refusal (-4), survivable.
check("C1 tank refusal costs -4 (70->66)", coach_c.gm_trust == 66,
      coach_c.gm_trust)
check("C2 refusal marks misaligned", view_c.draft.get("misaligned") is True)
m_c = cmw.build_mandate(team_c, view_c.draft, 2026)
check("C3 mandate aligned=False", m_c["aligned"] is False)

# ------------------------------------------------- D: developer embraces rebuild
coach_d = make_coach(ambition="developer", control_need=45, morale=70,
                     working_with_youngsters=85, gm_trust=70)
team_d = make_team(52, coach_d)
view_d = make_view(team_d, make_app(team_d, board_exp="rebuild"))
check("D1 developer assesses rebuild for 52 roster",
      view_d.draft["coach_assessment"] == "rebuild",
      view_d.draft["coach_assessment"])
view_d.debug_choose("opening", "begin")
view_d.debug_choose("expectations", "rebuild")
# Agreement off the roster's true rung is still agreement (+2).
check("D2 developer buys in (+2 -> 72)", coach_d.gm_trust == 72,
      coach_d.gm_trust)
view_d.debug_choose("rookies", "heavy")
# Heavy minutes with no age data: neutral-prime roster, developer +1.
check("D3 developer accepts heavy minutes (72->73)", coach_d.gm_trust == 73,
      coach_d.gm_trust)

# ------------------------------------------------- E: first-chair defers
coach_e = make_coach(ambition="climb", control_need=30, morale=65,
                     working_with_youngsters=55, gm_trust=70,
                     first_nhl_chair=True)
team_e = make_team(76, coach_e)
view_e = make_view(team_e, make_app(team_e))
view_e.debug_choose("opening", "begin")
view_e.debug_choose("expectations", "contend")  # below his win_cup read
# First-chair rookie defers to the GM's patience: +1, not misaligned.
check("E1 rookie chair defers (+1 -> 71)", coach_e.gm_trust == 71,
      coach_e.gm_trust)
check("E2 deferral not misaligned", not view_e.draft.get("misaligned"))

# ------------------------------------------------- F: leave and return
coach_f = make_coach(gm_trust=70)
team_f = make_team(70, coach_f)
view_f = make_view(team_f, make_app(team_f))
view_f.debug_choose("opening", "begin")
view_f.debug_choose("expectations", "contend")
trust_after_beat = coach_f.gm_trust  # whatever the situational beat gave
n_log = len(view_f.draft["log"])
view_f2 = make_view(team_f, make_app(team_f))  # "return"
check("F1 stage resumes at rookies", view_f2.draft["stage"] == "rookies")
check("F2 transcript replayed exactly",
      len(view_f2.draft["log"]) == n_log, (len(view_f2.draft["log"]), n_log))
check("F3 choices preserved",
      view_f2.draft["choices"].get("expectation") == "contend")
check("F4 trust not double-applied on return",
      coach_f.gm_trust == trust_after_beat, coach_f.gm_trust)
view_f2.debug_choose("rookies", "earned")
check("F5 meeting continues after return",
      view_f2.draft["stage"] == "tactics")

# ------------------------------------------------- G: degraded modes
team_g = make_team(70, None)  # coach-less
view_g = make_view(team_g, make_app(team_g))
texts_g = " ".join(all_texts(view_g)).lower()
check("G1 coach-less team gets clean message, no crash",
      "head coach" in texts_g, texts_g[:120])

# ------------------------------------------------- H: banner
banner = cmw.build_season_meeting_banner(fresh_holder(), make_app(team_f))
check("H1 banner returned while pending", banner is not None)
team_f.season_meeting_pending = False
banner2 = cmw.build_season_meeting_banner(fresh_holder(), make_app(team_f))
check("H2 no banner when not pending", banner2 is None)

# ------------------------------------------------- I: opener via show_screen
team_i = make_team(70, make_coach())
app_i = make_app(team_i)
captured = {}


def fake_show(screen_id, title, view_cls, *args, **kwargs):
    holder = fresh_holder()
    v = view_cls(holder, *args, app=app_i, **kwargs)
    v._close_screen = lambda: None
    captured["view"] = v
    captured["id"] = screen_id
    return v


app_i.show_screen = fake_show
opened = cmw.open_season_meeting(app_i)
check("I1 open_season_meeting routes via show_screen",
      captured.get("id") == "season_meeting" and opened is not None)

# ------------------------------------------------- J: a11y probes
team_j = make_team(70, make_coach())
view_j = make_view(team_j, make_app(team_j))
view_j.debug_choose("opening", "begin")
widgets = all_widgets(view_j)
ctk_texts = [w for w in widgets if isinstance(w, ctk.CTkTextbox)]
check("J1 single scrollable region (one transcript box)",
      len(ctk_texts) == 1, len(ctk_texts))
btns = [w for w in widgets if isinstance(w, ctk.CTkButton)]
check("J2 buttons found", len(btns) >= 1, len(btns))
check("J3 option buttons >= 36px tall",
      all(int(b.cget("height")) >= 36 for b in btns),
      [b.cget("height") for b in btns][:5])
check("J4 prompt label has wraplength",
      int(view_j.prompt_label.cget("wraplength")) > 0)
tfont = view_j.transcript.cget("font")
tsize = tfont[1] if isinstance(tfont, (tuple, list)) and len(tfont) > 1 else 13
check("J4 transcript font readable", tsize >= 12, tsize)
presets = cmw._identity_presets()
check("J5 presets offered have name+tagline",
      all(presets[k].get("name") and presets[k].get("tagline")
          for k in presets),
      list(presets))
print(f"INFO: IDENTITY_PRESETS ships {len(presets)} entries "
      f"({', '.join(presets)}); the 'curated ~6' is the full set.")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
print(f"shots in {SHOT_DIR}")
sys.exit(1 if FAIL else 0)
