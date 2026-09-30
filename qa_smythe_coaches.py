"""QA: Conn Smythe (real-life criteria) + coach season records + Jack Adams
+ reputation fine-tune (awards -> rep, Adams -> staff rep, playoff rounds,
team_perception track-record cushion).

Headless. Run: DISPLAY=:99 python3 qa_smythe_coaches.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from types import SimpleNamespace

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")

import game_classes as g
from game_classes import StaffRole, PlayerStats, PlayerPosition
import playoff_system as psys
import coach_records as cr
import reputation_system as rs
import accolades as acc

# ---------------------------------------------------------------- fold --
print("== playoff stat fold ==")
def mk_player(name, pos):
    p = SimpleNamespace(full_name=name, primary_position=pos,
                        is_goalie=(pos == PlayerPosition.GOALIE),
                        playoff_stats=PlayerStats(), career_accolades=[],
                        id=abs(hash(name)) % 10**6)
    return p

sk1 = mk_player("Skater One", PlayerPosition.CENTER)
gk1 = mk_player("Goalie One", PlayerPosition.GOALIE)
gk2 = mk_player("Goalie Two", PlayerPosition.GOALIE)
fake_sim = SimpleNamespace(
    game_stats={
        sk1.id: {"g": 2, "a": 1, "player": sk1},
        gk1.id: {"g": 0, "a": 0, "player": gk1, "saves": 30,
                 "shots_against": 32, "goals_against": 2, "shutouts": 0},
        gk2.id: {"g": 0, "a": 1, "player": gk2, "saves": 25,
                 "shots_against": 28, "goals_against": 3, "shutouts": 0},
    },
    _selected_goalie=lambda team: gk1 if team is t1 else gk2,
)
t1 = SimpleNamespace(team_name="Alpha", id=1)
t2 = SimpleNamespace(team_name="Beta", id=2)
br = psys.PlayoffBracket.__new__(psys.PlayoffBracket)
psys.PlayoffBracket._fold_playoff_stats(br, fake_sim, t1, t2, True)
check("skater gp/g/a folded",
      sk1.playoff_stats.games_played == 1
      and sk1.playoff_stats.goals == 2 and sk1.playoff_stats.assists == 1,
      vars(sk1.playoff_stats))
check("goalie saves folded", gk1.playoff_stats.saves == 30
      and gk1.playoff_stats.shots_against == 32)
check("winning goalie gets the W", gk1.playoff_stats.wins == 1)
check("losing goalie gets the L", gk2.playoff_stats.losses == 1)
check("losing goalie no win", gk2.playoff_stats.wins == 0)
# old-save player without the field is skipped, not crashed
old = SimpleNamespace(full_name="Old Timer")
try:
    psys.PlayoffBracket._fold_playoff_stats(
        br, SimpleNamespace(game_stats={9: {"g": 1, "player": old}},
                            _selected_goalie=lambda t: None), t1, t2, True)
    check("old-save player skipped safely", True)
except Exception as e:
    check("old-save player skipped safely", False, e)

# ------------------------------------------------------- smythe select --
print("== conn smythe selection ==")
def champ_team():
    star = mk_player("Star Winger", PlayerPosition.RIGHT_WING)
    star.playoff_stats.games_played = 20
    star.playoff_stats.goals = 12
    star.playoff_stats.assists = 13   # 25 pts
    mid = mk_player("Mid Center", PlayerPosition.CENTER)
    mid.playoff_stats.games_played = 20
    mid.playoff_stats.goals = 8
    mid.playoff_stats.assists = 12
    tendy = mk_player("Hot Goalie", PlayerPosition.GOALIE)
    tendy.playoff_stats.games_played = 20
    tendy.playoff_stats.wins = 14
    tendy.playoff_stats.saves = 580
    tendy.playoff_stats.shots_against = 617   # .940
    return SimpleNamespace(team_name="Champs", id=7,
                           roster=[star, mid, tendy]), star, tendy

br2 = psys.PlayoffBracket.__new__(psys.PlayoffBracket)
br2.league = SimpleNamespace(season_year=2026)
br2.stanley_cup_champion, star, tendy = champ_team()
w = br2._decide_conn_smythe()
check("all-time goalie run beats 25-pt skater", w is tendy,
      getattr(w, "full_name", None))
check("smythe banked on winner",
      any(e.get("award") == "conn_smythe" for e in tendy.career_accolades),
      tendy.career_accolades)
check("smythe season label", tendy.career_accolades[-1]["year"] == "2026-27",
      tendy.career_accolades)
check("smythe name stashed", br2.conn_smythe_name == "Hot Goalie",
      getattr(br2, "conn_smythe_name", None))

# same setup, mortal goalie (.920) -> skater wins
br3 = psys.PlayoffBracket.__new__(psys.PlayoffBracket)
br3.league = SimpleNamespace(season_year=2026)
team3, star3, tendy3 = champ_team()
tendy3.playoff_stats.saves = 568   # .9206
br3.stanley_cup_champion = team3
w3 = br3._decide_conn_smythe()
check("mortal goalie loses to scoring leader", w3 is star3,
      getattr(w3, "full_name", None))
br3._decide_conn_smythe()  # decide again: banking must stay idempotent
check("no double bank on re-decide",
      sum(1 for e in star3.career_accolades
          if e.get("award") == "conn_smythe") == 1)

# ------------------------------------------------------- coach records --
print("== coach records ==")
hc = g.Staff("Joel", "Quenneville2", StaffRole.HEAD_COACH)
ac = g.Staff("Dave", "Tippett2", StaffRole.ASSISTANT_COACH)
scout = g.Staff("Sam", "Scout", StaffRole.HEAD_SCOUT)
check("head coach is coaching role", cr.is_coaching_role(hc))
check("assistant is coaching role", cr.is_coaching_role(ac))
check("scout is not", not cr.is_coaching_role(scout))
e1 = cr.record_staff_season(hc, "2025-26", "Chicago", 48, 26, 8,
                            "Won Stanley Cup")
check("entry fields", e1["w"] == 48 and e1["playoff"] == "Won Stanley Cup"
      and e1["role"] == "Head Coach" and e1["jack_adams"] is False, e1)
cr.record_staff_season(ac, "2025-26", "Chicago", 48, 26, 8,
                       "Won Stanley Cup")
check("assistant role stamped", ac.career_record[0]["role"] == "Assistant Coach")
# idempotent re-record
cr.record_staff_season(hc, "2025-26", "Chicago", 50, 24, 8,
                       "Won Stanley Cup", jack_adams=True)
check("re-record updates in place",
      len(hc.career_record) == 1 and hc.career_record[0]["w"] == 50
      and hc.career_record[0]["jack_adams"] is True)
cr.record_staff_season(hc, "2026-27", "Chicago", 40, 30, 12,
                       "Lost Division Semifinals")
t = cr.career_totals(hc.career_record)
check("totals", t["w"] == 90 and t["l"] == 54 and t["seasons"] == 2
      and t["cups"] == 1 and t["adams"] == 1, t)

# playoff_result_for_team against a mock bracket
s1 = SimpleNamespace(name="Wild Card Round", team1=t1, team2=t2,
                     is_complete=True)
sF = SimpleNamespace(name="Stanley Cup Final", team1=t1,
                     team2=SimpleNamespace(team_name="Gamma", id=3),
                     is_complete=True)
mock_br = SimpleNamespace(playoff_series={"a": [s1], "b": [sF]})
check("champion result",
      cr.playoff_result_for_team(t1, mock_br, t1) == "Won Stanley Cup")
check("finalist result",
      cr.playoff_result_for_team(
          SimpleNamespace(team_name="Gamma", id=3), mock_br, t1)
      == "Lost Stanley Cup Final")
check("early exit result",
      cr.playoff_result_for_team(t2, mock_br, t1) == "Lost Wild Card Round")
check("missed playoffs",
      cr.playoff_result_for_team(
          SimpleNamespace(team_name="Delta", id=4), mock_br, t1)
      == "Missed playoffs")
check("None bracket safe",
      cr.playoff_result_for_team(t2, None, None) == "Missed playoffs")

# find_coach
teamX = SimpleNamespace(team_name="Chicago", staff=[hc, ac],
                        coach=hc)
found = cr.find_coach([teamX], "Joel Quenneville2", "Chicago")
check("find_coach exact match", found is hc)
found2 = cr.find_coach([teamX], "Nobody Here", "Chicago")
check("find_coach fallback to head coach", found2 is hc, found2)

# ------------------------------------------------- reputation wiring --
print("== reputation fine-tune ==")
sA = g.Staff("Win", "Now", StaffRole.HEAD_COACH)
sB = g.Staff("Also", "Good", StaffRole.HEAD_COACH)
sA.career_reputation = sB.career_reputation = 60
rs.update_staff_reputation(sA, team_win_pct=0.6, championships=0,
                           jack_adams=True)
rs.update_staff_reputation(sB, team_win_pct=0.6, championships=0)
check("jack adams +8 over same season",
      sA.career_reputation - sB.career_reputation == 8,
      (sA.career_reputation, sB.career_reputation))

# team_perception: track record buys rope in a bad year
for s, n in ((sA, 0), (sB, 0)):
    pass
sC = g.Staff("Proven", "Winner", StaffRole.HEAD_COACH)
sD = g.Staff("Unproven", "Rookie", StaffRole.HEAD_COACH)
for s in (sC, sD):
    s.man_management = s.motivating = s.leadership = 60
    s.controversy = 10
acc.bank_accolade(sC, "stanley_cup", "2024-25")
acc.bank_accolade(sC, "jack_adams", "2025-26")
pC = rs.team_perception(sC, {"win_pct": 0.40})
pD = rs.team_perception(sD, {"win_pct": 0.40})
check("track record cushions a bad year", pC > pD, (pC, pD))
check("cushion capped at +8", pC - pD <= 8.01, (pC, pD))

# conn smythe -> player reputation stacks
pl = SimpleNamespace(reputation=40, leadership=70, age=28,
                     captaincy=None, controversy=0,
                     reputation_history=[], career_accolades=[])
r0 = rs.update_player_reputation(pl, season_points=90, games_played=82,
                                 league_avg_ppg=0.9, awards=["hart"],
                                 playoff_rounds_won=0)
r1 = rs.update_player_reputation(pl, season_points=90, games_played=82,
                                 league_avg_ppg=0.9,
                                 awards=["hart", "conn_smythe"],
                                 playoff_rounds_won=4)
check("smythe adds +12 over hart-only",
      r1 - r0 == 27, (r0, r1))  # 12 smythe + 15 playoff rounds
check("ratchet never drops",
      rs.update_player_reputation(pl, season_points=10, games_played=82,
                                  league_avg_ppg=0.9, awards=[],
                                  playoff_rounds_won=0) == r1)

# ------------------------------------------------------- save / load --
print("== save/load ==")
import save_load_system as sls
saver = sls.GameSaveManager.__new__(sls.GameSaveManager)
pstats = PlayerStats()
pstats.games_played = 16; pstats.goals = 9; pstats.assists = 11
pstats.saves = 400; pstats.wins = 12
d = saver._serialize_player_stats(pstats)
back = saver._restore_player_stats(d)
check("playoff_stats round-trips",
      back.games_played == 16 and back.goals == 9 and back.wins == 12
      and back.saves == 400, (back.games_played, back.goals))

print("== staff card record tab (headless gui) ==")
try:
    import tkinter as tk
    root = tk.Tk()
    root.geometry("1600x900+0+0")
    root.update()
    from popup_system import register
    register(root)
    from datetime import date

    gteam = SimpleNamespace(team_name="Test Club", roster=[], staff=[],
                            inbox=[])
    gapp = SimpleNamespace(
        league=SimpleNamespace(teams=[gteam]), user_team=gteam,
        open_windows={}, current_date=date(2026, 11, 15),
        BG_COLOR="#1a1a2e", CONTENT_BG="#0e0e11",
        TEXT_COLOR="#ffffff", FONT_FAMILY="Segoe UI")
    from staff_management_window import StaffManagementView
    view = StaffManagementView(root, app=gapp)
    view.pack(fill="both", expand=True)
    root.update()

    gui_hc = g.Staff("Record", "Coach", StaffRole.HEAD_COACH)
    cr.record_staff_season(gui_hc, "2024-25", "Test Club", 52, 22, 8,
                           "Won Stanley Cup", jack_adams=True)
    cr.record_staff_season(gui_hc, "2025-26", "Test Club", 38, 34, 10,
                           "Lost Division Semifinals")
    acc.bank_accolade(gui_hc, "stanley_cup", "2024-25")
    acc.bank_accolade(gui_hc, "jack_adams", "2024-25")
    gui_ac = g.Staff("Help", "Er", StaffRole.ASSISTANT_COACH)
    cr.record_staff_season(gui_ac, "2025-26", "Test Club", 38, 34, 10,
                           "Lost Division Semifinals")

    def open_and_click_record(staff_member):
        view.show_staff_details_window(staff_member, is_current=True)
        root.update()
        found = []
        def rec(wid):
            try:
                entry = getattr(wid, "_popup_entry", None)
                if entry and "Staff Details" in str(
                        getattr(wid, "_popup_title", "")):
                    found.append(wid)
            except Exception:
                pass
            for ch in wid.winfo_children():
                rec(ch)
        rec(root)
        assert found, "details popup not found"
        popup = found[0]
        clicked = []
        def rec2(wid):
            try:
                if wid.cget("text") == "Record":
                    wid.invoke(); clicked.append(True); return
            except Exception:
                pass
            for ch in wid.winfo_children():
                if not clicked:
                    rec2(ch)
        rec2(popup)
        assert clicked, "Record tab button not found"
        root.update()
        texts = []
        def walk(wid):
            try:
                t = wid.cget("text")
                if isinstance(t, str) and t:
                    texts.append(t)
            except Exception:
                pass
            for ch in wid.winfo_children():
                walk(ch)
        walk(popup)
        popup.destroy()
        root.update()
        return texts

    t1 = open_and_click_record(gui_hc)
    blob1 = "\n".join(t1)
    check("record tab renders hc seasons",
          "2024-25" in blob1 and "2025-26" in blob1, blob1[:200])
    check("record tab shows w-l-otl", "52-22-8" in blob1)
    check("record tab shows cup", "Won Stanley Cup" in blob1)
    check("record tab shows adams trophy", "\U0001f3c6" in blob1)
    check("record tab totals", "90-56-18" in blob1, blob1[:300])
    check("record tab honours",
          "Stanley Cup Winner: 2024-25" in blob1
          and "Jack Adams Award Winner: 2024-25" in blob1)
    t2 = open_and_click_record(gui_ac)
    check("assistant gets record tab too",
          "2025-26" in "\n".join(t2) and "Assistant Coach" in "\n".join(t2))
    # scout must NOT get the tab
    gsc = g.Staff("No", "Tab", StaffRole.HEAD_SCOUT)
    view.show_staff_details_window(gsc, is_current=True)
    root.update()
    tab_names = []
    def rec3(wid):
        try:
            if isinstance(wid.cget("text"), str) and wid.cget("text") in (
                    "Overview", "Attributes", "Standing", "Personality",
                    "Track Record", "Analytics", "Record"):
                tab_names.append(wid.cget("text"))
        except Exception:
            pass
        for ch in wid.winfo_children():
            rec3(ch)
    rec3(root)
    check("scout has no record tab", "Record" not in tab_names, tab_names)
    root.destroy()
except Exception as e:
    check("staff card record tab (headless gui)", False, repr(e)[:300])

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
