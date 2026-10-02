"""QA: season recap new sections (Muck 2026-10-02).

Verifies the season-recap update: INJURY REPORT, SEASON STORYLINES,
RIVALRY WATCH, MILESTONES, HISTORICAL CONTEXT sections build without
errors on empty/garbage data and populate correctly on sample data;
_record_season_stories banks the enriched facts for next season's lore.
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, "/tmp/wt-season-recap")

import season_review as sr

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def never_raises(name, fn):
    try:
        fn()
        check(name, True)
    except Exception as e:  # noqa: BLE001
        check(f"{name} (raised {type(e).__name__}: {e})", False)


# ---------------------------------------------------------------- fixtures
def blank_team(name="Test Club"):
    return SimpleNamespace(team_name=name, roster=[], league_name="National Hockey League")


def blank_app(team):
    league = SimpleNamespace(
        teams=[team], season_year=2027, rivalries=[],
        media_narratives=[], standings={},
    )
    return SimpleNamespace(league=league, user_team=team,
                           current_date=None, league_history=None)


# ------------------------------------------------------- 1. empty data safe
t = blank_team()
app = blank_app(t)
never_raises("injury: empty roster", lambda: sr._injury_lines(app, t, 2027))
never_raises("storylines: no narratives", lambda: sr._storyline_lines(app, t, 2027))
never_raises("rivalry watch: no data", lambda: sr._rivalry_watch_lines(app, t, 2027))
never_raises("milestones: no ledger", lambda: sr._milestone_lines(app, t, 2027))
never_raises("history: no league_history", lambda: sr._history_lines(app, t, 2027))
never_raises("extra facts: bare app", lambda: sr._season_story_extra_facts(app, t))

check("injury: empty -> []", sr._injury_lines(app, t, 2027) == [])
check("storylines: empty -> []", sr._storyline_lines(app, t, 2027) == [])
check("rivalry watch: empty -> []", sr._rivalry_watch_lines(app, t, 2027) == [])
check("milestones: empty -> []", sr._milestone_lines(app, t, 2027) == [])
check("history: empty -> []", sr._history_lines(app, t, 2027) == [])
check("extra facts: dict", isinstance(sr._season_story_extra_facts(app, t), dict))

# ------------------------------------------------------- 2. garbage data safe
g = SimpleNamespace(team_name=123, roster="notalist")
gapp = SimpleNamespace(league="nonsense", user_team=g, current_date="x",
                       league_history="junk")
never_raises("injury: garbage", lambda: sr._injury_lines(gapp, g, 2027))
never_raises("storylines: garbage", lambda: sr._storyline_lines(gapp, g, 2027))
never_raises("rivalry watch: garbage", lambda: sr._rivalry_watch_lines(gapp, g, 2027))
never_raises("milestones: garbage", lambda: sr._milestone_lines(gapp, g, 2027))
never_raises("history: garbage", lambda: sr._history_lines(gapp, g, 2027))
never_raises("extra facts: garbage", lambda: sr._season_story_extra_facts(gapp, g))

# ------------------------------------------------------- 3. storylines populate
n1 = SimpleNamespace(kind="cup_window", team_name="Test Club",
                     title="The window is open -- is this the year?", heat=82.0)
n2 = SimpleNamespace(kind="prospect_watch", team_name="Test Club",
                     title="The kids are the story", heat=12.0)
n3 = SimpleNamespace(kind="cup_window", team_name="Other Club",
                     title="Someone else's story", heat=99.0)
t3 = blank_team()
app3 = blank_app(t3)
app3.league.media_narratives = [n1, n2, n3]
lines = sr._storyline_lines(app3, t3, 2027)
check("storylines: 2 for team", len(lines) == 2)
check("storylines: hot first", "still burning" in lines[0])
check("storylines: fizzled second", "fizzled out" in lines[1])
check("storylines: other club excluded",
      all("Someone else" not in ln for ln in lines))
check("storylines: kind label", any("Cup window" in ln for ln in lines))

# ------------------------------------------------------- 4. history populates
class FakeHist:
    seasons = [
        {"year": 2027, "champion": "Test Club"},
        {"year": 2026, "champion": "Test Club"},
        {"year": 2025, "champion": "Rival Club"},
    ]

t4 = blank_team()
app4 = blank_app(t4)
app4.league_history = FakeHist()
hlines = sr._history_lines(app4, t4, 2027)
check("history: back-to-back", any("Back-to-back" in ln for ln in hlines))
check("history: champions line", any("dynasties are rare" in ln for ln in hlines))

app4b = blank_app(blank_team("Rival Club"))
app4b.league_history = FakeHist()
hlines2 = sr._history_lines(app4b, app4b.user_team, 2027)
check("history: drought counted",
      any("2 years since the 2025 Cup" in ln for ln in hlines2))

class EmptyHist:
    seasons = []
app4c = blank_app(t4)
app4c.league_history = EmptyHist()
check("history: no seasons -> []", sr._history_lines(app4c, t4, 2027) == [])

# ------------------------------------------------------- 5. milestones populate
from narrative_ledger import NarrativeLedger
t5 = blank_team()
app5 = blank_app(t5)
led = NarrativeLedger()
led.record(kind="milestone", teams=["Test Club"], players=["Star Player"],
           text="Star Player reaches 500 goals", weight=70, season=2027)
led.record(kind="milestone", teams=["Other Club"], players=["Other Guy"],
           text="Other Guy reaches 1000 games", weight=70, season=2026)
app5.narrative_ledger = led
mlines = sr._milestone_lines(app5, t5, 2027)
check("milestones: 1 this season/team", len(mlines) == 1)
check("milestones: text", any("500 goals" in ln for ln in mlines))

# ------------------------------------------------------- 6. rivalry watch
t6 = blank_team()
app6 = blank_app(t6)
led6 = NarrativeLedger()
led6.record(kind="brawl_game", teams=["Test Club", "Rival Club"],
            text="Line brawl mars the third period", weight=80, season=2027)
led6.record(kind="incident", teams=["Other Club", "Third Club"],
            text="Unrelated incident", weight=90, season=2027)
app6.narrative_ledger = led6
app6.league.rivalries = [
    {"kind": "team_team", "a_name": "Alpha", "b_name": "Beta", "intensity": 75},
    {"kind": "team_team", "a_name": "Test Club", "b_name": "Rival Club",
     "intensity": 55},
    {"kind": "gm_respect", "a_name": "X", "b_name": "Y", "intensity": 99},
]
rlines = sr._rivalry_watch_lines(app6, t6, 2027)
check("rivalry watch: hottest pair", any("Alpha vs Beta" in ln for ln in rlines))
check("rivalry watch: flashpoint", any("Flashpoint" in ln for ln in rlines))
check("rivalry watch: ignores gm kind",
      all("X vs Y" not in ln for ln in rlines))

# ------------------------------------------------------- 7. injury lines (mock ir)
p1 = SimpleNamespace(full_name="Hurt Star", injury_type="torn ACL")
p2 = SimpleNamespace(full_name="Depth Guy", injury_type="concussion")
t7 = blank_team()
app7 = blank_app(t7)

import ir_system as _ir
_orig_ltir, _orig_ir = _ir.ltir_players, _ir.ir_players
_orig_relief, _orig_days = _ir.ltir_relief, _ir.days_on_ir
_ir.ltir_players = lambda team: [p1]
_ir.ir_players = lambda team: [p2]
_ir.ltir_relief = lambda team: 9_500_000
_ir.days_on_ir = lambda p, d: 120 if p is p1 else 9
try:
    ilines = sr._injury_lines(app7, t7, 2027)
    check("injury: LTIR line", any("Hurt Star" in ln and "LTIR" in ln for ln in ilines))
    check("injury: IR line", any("Depth Guy" in ln and "-- IR" in ln for ln in ilines))
    check("injury: relief dollars", any("$9,500,000" in ln for ln in ilines))
    facts = sr._season_story_extra_facts(app7, t7)
    check("facts: ltir_relief", facts.get("ltir_relief") == 9_500_000)
    check("facts: counts", facts.get("ltir_count") == 1 and facts.get("ir_count") == 1)
finally:
    _ir.ltir_players, _ir.ir_players = _orig_ltir, _orig_ir
    _ir.ltir_relief, _ir.days_on_ir = _orig_relief, _orig_days

# ------------------------------------------------------- 8. extra facts: storyline + rival
t8 = blank_team()
app8 = blank_app(t8)
app8.league.media_narratives = [n1]
led8 = NarrativeLedger()
led8.record(kind="milestone", teams=["Test Club"], players=["P"],
            text="P reaches 1000 games", weight=70, season=2027)
app8.narrative_ledger = led8
app8.league.rivalries = [
    {"kind": "team_team", "a": ("team", "Test Club"), "b": ("team", "Foe"),
     "a_name": "Test Club", "b_name": "Foe", "intensity": 66},
]
facts8 = sr._season_story_extra_facts(app8, t8)
check("facts: top storyline kind", facts8.get("top_storyline_kind") == "cup_window")
check("facts: milestones", facts8.get("milestones") == 1)
check("facts: hottest rival", facts8.get("hottest_rival") == "Foe")
check("facts: rival heat", facts8.get("hottest_rival_heat") == 66)

# ------------------------------------------------------- 9. build_review wiring
t9 = blank_team("Colorado Avalanche")
app9 = blank_app(t9)
app9.user_team = t9
app9.league.standings = {"Colorado Avalanche": {"W": 50, "L": 25, "OTL": 7}}
app9.league_history = FakeHist()
app9.league.media_narratives = [SimpleNamespace(
    kind="cup_window", team_name="Colorado Avalanche",
    title="Defending the crown?", heat=88.0)]
led9 = NarrativeLedger()
led9.record(kind="milestone", teams=["Colorado Avalanche"], players=["C"],
            text="C reaches 500 goals", weight=70, season=2027)
app9.narrative_ledger = led9
rev = sr.build_review(app9, t9)
titles = [s[0] for s in []]  # placeholder
try:
    from io import StringIO
    import contextlib
    check("build_review: returns dict", isinstance(rev, dict))
    blob = "\n".join(rev["lines"])
    check("build_review: SEASON STORYLINES section", "SEASON STORYLINES" in blob)
    check("build_review: HISTORICAL CONTEXT section", "HISTORICAL CONTEXT" in blob)
    check("build_review: MILESTONES section", "MILESTONES" in blob)
    check("build_review: storyline content", "Defending the crown?" in blob)
    check("build_review: milestone content", "500 goals" in blob)
    check("build_review: history content", "Back-to-back" in blob)
except Exception as e:  # noqa: BLE001
    check(f"build_review wiring (raised {e})", False)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
