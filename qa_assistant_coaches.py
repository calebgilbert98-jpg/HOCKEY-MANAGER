"""Deterministic QA: assistant coaches, prowess-scaled, results-gated.

No development aspect. Any great coach can have the effect; it decays with
losing / poor mesh / shelf life; icons never decay (legacy cemented).
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, '.')

import assistant_coaches as ac
import reputation_system as rs

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name +
          (f" -- {detail}" if detail and not cond else ""))


def coach(**kw):
    base = dict(first_name="Paul", last_name="Coffey",
                role=SimpleNamespace(value="Assistant Coach"),
                attacking_coaching=60, defensive_coaching=92,
                coaching_goalies=40, working_with_youngsters=80,
                tactical_knowledge=85, man_management=80, reputation=85,
                experience=12, years_with_team=1, morale=70,
                icon_team="", icon_level="", assistant_effect=None)
    base.update(kw)
    return SimpleNamespace(**base)


def skater(morale=70):
    return SimpleNamespace(primary_position="LD", age=24, morale=morale)


def team_of(*staff, name="Edmonton Oilers", roster=(), wins=0, losses=0,
            fam=85):
    return SimpleNamespace(team_name=name, staff=list(staff),
                           roster=list(roster), wins=wins, losses=losses,
                           otl=0, tactics_familiarity=fam,
                           tactics=dict(offense="balanced", defense="hybrid",
                                        pp="umbrella", pk="diamond",
                                        philosophy="pragmatist"))

# Pin chemistry: deterministic mesh.
_chem_score = [80.0]
_orig_chem = rs.team_chemistry
rs.team_chemistry = lambda roster, ctx=None: {"score": _chem_score[0]}

# --- specialties / icons / retirement (unchanged) ---
print("--- identity ---")
check("defense specialty", ac.assistant_specialty(coach()) == "defense")
icon = coach(icon_team="Edmonton Oilers", icon_level="icon")
check("icon recognized by his team",
      ac.is_franchise_icon(icon, team_of(icon)))
check("not an icon elsewhere",
      not ac.is_franchise_icon(icon, team_of(name="Toronto Maple Leafs")))
star = SimpleNamespace(leadership=80, controversy=20, career_reputation=85,
                       career_games=900, last_team_name="Edmonton Oilers")
check("star retires an icon",
      rs.staffer_from_retired_player(star, []).get("icon_team")
      == "Edmonton Oilers")

# --- prowess: scaled on the coach, not the legend ---
print("--- prowess ---")
great = coach()  # 92 D-coaching, 85s elsewhere, 12 yrs
dud = coach(defensive_coaching=42, tactical_knowledge=45, man_management=40,
            reputation=35, experience=2)
pg, pd = ac.assistant_prowess(great), ac.assistant_prowess(dud)
check("great coach: high prowess", pg >= 80, f"{pg:.1f}")
check("dud: low prowess", pd < 50, f"{pd:.1f}")
check("prowess > icon status: non-icon can out-rate",
      ac.assistant_prowess(coach(icon_team="", icon_level="")) >= 80)

# --- effectiveness seeds from prowess ---
print("--- seeding ---")
check("effect seeds from prowess",
      abs(ac.assistant_effect(great) - pg) < 0.01)
check("stored after seeding", great.assistant_effect is not None)

# --- monthly drift: reflective with results ---
print("--- drift ---")
tm_win = team_of(great, wins=40, losses=20)   # .667
tm_lose = team_of(coach(), wins=15, losses=45)  # .250
e0 = ac.assistant_effect(tm_win.staff[0])
ac.assistants_monthly_tick(tm_win)
check("winning grows him", tm_win.staff[0].assistant_effect > e0,
      f"{e0:.1f} -> {tm_win.staff[0].assistant_effect:.1f}")
e1 = ac.assistant_effect(tm_lose.staff[0])
ac.assistants_monthly_tick(tm_lose)
check("losing erodes him", tm_lose.staff[0].assistant_effect < e1,
      f"{e1:.1f} -> {tm_lose.staff[0].assistant_effect:.1f}")

# mesh: fractured room accelerates the slide
_chem_score[0] = 30.0
tm_frac = team_of(coach(), wins=30, losses=30)
e2 = ac.assistant_effect(tm_frac.staff[0])
ac.assistants_monthly_tick(tm_frac)
_chem_score[0] = 80.0
check("fractured room drags even at .500", tm_frac.staff[0].assistant_effect < e2,
      f"{e2:.1f} -> {tm_frac.staff[0].assistant_effect:.1f}")

# shelf life: the message gets stale (isolated: same coach, 1yr vs 5yr)
fresh_c = coach(years_with_team=1)
stale_c = coach(years_with_team=5)
tm_fresh = team_of(fresh_c, wins=30, losses=30)
tm_stale = team_of(stale_c, wins=30, losses=30)
ac.assistants_monthly_tick(tm_fresh)
ac.assistants_monthly_tick(tm_stale)
check("3+ years: shelf-life drag",
      tm_stale.staff[0].assistant_effect < tm_fresh.staff[0].assistant_effect,
      f"5yr {tm_stale.staff[0].assistant_effect:.1f} vs "
      f"1yr {tm_fresh.staff[0].assistant_effect:.1f}")

# system in flux: low familiarity hurts traction (chemistry neutral)
_chem_score[0] = 60.0
tm_flux = team_of(coach(), wins=30, losses=30, fam=50)
tm_set = team_of(coach(), wins=30, losses=30, fam=85)
ac.assistants_monthly_tick(tm_flux)
ac.assistants_monthly_tick(tm_set)
_chem_score[0] = 80.0
check("system in flux: less traction",
      tm_flux.staff[0].assistant_effect < tm_set.staff[0].assistant_effect,
      f"flux {tm_flux.staff[0].assistant_effect:.1f} vs "
      f"set {tm_set.staff[0].assistant_effect:.1f}")

# --- icons never decay ---
print("--- icons cemented ---")
icon_c = coach(icon_team="Edmonton Oilers", icon_level="icon",
               years_with_team=8)
_chem_score[0] = 25.0  # fractured
tm_icon = team_of(icon_c, wins=10, losses=50, fam=40,  # awful everywhere
                 name="Edmonton Oilers")
p0 = ac.assistant_prowess(icon_c)
for _ in range(6):  # half a season of misery
    ac.assistants_monthly_tick(tm_icon)
check("icon effect cemented through misery",
      abs(tm_icon.staff[0].assistant_effect - p0) < 0.01,
      f"{tm_icon.staff[0].assistant_effect:.1f} vs prowess {p0:.1f}")
_chem_score[0] = 80.0

# --- morale: the "brings more out of players" channel ---
print("--- morale channel ---")
r1 = [skater(70) for _ in range(5)]
tm_g = team_of(coach(), roster=r1, wins=40, losses=20)
ac.assistants_monthly_tick(tm_g)
check("great assistant lifts the room", all(p.morale > 70 for p in r1),
      str([round(p.morale, 2) for p in r1]))
r2 = [skater(70) for _ in range(5)]
tm_d = team_of(dud, roster=r2, wins=40, losses=20)
ac.assistants_monthly_tick(tm_d)
check("dud drags the room", all(p.morale < 70 for p in r2),
      str([round(p.morale, 2) for p in r2]))

# --- stale-message news ---
print("--- news ---")
wash = coach(assistant_effect=56, years_with_team=6)
tm_w = team_of(wash, wins=10, losses=50)
lines = ac.assistants_monthly_tick(tm_w)
check("stale voice makes the news",
      any("stale" in l for l in lines), str(lines))

# --- familiarity buy-in from effectiveness ---
print("--- buy-in ---")
check("elite: +2", ac.assistant_familiarity_bonus(team_of(coach())) == 2.0)
mid = coach(defensive_coaching=72, tactical_knowledge=70, man_management=65,
            reputation=60, experience=8, assistant_effect=70.0)
check("solid: +1", ac.assistant_familiarity_bonus(team_of(mid)) == 1.0)
washed = coach(assistant_effect=35.0)
check("dud: -1 slows the room",
      ac.assistant_familiarity_bonus(team_of(washed)) == -1.0)
check("icon always elite",
      ac.assistant_familiarity_bonus(
          team_of(icon_c, name="Edmonton Oilers")) == 2.0)
check("clamped", ac.assistant_familiarity_bonus(
    team_of(coach(), coach(), coach())) == 4.0)

import tactics as tx
t_dud = team_of(washed, fam=50)
t_none = team_of(fam=50)
tx.tick_tactics_familiarity(t_dud)
tx.tick_tactics_familiarity(t_none)
check("dud slows learning vs nobody",
      t_dud.tactics_familiarity < t_none.tactics_familiarity,
      f"{t_dud.tactics_familiarity} vs {t_none.tactics_familiarity}")

# --- development: modest, specialty-based, head coach stays main ---
print("--- development ---")


def dskater(pos="LD", age=20):
    return SimpleNamespace(primary_position=pos, age=age, morale=70,
                           team_name="Edmonton Oilers")


kid_d = dskater("LD", 20)
tm_dev = team_of(coach(), roster=[kid_d])  # 92 D-coaching, eff ~82.6
dd = ac.assistant_development_deltas(kid_d, tm_dev)
check("young D gets a modest bump", len(dd) == 1 and 0.5 <= dd[0][1] < 4.0,
      str(dd))
check("head coach still the main voice (bump < 4)",
      dd[0][1] < 4.0, str(dd[0][1]))

icon_dev = coach(icon_team="Edmonton Oilers", icon_level="icon")
tm_icon_dev = team_of(icon_dev, roster=[kid_d])
di = ac.assistant_development_deltas(kid_d, tm_icon_dev)
check("icon edge is small, not unbalanced",
      1.0 < di[0][1] / dd[0][1] < 1.35,
      f"{di[0][1]:.2f} vs {dd[0][1]:.2f}")

hot = coach(assistant_effect=90.0)
cold = coach(assistant_effect=40.0)
dh = ac.assistant_development_deltas(kid_d, team_of(hot, roster=[kid_d]))[0][1]
dc = ac.assistant_development_deltas(kid_d, team_of(cold, roster=[kid_d]))[0][1]
check("in-form assistant develops more than a stale one", dh > dc,
      f"{dh:.2f} vs {dc:.2f}")

check("veterans don't get the kid bump",
      ac.assistant_development_deltas(dskater("LD", 30), tm_dev) == [])
check("forwards don't learn from the D coach",
      ac.assistant_development_deltas(dskater("C", 20), tm_dev) == [])
gen_c = coach(defensive_coaching=55, attacking_coaching=55, coaching_goalies=55)
check("generalist develops nobody",
      ac.assistant_development_deltas(kid_d, team_of(gen_c)) == [])
gk = dskater("GOALIE", 20)
gcoach = coach(defensive_coaching=50, attacking_coaching=50, coaching_goalies=95)
dg = ac.assistant_development_deltas(gk, team_of(gcoach, roster=[gk]))
check("goalie coach develops goalies", len(dg) == 1 and dg[0][1] > 0.5,
      str(dg))

# --- hire hook ---
print("--- hire ---")
news = []


class FakeApp:
    def add_news(self, line):
        news.append(line)


line = ac.on_assistant_hired(team_of(name="Edmonton Oilers"), icon,
                             app=FakeApp())
check("icon hire is an event", "franchise icon" in line, line)
check("news delivered", len(news) == 1)
elite = coach(icon_team="", first_name="Dave", last_name="Elite")
line2 = ac.on_assistant_hired(team_of(), elite)
check("elite non-icon hire is a story", "highly-regarded" in line2, line2)
line3 = ac.on_assistant_hired(team_of(), dud)
check("dud hire: quiet line", "highly-regarded" not in line3
      and "icon" not in line3)
head = coach(role=SimpleNamespace(value="Head Coach"))
check("non-assistant: None", ac.on_assistant_hired(team_of(), head) is None)

# --- describe ---
desc = ac.describe_assistants(team_of(icon, dud))
check("describe shows effect + icon tag",
      any("FRANCHISE ICON" in l and "effect" in l for l in desc), str(desc))

rs.team_chemistry = _orig_chem
print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
