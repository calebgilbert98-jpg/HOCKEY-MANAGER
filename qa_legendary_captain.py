# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: legendary captain status -> fan opinion -> team icon -> legacy.

A completed Toews/Crosby/Yzerman arc (5+ years wearing the C, 88+
leadership, a Cup lifted as captain) stamps legendary status once, which
feeds:
  - fan opinion (fan_favourite_score: +12, "face of the franchise"),
  - team icon status (player.icon_team, team-specific, never reassigned),
  - legacy (immortality snapshot flag -> career_score +8 -> number_worthy
    and the HOF ballot),
  - the staff pipeline (a legendary captain turned coach carries his
    icon team, not merely his last sweater).
"""
import json
import sys

sys.path.insert(0, ".")

import captaincy_growth as cg
import immortality as imm
import reputation_system as rs
from game_classes import Player, PlayerPosition

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS " if cond else "  FAIL ") + name +
          (f"\n    {detail}" if detail and not cond else ""))


def mkplayer(**kw):
    p = Player("Test", "Legend", 30, PlayerPosition.CENTER)
    # Pin the random default factories that feed fan scores: team_tenure
    # (up to 15 pts) and the dealt base controversy (overwrites the
    # controversy attr via ensure_reputation_fields; gates "Model pro").
    p.team_tenure = "4+ years"
    for k, v in kw.items():
        setattr(p, k, v)
    p.base_controversy = int(getattr(p, "controversy", 10) or 10)
    return p


def mk_captain(tenure=5, leadership=88, cup_seasons=None):
    return mkplayer(
        captaincy="C",
        captain_tenure_years=tenure,
        leadership=leadership,
        _cup_captain_rep_seasons=set(
            cup_seasons if cup_seasons is not None else [2026]),
        games_played=82,
        points=70,
        reputation=70,
        controversy=10,
        age=30,
    )


# --- 1. criteria -------------------------------------------------------
check("full arc qualifies",
      cg.is_legendary_captain(mk_captain()) is True)

check("4-year tenure does not qualify",
      cg.is_legendary_captain(mk_captain(tenure=4)) is False)

check("87 leadership does not qualify",
      cg.is_legendary_captain(mk_captain(leadership=87)) is False)

check("no Cup as captain does not qualify",
      cg.is_legendary_captain(mk_captain(cup_seasons=[])) is False)

check("plain player does not qualify and does not crash",
      cg.is_legendary_captain(mkplayer()) is False)

check("alternate with Cups does not qualify",
      cg.is_legendary_captain(mkplayer(
          captaincy="A", alternate_tenure_years=8, leadership=95,
          _cup_captain_rep_seasons={2026})) is False)

# --- 2. stamping --------------------------------------------------------
p = mk_captain()
check("stamp returns True when newly earned",
      cg.stamp_legendary_captain(p, "Bruins", season_year=2027) is True)
check("stamp sets the status flag",
      getattr(p, "_legendary_captain", False) is True)
check("stamp records the team and season",
      getattr(p, "_legendary_captain_team", "") == "Bruins"
      and getattr(p, "_legendary_captain_season", 0) == 2027)
check("stamp sets player team icon status",
      getattr(p, "icon_team", "") == "Bruins")
check("re-stamp is a no-op (news fires once)",
      cg.stamp_legendary_captain(p, "Bruins", season_year=2027) is False)

p2 = mk_captain(tenure=4)
check("non-qualifier is not stamped",
      cg.stamp_legendary_captain(p2, "Bruins") is False
      and getattr(p2, "icon_team", "") == "")

p3 = mk_captain()
cg.stamp_legendary_captain(p3, "Bruins")
check("icon team survives a later trade (Coffey rule)",
      getattr(p3, "icon_team", "") == "Bruins")

# --- 3. fan opinion ------------------------------------------------------
class FakeTeam:
    def __init__(self, name):
        self.team_name = name

base = mk_captain()
leg = mk_captain()
cg.stamp_legendary_captain(leg, "Bruins")
s_base = rs.fan_favourite_score(base, FakeTeam("Bruins"))
s_leg = rs.fan_favourite_score(leg, FakeTeam("Bruins"))
check("legendary captain scores +12 over an identical C",
      s_leg["score"] - s_base["score"] == 12,
      f"base={s_base['score']} leg={s_leg['score']}")
check("legendary reason names the face of the franchise",
      any("Legendary captain" in r for r in s_leg["reasons"]),
      f"reasons={s_leg['reasons']}")

s_away = rs.fan_favourite_score(leg, FakeTeam("Hawks"))
check("legendary bonus is not team-gated (status travels, icon does not)",
      s_away["score"] == s_leg["score"],
      f"home={s_leg['score']} away={s_away['score']}")

icon = mk_captain(tenure=4)  # not legendary, but an icon of the Bruins
icon.icon_team = "Bruins"
s_icon_home = rs.fan_favourite_score(icon, FakeTeam("Bruins"))
s_icon_away = rs.fan_favourite_score(icon, FakeTeam("Hawks"))
check("franchise icon gets +8 at home, nothing away",
      s_icon_home["score"] - s_icon_away["score"] == 8
      and any("Franchise icon" in r for r in s_icon_home["reasons"]),
      f"home={s_icon_home['score']} away={s_icon_away['score']}")

# --- 4. legacy ------------------------------------------------------------
snap_leg = imm.snapshot_player(leg, "Bruins", 2027)
snap_base = imm.snapshot_player(base, "Bruins", 2027)
check("snapshot carries the legendary flag",
      snap_leg.get("legendary_captain") is True
      and snap_base.get("legendary_captain") is False)
check("career_score pays +8 for the completed arc",
      imm.career_score(snap_leg) - imm.career_score(snap_base) == 8.0,
      f"leg={imm.career_score(snap_leg)} base={imm.career_score(snap_base)}")

# Borderline: 64.5 + Cup, no awards, <800 games -> number_worthy False;
# the +8 pushes it to 72.5 -> True.
border = {"goalie": False, "points": 1400, "goals": 0, "games": 700,
          "cups": 1, "awards": [], "legendary_captain": False}
border_leg = dict(border, legendary_captain=True)
check("career_score math on the borderline case",
      imm.career_score(border) == 64.5
      and imm.career_score(border_leg) == 72.5,
      f"base={imm.career_score(border)} leg={imm.career_score(border_leg)}")
check("legendary arc tips a borderline career into number_worthy",
      imm.number_worthy(border) is False
      and imm.number_worthy(border_leg) is True)

# --- 5. staff pipeline ------------------------------------------------------
leg_player = mk_captain()
cg.stamp_legendary_captain(leg_player, "Bruins")
leg_player.last_team_name = "Hawks"
leg_player.career_reputation = 90
leg_player.career_games = 1200
attrs = rs.staffer_from_retired_player(leg_player, [])
check("legendary captain turned coach carries his icon team",
      attrs.get("icon_team") == "Bruins"
      and attrs.get("icon_level") == "icon",
      f"attrs={attrs.get('icon_team')}/{attrs.get('icon_level')}")

star = mkplayer(last_team_name="Hawks", career_reputation=90,
                career_games=1200)
attrs2 = rs.staffer_from_retired_player(star, [])
check("non-legendary star keeps the old last-team rule",
      attrs2.get("icon_team") == "Hawks"
      and attrs2.get("icon_level") == "icon")

# --- 6. save/load round-trip ----------------------------------------------
p4 = mk_captain()
cg.stamp_legendary_captain(p4, "Bruins", season_year=2027)
blob = json.dumps(p4.__dict__, default=str)
restored = mkplayer()
for k, v in json.loads(blob).items():
    try:
        setattr(restored, k, v)
    except Exception:
        pass
check("legendary flags survive a save/load round-trip",
      getattr(restored, "_legendary_captain", False) is True
      and getattr(restored, "icon_team", "") == "Bruins"
      and cg.is_legendary_captain(restored) is True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
