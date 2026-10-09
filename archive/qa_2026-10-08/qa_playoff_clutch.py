# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: playoff clutch reputation ("Mr. Game 7" / "Playoff Performer").

Covers:
  (a) thresholds grant tags -- game-7 stars count toward Mr. Game 7,
      ordinary playoff stars toward Playoff Performer, tracked separately;
  (b) no tag below threshold;
  (c) tags + counters survive a save/load round-trip;
  (d) playoff stories mention the tag when the tagged player is the
      subject (cup recap, series storylines, game-story headline,
      story specs) and read normally when he has none;
  (e) no-stars / non-playoff baseline unaffected;
  (+) grant idempotency: no duplicates, no re-grant spam.

Deterministic: random.seed() pinned before any generation.
"""

import random
random.seed(20260929)

from types import SimpleNamespace

from game_classes import Player, PlayerPosition
from stars import record_game_stars
from clutch import (PLAYOFF_PERFORMER_STARS, MR_GAME_7_STARS,
                    PLAYOFF_PERFORMER_TAG, MR_GAME_7_TAG,
                    maybe_grant_clutch_tags, clutch_epithet, clutch_tags,
                    playoff_star_count, game7_star_count, tag_label)

PASS = 0
FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}")


def mk_player(first, last):
    return Player(first, last, 27, PlayerPosition.CENTER)


def mk_team(name, roster):
    return SimpleNamespace(team_name=name, roster=list(roster))


def star_game(hero, home, away, playoff=False, game7=False):
    """One game where `hero` is the 1st star (hat trick)."""
    gr = {
        "game_stats": {hero.id: {"player": hero, "g": 3, "a": 0,
                                 "saves": 0}},
        "home_score": 4, "away_score": 2, "winner": home,
        "notable_events": [],
    }
    stars = record_game_stars(gr, home, away, preseason=False,
                             game_date="2027-05-01",
                             playoff=playoff, game7=game7)
    return gr, stars


print("== (a) thresholds grant tags, tracked separately ==")
a = mk_player("Clutch", "Hero")
home = mk_team("Home Club", [a])
away = mk_team("Away Club", [mk_player("Depth", "Guy")])
last_gr = None
for _ in range(MR_GAME_7_STARS):
    last_gr, _ = star_game(a, home, away, playoff=True, game7=True)
check("game-7 stars counted separately", game7_star_count(a) == MR_GAME_7_STARS)
check("game-7 stars also count as playoff stars",
      playoff_star_count(a) == MR_GAME_7_STARS)
check("Mr. Game 7 tag granted", MR_GAME_7_TAG in clutch_tags(a))
check("grant stamped on the game result",
      any(g.get("tag") == MR_GAME_7_TAG
          for g in last_gr.get("clutch_tags_granted", [])))
check("epithet resolves", clutch_epithet(a) == "Mr. Game 7")

b = mk_player("Steady", "Eddy")
home2 = mk_team("Home Club", [b])
away2 = mk_team("Away Club", [mk_player("Depth", "Guy")])
for _ in range(PLAYOFF_PERFORMER_STARS):
    star_game(b, home2, away2, playoff=True, game7=False)
check("ordinary playoff stars counted", playoff_star_count(b) == PLAYOFF_PERFORMER_STARS)
check("game-7 counter stays zero", game7_star_count(b) == 0)
check("Playoff Performer tag granted",
      PLAYOFF_PERFORMER_TAG in clutch_tags(b))
check("no Mr. Game 7 without game-7 stars",
      MR_GAME_7_TAG not in clutch_tags(b))
check("epithet resolves", clutch_epithet(b) == "Playoff Performer")

print("== (b) no tag below threshold ==")
c = mk_player("Almost", "There")
home3 = mk_team("Home Club", [c])
away3 = mk_team("Away Club", [mk_player("Depth", "Guy")])
for _ in range(MR_GAME_7_STARS - 1):
    star_game(c, home3, away3, playoff=True, game7=True)
for _ in range(PLAYOFF_PERFORMER_STARS - 1 - (MR_GAME_7_STARS - 1)):
    star_game(c, home3, away3, playoff=True, game7=False)
check("below both thresholds: no tags", clutch_tags(c) == [])
check("below threshold: epithet empty", clutch_epithet(c) == "")

print("== (+) grant idempotency ==")
before = list(clutch_tags(a))
again = maybe_grant_clutch_tags(a)
check("re-grant returns nothing new", again == [])
check("no duplicate tags", clutch_tags(a) == before
      and len(clutch_tags(a)) == len(set(clutch_tags(a))))
star_game(a, home, away, playoff=True, game7=True)  # one more star
check("extra star does not duplicate the tag",
      clutch_tags(a).count(MR_GAME_7_TAG) == 1)

print("== (c) save/load round-trip ==")
from save_load_system import GameSaveManager
_mgr = GameSaveManager(None)  # _serialize/_restore_player need no manager
data = _mgr._serialize_player(a)
restored = _mgr._restore_player(dict(data))
check("restore succeeded", restored is not None)
check("tags survive", clutch_tags(restored) == clutch_tags(a))
check("playoff_stars survives",
      playoff_star_count(restored) == playoff_star_count(a))
check("game7_stars survives", game7_star_count(restored) == game7_star_count(a))
# Old-save shape: fields missing entirely -> defaults, no crash.
old_shape = {k: v for k, v in data.items()
             if k not in ("playoff_stars", "game7_stars", "clutch_tags")}
restored_old = _mgr._restore_player(dict(old_shape))
check("old save restores", restored_old is not None)
check("old save: zero counters", playoff_star_count(restored_old) == 0
      and game7_star_count(restored_old) == 0)
check("old save: no tags", clutch_tags(restored_old) == [])

print("== (d) stories mention the tag ==")
from immortality import build_cup_recap


def _ps(g, a, gp):
    return SimpleNamespace(goals=g, assists=a, games_played=gp)


smythe = mk_player("Conn", "Smythe")
smythe.playoff_stats = _ps(12, 14, 24)
smythe.career_games = 900
smythe.age = 31
smythe.career_accolades = []
smythe.career_points = 800
mate = mk_player("Hero", "Two")
mate.playoff_stats = _ps(9, 11, 24)
mate.career_games = 700
mate.age = 29
mate.career_accolades = []
mate.career_points = 600
# Tag the Smythe winner like a real Mr. Game 7.
for _ in range(MR_GAME_7_STARS):
    smythe.game7_stars += 1
    smythe.playoff_stars += 1
maybe_grant_clutch_tags(smythe)
champ = SimpleNamespace(team_name="Champ Club", roster=[smythe, mate],
                        head_coach=None)
opp = SimpleNamespace(team_name="Opp Club", roster=[])
series = SimpleNamespace(team1=champ, team2=opp, winner=champ,
                         team1_wins=4, team2_wins=3)
bracket = SimpleNamespace(
    playoff_series={"stanley_cup_final": [series]},
    conn_smythe_winner=smythe, conn_smythe_name=None)
league = SimpleNamespace(season_year=2026)
recap = build_cup_recap(champ, bracket, league)
check("cup recap names the tag on the Smythe winner",
      '"Mr. Game 7"' in recap and "Conn Smythe" in recap)
# Untagged Smythe: normal copy, no tag text.
plain = mk_player("Plain", "Winner")
plain.playoff_stats = _ps(10, 10, 24)
plain.career_games = 800
plain.age = 30
plain.career_accolades = []
plain.career_points = 700
champ2 = SimpleNamespace(team_name="Champ Club", roster=[plain, mate],
                         head_coach=None)
series2 = SimpleNamespace(team1=champ2, team2=opp, winner=champ2,
                          team1_wins=4, team2_wins=1)
bracket2 = SimpleNamespace(
    playoff_series={"stanley_cup_final": [series2]},
    conn_smythe_winner=plain, conn_smythe_name=None)
recap2 = build_cup_recap(champ2, bracket2, league)
check("cup recap reads normally for untagged winner",
      "Conn Smythe winner" in recap2
      and "Mr. Game 7" not in recap2 and "Playoff Performer" not in recap2)

# Series storylines: looming Game 7 with a tagged skater on a roster.
from playoff_system import _series_storylines
g7series = SimpleNamespace(
    team1=mk_team("AAA", [a]), team2=mk_team("BBB", [mk_player("No", "Tag")]),
    team1_wins=3, team2_wins=3, games_played=6, is_complete=False,
    winner=None,
    game_results=[{"team1_won": True}, {"team1_won": False},
                  {"team1_won": True}, {"team1_won": False},
                  {"team1_won": True}, {"team1_won": False}])
sl = _series_storylines(g7series)
check("storylines name the tag before Game 7",
      any("Mr. Game 7" in ln for ln in sl))
check("storylines still carry the decider line",
      any("Game 7 will decide it" in ln for ln in sl))
# No tagged players: no tag line, normal copy.
g7plain = SimpleNamespace(
    team1=mk_team("AAA", [mk_player("No", "Tag")]),
    team2=mk_team("BBB", [mk_player("Nope", "None")]),
    team1_wins=3, team2_wins=3, games_played=6, is_complete=False,
    winner=None,
    game_results=[{"team1_won": True}, {"team1_won": False},
                  {"team1_won": True}, {"team1_won": False},
                  {"team1_won": True}, {"team1_won": False}])
sl2 = _series_storylines(g7plain)
check("storylines read normally with no tagged players",
      any("Game 7 will decide it" in ln for ln in sl2)
      and not any("Mr. Game 7" in ln or "Playoff Performer" in ln
                  for ln in sl2))

# Game-story headline: epithet colors the email; empty epithet is normal.
from headlines import make_headline
from datetime import date
msg = make_headline("game_story", date(2027, 5, 20), story_kind="hat_trick",
                    text="Clutch Hero (Champ Club) scored 3 in a 4-2 win.",
                    home="Champ Club", away="Opp Club", epithet="Mr. Game 7")
check("headline built", msg is not None)
check("headline references the tag",
      msg is not None and "Mr. Game 7" in msg.content)
msg2 = make_headline("game_story", date(2027, 5, 20), story_kind="hat_trick",
                     text="Plain Winner (Champ Club) scored 3 in a 4-2 win.",
                     home="Champ Club", away="Opp Club")
check("headline normal without epithet",
      msg2 is not None and "Mr. Game 7" not in msg2.content
      and "Some nights are bigger than the score." in msg2.content)

# Story specs: a tagged subject's epithet travels on the spec (not the
# ledger text).
import narrative_incidents as ni


class _Ledger:
    def __init__(self):
        self.texts = []

    def record(self, kind, teams=None, weight=0, facts=None, text=""):
        self.texts.append(text)


class _StubSim:
    def __init__(self, stats):
        self.stats = stats


tagged = mk_player("Tag", "Ged")
for _ in range(MR_GAME_7_STARS):
    tagged.game7_stars += 1
    tagged.playoff_stars += 1
maybe_grant_clutch_tags(tagged)
t_home = mk_team("Home Club", [tagged])
t_away = mk_team("Away Club", [mk_player("Other", "Guy")])
sim = _StubSim({"Home Club": {tagged.id: {"goals": 3, "assists": 0,
                                          "saves": 0}}})
led = _Ledger()
specs = ni.record_stories(t_home, t_away, 4, 2, False, False, sim, [], led)
ht = [s for s in specs if s.get("kind") == "hat_trick"]
check("hat-trick story produced", len(ht) == 1)
check("spec carries the epithet",
      ht and ht[0].get("epithet") == "Mr. Game 7")
check("ledger text stays clean",
      led.texts and "Mr. Game 7" not in led.texts[0])

# The Game-7 OT hero resolver: prefers the real OT scorer, falls back to
# the 1st star; tagged hero reads with the tag.
from playoff_system import _game7_ot_hero
from stars import _ot_scorer_id
otp = mk_player("Otee", "Winner")
for _ in range(MR_GAME_7_STARS):
    otp.game7_stars += 1
    otp.playoff_stars += 1
maybe_grant_clutch_tags(otp)
t1 = mk_team("Home Club", [otp])
t2 = mk_team("Away Club", [mk_player("Other", "Guy")])
pgr = {
    "notable_events": [{"event": "Goal", "period": 4,
                        "player": SimpleNamespace(id=otp.id)}],
    "three_stars": [{"player_id": otp.id, "rank": 1}],
}
hero = _game7_ot_hero(pgr, t1, t2)
check("OT hero resolves", hero is not None and hero[0] is otp)
check("OT hero carries the tag",
      hero is not None and __import__("clutch").clutch_epithet(hero[0])
      == "Mr. Game 7")
pgr2 = {"notable_events": [],
        "three_stars": [{"player_id": otp.id, "rank": 1}]}
hero2 = _game7_ot_hero(pgr2, t1, t2)
check("falls back to 1st star", hero2 is not None and hero2[0] is otp)
hero3 = _game7_ot_hero({"notable_events": [], "three_stars": []}, t1, t2)
check("no hero -> None", hero3 is None)

print("== (e) baselines unaffected ==")
z = mk_player("Zero", "Stars")
hz = mk_team("Home Club", [z])
az = mk_team("Away Club", [mk_player("Depth", "Guy")])
gr0 = {"game_stats": {}, "home_score": 2, "away_score": 1, "winner": hz,
       "notable_events": []}
out0 = record_game_stars(gr0, hz, az, preseason=False, playoff=True,
                         game7=True)
check("empty game_stats -> no stars", out0 == [])
check("no counters bumped", playoff_star_count(z) == 0
      and game7_star_count(z) == 0)
check("no grant key stamped", "clutch_tags_granted" not in gr0)
check("no tags", clutch_tags(z) == [])
# Regular-season stars never touch playoff counters.
gr1, _ = star_game(z, hz, az, playoff=False)
check("regular-season star: playoff counters untouched",
      playoff_star_count(z) == 0 and game7_star_count(z) == 0)
check("season game_stars still bumped",
      (getattr(z, "game_stars", None) or {}).get("first") == 1)

print(f"\nRESULT: {PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
