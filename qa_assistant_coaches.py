"""Deterministic QA for the assistant-coach / Coffey-effect system."""
import sys
from types import SimpleNamespace

sys.path.insert(0, '.')

import assistant_coaches as ac

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
                tactical_knowledge=85, icon_team="", icon_level="")
    base.update(kw)
    return SimpleNamespace(**base)


def skater(pos="LD", age=20, happiness=60):
    return SimpleNamespace(primary_position=pos, age=age, happiness=happiness,
                           team_name="Edmonton Oilers")


def team_of(*staff, name="Edmonton Oilers", roster=()):
    return SimpleNamespace(team_name=name, staff=list(staff), roster=list(roster))

# --- specialties ---
print("--- specialties ---")
check("defense specialty", ac.assistant_specialty(coach()) == "defense")
check("offense specialty",
      ac.assistant_specialty(coach(defensive_coaching=50,
                                   attacking_coaching=95)) == "offense")
check("goalie specialty",
      ac.assistant_specialty(coach(defensive_coaching=50, attacking_coaching=50,
                                   coaching_goalies=93)) == "goalie")
check("general below 60",
      ac.assistant_specialty(coach(defensive_coaching=55, attacking_coaching=55,
                                   coaching_goalies=55)) == "general")

# --- icon detection is team-specific ---
print("--- icon detection ---")
icon = coach(icon_team="Edmonton Oilers", icon_level="icon")
edm = team_of(icon)
tor = team_of(icon, name="Toronto Maple Leafs")
check("icon recognized by his team", ac.is_franchise_icon(icon, edm))
check("not an icon elsewhere", not ac.is_franchise_icon(icon, tor))
check("no icon_team, no icon",
      not ac.is_franchise_icon(coach(), edm))

# --- retirement stamping ---
print("--- retirement stamping ---")
import reputation_system as rs
star = SimpleNamespace(leadership=80, controversy=20, career_reputation=85,
                       career_games=900, last_team_name="Edmonton Oilers")
attrs = rs.staffer_from_retired_player(star, [])
check("star retires an icon of his last team",
      attrs.get("icon_team") == "Edmonton Oilers", str(attrs.get("icon_team")))
check("generational = icon level", attrs.get("icon_level") == "icon")
mid = SimpleNamespace(leadership=60, controversy=20, career_reputation=70,
                      career_games=450, last_team_name="Boston Bruins")
attrs2 = rs.staffer_from_retired_player(mid, [])
check("good-not-great = star level",
      attrs2.get("icon_team") == "Boston Bruins"
      and attrs2.get("icon_level") == "star")
scrub = SimpleNamespace(leadership=50, controversy=20, career_reputation=30,
                        career_games=200, last_team_name="Boston Bruins")
attrs3 = rs.staffer_from_retired_player(scrub, [])
check("scrub retires no icon", not attrs3.get("icon_team"))

# --- development deltas ---
print("--- development ---")
kid_d = skater("LD", 20)
tm = team_of(icon, roster=[kid_d])
d = ac.assistant_development_deltas(kid_d, tm)
check("young D gets a bump from the icon", len(d) == 1 and d[0][1] > 4,
      str(d))
check("icon label names him", "Coffey" in d[0][0] and "icon" in d[0][0])

plain = coach(icon_team="", icon_level="")  # great teacher, no status
tm2 = team_of(plain, roster=[kid_d])
d2 = ac.assistant_development_deltas(kid_d, tm2)
check("same teacher, no icon: smaller bump",
      0.5 <= d2[0][1] < d[0][1], f"{d2[0][1]} vs {d[0][1]}")

old_d = skater("LD", 30)
check("veterans don't get the kid bump",
      ac.assistant_development_deltas(old_d, tm) == [])
kid_f = skater("C", 20)
check("forwards don't learn from the D coach",
      ac.assistant_development_deltas(kid_f, tm) == [])
okl = skater("GOALIE", 20)
gcoach = coach(defensive_coaching=50, attacking_coaching=50, coaching_goalies=95)
tm3 = team_of(gcoach, roster=[okl])
d3 = ac.assistant_development_deltas(okl, tm3)
check("goalie coach develops goalies", len(d3) == 1 and d3[0][1] > 0, str(d3))

# --- familiarity buy-in ---
print("--- familiarity ---")
check("icon = +2 buy-in", ac.assistant_familiarity_bonus(tm) == 2.0)
star_c = coach(icon_team="Edmonton Oilers", icon_level="star")
check("star = +1", ac.assistant_familiarity_bonus(team_of(star_c)) == 1.0)
teacher = coach(icon_team="", tactical_knowledge=85)
check("great teacher (no icon) = +1",
      ac.assistant_familiarity_bonus(team_of(teacher)) == 1.0)
nobody = coach(icon_team="", tactical_knowledge=50)
check("nobody special = 0",
      ac.assistant_familiarity_bonus(team_of(nobody)) == 0.0)
many = team_of(icon, star_c, teacher, coach(icon_team="Edmonton Oilers",
                                            icon_level="icon"))
check("bonus capped at 4", ac.assistant_familiarity_bonus(many) == 4.0)

# --- tick integration ---
print("--- tick integration ---")
import tactics as tx
t_plain = SimpleNamespace(team_name="X", roster=[], staff=[nobody],
                          tactics=dict(offense="balanced", defense="hybrid",
                                       pp="umbrella", pk="diamond",
                                       philosophy="pragmatist"),
                          tactics_familiarity=50)
t_icon = SimpleNamespace(team_name="Edmonton Oilers", roster=[], staff=[icon],
                         tactics=dict(offense="balanced", defense="hybrid",
                                      pp="umbrella", pk="diamond",
                                      philosophy="pragmatist"),
                         tactics_familiarity=50)
tx.tick_tactics_familiarity(t_plain)
tx.tick_tactics_familiarity(t_icon)
check("icon room learns faster",
      t_icon.tactics_familiarity - t_plain.tactics_familiarity == 2.0,
      f"{t_icon.tactics_familiarity} vs {t_plain.tactics_familiarity}")

# --- hire hook ---
print("--- hire hook ---")
news = []


class FakeApp:
    def add_news(self, line):
        news.append(line)


kid2 = skater("RD", 21, happiness=60)
vet = skater("RD", 30, happiness=60)
htm = team_of(roster=[kid2, vet])
line = ac.on_assistant_hired(htm, icon, app=FakeApp())
check("icon hire makes the news", line is not None and "Coffey" in line,
      str(line))
check("news delivered", len(news) == 1)
check("young D gets the dream bump", kid2.happiness == 64, str(kid2.happiness))
check("veteran unmoved", vet.happiness == 60)
head = coach(role=SimpleNamespace(value="Head Coach"))
check("non-assistant hire returns None",
      ac.on_assistant_hired(htm, head) is None)
plain_line = ac.on_assistant_hired(htm, plain, app=FakeApp())
check("regular hire: quiet line, no icon tag",
      plain_line is not None and "icon" not in plain_line.lower())

# --- describe ---
print("--- describe ---")
desc = ac.describe_assistants(team_of(icon, plain))
check("icon tagged", any("FRANCHISE ICON" in l for l in desc), str(desc))
check("two lines", len(desc) == 2)

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
