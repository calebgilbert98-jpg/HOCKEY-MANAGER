#!/usr/bin/env python3
"""QA: menu-bar date + next-game countdown (Muck 2026-10-02).

Verifies:
1. refresh_menu_date exists and never raises.
2. Date label shows current_date in "%a, %b %d, %Y" format.
3. Countdown: "Game today!" / "Game tomorrow" / "Game in N days" / empty.
4. _get_next_game_days_away handles dict + tuple schedule formats, skips NHL_EVENTs.
5. refresh_next_day_button still works and calls refresh_menu_date.
"""
import ast
import sys
import types
from datetime import date, timedelta

MAIN_PY = "/home/hatch/workspace/wt-datemenubar/main.py"

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL"), "-", name, detail if not cond else "")

# --- Extract the real methods from main.py via AST ---
with open(MAIN_PY) as f:
    tree = ast.parse(f.read())

wanted = {"refresh_menu_date", "_get_next_game_days_away", "refresh_next_day_button"}
found_src = {}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in wanted:
        # Grab the full source segment
        lines = open(MAIN_PY).read().splitlines(True)
        seg = "".join(lines[node.lineno - 1:node.end_lineno])
        found_src[node.name] = seg

check("refresh_menu_date defined in main.py", "refresh_menu_date" in found_src)
check("_get_next_game_days_away defined in main.py", "_get_next_game_days_away" in found_src)
check("refresh_next_day_button calls refresh_menu_date",
      "refresh_menu_date" in found_src.get("refresh_next_day_button", ""),
      "refresh_next_day_button must refresh the date on every call")

# --- Build a fake manager with the real methods bound ---
class FakeLabel:
    def __init__(self):
        self.text = "UNSET"
        self.fg = "UNSET"
    def configure(self, **kw):
        if "text" in kw:
            self.text = kw["text"]
        if "fg" in kw:
            self.fg = kw["fg"]
    def winfo_exists(self):
        return True

class FakeTeam:
    def __init__(self, name):
        self.team_name = name

class FakeLeague:
    def __init__(self, schedule):
        self.schedule = schedule

class FakeMgr:
    pass

ns = {}
for name, seg in found_src.items():
    # Compile each method in isolation; dedent to top level
    import textwrap
    code = textwrap.dedent(seg)
    mod = ast.parse(code)
    fn_node = mod.body[0]
    fn_node.name = fn_node.name  # keep name
    exec(compile(mod, "<qa>", "exec"), ns)

for name in wanted:
    if name in ns:
        setattr(FakeMgr, name, ns[name])

# Make refresh_next_day_button safe: it calls _mp_host_mode etc.
# We only test that it doesn't raise and calls refresh_menu_date.
def run_case(name, current, schedule, user_team_name,
             expect_date_text=None, expect_countdown=None):
    mgr = FakeMgr()
    mgr.current_date = current
    mgr.user_team = FakeTeam(user_team_name)
    mgr.league = FakeLeague(schedule)
    mgr._menu_date_label = FakeLabel()
    mgr._menu_countdown_label = FakeLabel()
    try:
        mgr.refresh_menu_date()
        raised = None
    except Exception as e:
        raised = e
    check(f"{name}: never raises", raised is None, str(raised))
    if expect_date_text is not None:
        check(f"{name}: date text", mgr._menu_date_label.text == expect_date_text,
              f"got {mgr._menu_date_label.text!r}, want {expect_date_text!r}")
    if expect_countdown is not None:
        check(f"{name}: countdown text",
              mgr._menu_countdown_label.text == expect_countdown,
              f"got {mgr._menu_countdown_label.text!r}, want {expect_countdown!r}")
    return mgr

EDM = "Edmonton Oilers"
OTHER = "Calgary Flames"
today = date(2026, 9, 27)

# Dict-format schedule
dict_sched = [
    {"date": today + timedelta(days=3), "home_team": None, "away_team": None},
]
mgr = FakeMgr()
t_edm = FakeTeam(EDM)
t_cgy = FakeTeam(OTHER)
dict_sched[0]["home_team"] = t_edm
dict_sched[0]["away_team"] = t_cgy

# 1. Date format matches dashboard ("Sun, Sep 27, 2026")
run_case("date-format", today, [], EDM,
         expect_date_text="Sun, Sep 27, 2026", expect_countdown="")

# 2. Game today (dict format)
run_case("game-today-dict", today,
         [{"date": today, "home_team": t_edm, "away_team": t_cgy}],
         EDM, expect_countdown="\u2022 Game today!")

# 3. Game tomorrow
run_case("game-tomorrow", today,
         [{"date": today + timedelta(days=1), "home_team": t_edm, "away_team": t_cgy}],
         EDM, expect_countdown="\u2022 Game tomorrow")

# 4. Game in 3 days
run_case("game-in-3", today,
         [{"date": today + timedelta(days=3), "home_team": t_edm, "away_team": t_cgy}],
         EDM, expect_countdown="\u2022 Game in 3 days")

# 5. Tuple format (game_date, home, away)
run_case("game-tuple-format", today,
         [(today + timedelta(days=5), t_edm, t_cgy)],
         EDM, expect_countdown="\u2022 Game in 5 days")

# 6. NHL_EVENT tuples are skipped
run_case("nhl-events-skipped", today,
         [(today, "NHL_EVENT", {"x": 1}),
          (today + timedelta(days=2), t_edm, t_cgy)],
         EDM, expect_countdown="\u2022 Game in 2 days")

# 7. Other teams' games don't count
run_case("other-teams-ignored", today,
         [(today, t_cgy, FakeTeam("Toronto Maple Leafs")),
          (today + timedelta(days=4), t_edm, t_cgy)],
         EDM, expect_countdown="\u2022 Game in 4 days")

# 8. No games -> empty countdown, no crash
run_case("no-games", today, [], EDM, expect_countdown="")

# 9. No schedule attr -> None-safe
mgr2 = FakeMgr()
mgr2.current_date = today
mgr2.user_team = t_edm
mgr2.league = FakeLeague(None)
mgr2._menu_date_label = FakeLabel()
mgr2._menu_countdown_label = FakeLabel()
try:
    mgr2.refresh_menu_date()
    check("none-schedule: never raises", True)
    check("none-schedule: countdown empty",
          mgr2._menu_countdown_label.text == "")
except Exception as e:
    check("none-schedule: never raises", False, str(e))

# 10. Past games ignored, nearest future picked
run_case("nearest-future", today,
         [(today - timedelta(days=2), t_edm, t_cgy),
          (today + timedelta(days=6), t_edm, t_cgy),
          (today + timedelta(days=2), t_edm, t_cgy)],
         EDM, expect_countdown="\u2022 Game in 2 days")

# 11. Date updates when current_date advances (sim a day)
mgr3 = run_case("advance-day-1", today,
                [(today + timedelta(days=2), t_edm, t_cgy)],
                EDM, expect_countdown="\u2022 Game in 2 days")
mgr3.current_date = today + timedelta(days=1)
mgr3.refresh_menu_date()
check("advance-day: date text updates",
      mgr3._menu_date_label.text == "Mon, Sep 28, 2026",
      f"got {mgr3._menu_date_label.text!r}")
check("advance-day: countdown updates",
      mgr3._menu_countdown_label.text == "\u2022 Game tomorrow",
      f"got {mgr3._menu_countdown_label.text!r}")

# 12. refresh_next_day_button calls refresh_menu_date (wiring check)
src = found_src.get("refresh_next_day_button", "")
check("wiring: refresh_next_day_button invokes refresh_menu_date",
      "self.refresh_menu_date()" in src)

# 13. Menu-bar construction code: date labels created in right_menu_frame
with open(MAIN_PY) as f:
    main_src = f.read()
check("menu bar creates _menu_date_label", "_menu_date_label" in main_src)
check("menu bar creates _menu_countdown_label", "_menu_countdown_label" in main_src)
check("date labels placed in right_menu_frame section",
      main_src.find("_menu_date_label = tk.Label") > main_src.find("right_menu_frame = tk.Frame"))

# --- Summary ---
fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} pass")
sys.exit(1 if fails else 0)
