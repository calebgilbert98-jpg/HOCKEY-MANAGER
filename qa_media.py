# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# qa_media.py — press-ecosystem checks: markets, reporters, interviews,
# narratives, fines, coach-media beefs. Rare drama by construction.

import random
import sys
import types
from datetime import date

sys.path.insert(0, ".")
from game_classes import Player, PlayerPosition
import media_engine as me

PASS, FAIL = [], []


def check(name, cond, info=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS: " if cond else "FAIL: ") + name +
          (f" -- {info}" if info and not cond else ""))


def make_player(age=26, overall_target=78, seed=1, pos=PlayerPosition.CENTER,
                **kw):
    random.seed(seed)
    p = Player(first_name="Test", last_name=f"P{seed}", age=age,
               primary_position=pos)
    p.nationality = "Canada"
    for a in ("skating", "shooting", "passing", "hockey_iq", "strength",
              "checking", "defense"):
        if hasattr(p, a):
            setattr(p, a, overall_target)
    for k, v in kw.items():
        if hasattr(p, k):
            setattr(p, k, v)
    p.overall_rating = lambda _o=overall_target: float(_o)
    return p


def make_coach(seed=1, controversy=40, control_need=50, name="Coach"):
    random.seed(9000 + seed)
    c = types.SimpleNamespace(
        id=seed, full_name=f"{name} C{seed}", last_name=f"C{seed}",
        role=types.SimpleNamespace(value="Head Coach"),
        controversy=controversy, control_need=control_need,
        media_stonewalls=0)
    return c


def make_team(name, roster, staff=None, wins=25, losses=25, ot_losses=6):
    return types.SimpleNamespace(team_name=name, roster=list(roster),
                                 staff=list(staff or []), wins=wins,
                                 losses=losses, ot_losses=ot_losses)


def make_league():
    lg = types.SimpleNamespace()
    me.ensure_media_state(lg)
    return lg


# --- 1. Markets ------------------------------------------------------------
tor = me.market_of("Toronto Maple Leafs")
uta = me.market_of("Utah Hockey Club")
mtl = me.market_of("Montréal Canadiens")
check("mkt: Toronto is a fishbowl", tor["intensity"] == 95, f"{tor}")
check("mkt: Utah is quiet", uta["intensity"] < 50, f"{uta}")
check("mkt: Montreal adversarial", mtl["adversarial"] >= 65, f"{mtl}")
check("mkt: unknown team -> sane default",
      me.market_of("Nope") == {"intensity": 55, "adversarial": 45,
                               "loyalty": 65, "patience": 65})

# --- 2. Reporters ----------------------------------------------------------
lg = make_league()
check("rep: 3 per market x 32", len(lg.reporters) == 96, len(lg.reporters))
tor_reps = me.reporters_for("Toronto Maple Leafs", lg)
archs = {r.archetype for r in tor_reps}
check("rep: every market has stirrer+loyalist+neutral", archs == {
      "stirrer", "loyalist", "neutral"}, archs)
check("rep: ids stable across ensure calls",
      len({r.id for r in lg.reporters}) == 96)
lg2 = types.SimpleNamespace()
me.ensure_media_state(lg2)
check("rep: names deterministic per market",
      [r.name for r in me.reporters_for("Toronto Maple Leafs", lg2)] ==
      [r.name for r in tor_reps])

# --- 3. Media savvy --------------------------------------------------------
vet = make_player(seed=11, composure=85, controversy=10, leadership=80,
                  nhl_games_played=600, pressure_player=80)
kid = make_player(seed=12, age=19, composure=40, controversy=55,
                  leadership=30, nhl_games_played=0, pressure_player=35)
check("savvy: composed vet >> rattled kid",
      me.media_savvy(vet) > me.media_savvy(kid) + 25,
      f"{me.media_savvy(vet):.1f} vs {me.media_savvy(kid):.1f}")
check("savvy: bounded 0-100", 0 <= me.media_savvy(kid) <= 100)

# --- 4. cover_game smoke ---------------------------------------------------
coach = make_coach()
home = make_team("Toronto Maple Leafs",
                 [make_player(seed=i, overall_target=70 + (i % 15))
                  for i in range(20)], staff=[coach])
away = make_team("Utah Hockey Club",
                 [make_player(seed=100 + i) for i in range(20)])
evs = me.cover_game(lg, home, away, home, away, (4, 2), False,
                    date(2026, 10, 5), rng=random.Random(1))
check("cover: returns event list, no crash", isinstance(evs, list))
check("cover: interview happened in Toronto",
      any(e["kind"] == "quote" for e in evs), f"{[e['kind'] for e in evs]}")

bare = types.SimpleNamespace()  # nothing on it
evs2 = me.cover_game(make_league(), bare, bare, bare, bare, (0, 0), False,
                     date(2026, 10, 5), rng=random.Random(2))
check("cover: bare-bones teams never crash", isinstance(evs2, list))

# Quiet markets often have no scrum at all.
quiet = make_team("Utah Hockey Club",
                  [make_player(seed=200 + i) for i in range(20)])
loud = make_team("Toronto Maple Leafs",
                 [make_player(seed=300 + i) for i in range(20)])
q_n = sum(1 for t in range(60)
          if me.cover_game(make_league(), quiet, loud, quiet, loud, (3, 2),
                           False, date(2026, 10, 5),
                           rng=random.Random(1000 + t)))
l_n = sum(1 for t in range(60)
          if me.cover_game(make_league(), loud, quiet, loud, quiet, (3, 2),
                           False, date(2026, 10, 5),
                           rng=random.Random(2000 + t)))
check("cover: Toronto covered far more often than Utah", l_n > q_n * 1.5,
      f"TOR={l_n} UTA={q_n}")

# --- 5. Hot-headed outburst (rare, gated) ----------------------------------
hothead = make_player(seed=21, controversy=85, composure=45)
hothead.nhl_games_played = 200
loser_team = make_team("Edmonton Oilers", [hothead] + [
    make_player(seed=400 + i, overall_target=60) for i in range(3)],
    wins=8, losses=20, ot_losses=2)  # spiraling
winner_team = make_team("Toronto Maple Leafs",
                        [make_player(seed=500 + i) for i in range(20)])
lg3 = make_league()
outs = fines = 0
for t in range(150):
    evs = me.cover_game(lg3, loser_team, winner_team, winner_team,
                        loser_team, (1, 6), False, date(2026, 10, 6),
                        rng=random.Random(3000 + t))
    for e in evs:
        if e["kind"] in ("fine", "outburst_room"):
            outs += 1
        if e["kind"] == "fine" and e.get("role", "player") == "player":
            fines += 1
check("drama: hot head in a blowout loss sometimes pops off",
      1 <= outs <= 60, f"outbursts in 200 games: {outs}")
check("drama: pop-offs can mean a real fine",
      fines >= 1 and all(f["amount"] in (2500, 5000)
                         for f in lg3.media_fines), f"fines={fines}")
check("drama: fine ledger records it",
      any("officiating" in f["reason"] for f in lg3.media_fines))

# The same situation with a composed pro: no outbursts.
pro = make_player(seed=22, controversy=15, composure=88)
pro.nhl_games_played = 500
calm_team = make_team("Edmonton Oilers", [pro] + [
    make_player(seed=600 + i) for i in range(19)],
    wins=8, losses=20, ot_losses=2)
outs_calm = 0
for t in range(120):
    # force the interview onto our composed pro every time
    lgx = make_league()
    lgx.media_recent_faces = [getattr(p, "id", None)
                              for p in calm_team.roster[1:]]
    evs = me.cover_game(lgx, calm_team, winner_team, winner_team,
                        calm_team, (1, 6), False, date(2026, 10, 6),
                        rng=random.Random(4000 + t))
    outs_calm += sum(1 for e in evs
                     if e["kind"] in ("fine", "outburst_room"))
check("drama: composed pro never pops off", outs_calm == 0,
      f"outbursts={outs_calm}")

# Outburst effects stay small.
p_mess = make_player(seed=23, controversy=85, composure=40)
p_mess.team_chemistry = 70
chem0 = p_mess.team_chemistry
mess_team = make_team("Philadelphia Flyers", [p_mess] + [
    make_player(seed=700 + i) for i in range(19)],
    wins=8, losses=20, ot_losses=2)
for t in range(60):
    lgm = make_league()
    lgm.media_recent_faces = [getattr(p, "id", None)
                              for p in mess_team.roster[1:]]
    me.cover_game(lgm, mess_team, winner_team, winner_team, mess_team,
                  (2, 5), False, date(2026, 10, 6),
                  rng=random.Random(5000 + t))
    if p_mess.team_chemistry < chem0:
        break
check("drama: room-callout costs at most 2 chemistry",
      chem0 - p_mess.team_chemistry <= 2,
      f"{chem0} -> {p_mess.team_chemistry}")

# --- 6. Tortorella: stonewall -> fine --------------------------------------
torts = make_coach(seed=31, controversy=92, control_need=95,
                   name="John Tortorella")
torts_team = make_team("Philadelphia Flyers",
                       [make_player(seed=800 + i) for i in range(20)],
                       staff=[torts])
lg4 = make_league()
stonewalled = coach_fined = 0
for t in range(40):
    evs = me.cover_game(lg4, torts_team, winner_team, winner_team,
                        torts_team, (2, 3), False, date(2026, 10, 7),
                        rng=random.Random(6000 + t))
    for e in evs:
        if e["kind"] == "quote" and "done here" in e.get("quote", ""):
            stonewalled += 1
        if e["kind"] == "fine" and e.get("role") == "coach":
            coach_fined += 1
            check("drama: coach media fine is $25k", e["amount"] == 25000,
                  f"{e['amount']}")
check("drama: prickly coach stonewalls sometimes", stonewalled >= 1,
      f"stonewalls={stonewalled}")
check("drama: third stonewall -> league fine", coach_fined >= 1,
      f"coach fines={coach_fined}")

# Easygoing coach: no stonewalls, no fines.
nice = make_coach(seed=32, controversy=20, control_need=25, name="Nice")
nice_team = make_team("Seattle Kraken",
                      [make_player(seed=900 + i) for i in range(20)],
                      staff=[nice])
lg5 = make_league()
nice_fines = 0
for t in range(60):
    evs = me.cover_game(lg5, nice_team, winner_team, nice_team,
                        winner_team, (4, 1), False, date(2026, 10, 7),
                        rng=random.Random(7000 + t))
    nice_fines += sum(1 for e in evs if e["kind"] == "fine"
                      and e.get("role") == "coach")
check("drama: easygoing coach never fined for media", nice_fines == 0)

# --- 7. Coach vs stirrer beef ----------------------------------------------
prickly = make_coach(seed=33, controversy=75, control_need=60,
                     name="Prickly")
beef_team = make_team("Toronto Maple Leafs",
                      [make_player(seed=950 + i) for i in range(20)],
                      staff=[prickly])
lg6 = make_league()
# Force stirrer interviews: only stirrers on this test league's Toronto beat.
lg6.reporters = [r for r in lg6.reporters
                 if not (r.market == "Toronto Maple Leafs"
                         and r.archetype != "stirrer")]
morale0 = None
for t in range(80):
    evs = me.cover_game(lg6, beef_team, winner_team, winner_team,
                        beef_team, (2, 4), False, date(2026, 10, 8),
                        rng=random.Random(8000 + t))
    if lg6.coach_media_beefs and morale0 is None:
        morale0 = [p.morale for p in beef_team.roster]
beefs = lg6.coach_media_beefs
check("drama: stirrer + prickly coach -> beef", len(beefs) >= 1,
      f"beefs={len(beefs)}")
if beefs:
    b = beefs[0]
    check("drama: beef escalates to full circus", b.level == 3,
          f"level={b.level}")
    check("drama: level-3 circus costs 1 morale, no more",
          all(m0 - p.morale <= 1
              for m0, p in zip(morale0, beef_team.roster)),
          "morale drop too big")

# --- 8. Narratives: spawn, poke, shutdown, decay ----------------------------
lg7 = make_league()
skid_team = make_team("Vancouver Canucks",
                      [make_player(seed=1000 + i) for i in range(20)],
                      staff=[make_coach(seed=41, name="Hotseat")],
                      wins=6, losses=22, ot_losses=2)
spawned = 0
max_narr = 0
max_canucks = 0
for t in range(120):
    evs = me.cover_game(lg7, skid_team, winner_team, winner_team,
                        skid_team, (1, 4), False, date(2026, 10, 9),
                        rng=random.Random(9000 + t))
    spawned += sum(1 for e in evs if e["kind"] == "narrative_spawn")
    max_narr = max(max_narr, len(lg7.media_narratives))
    max_canucks = max(max_canucks,
                      sum(1 for n in lg7.media_narratives
                          if n.team_name == "Vancouver Canucks"))
check("drama: spiraling team grows a narrative", spawned >= 1,
      f"spawns={spawned}")
check("drama: narratives capped league-wide",
      max_narr <= 6, max_narr)
check("drama: one storyline per team at a time",
      max_canucks <= 1, max_canucks)

# The Draisaitl: composed star kills it on camera.
star = make_player(seed=51, composure=90, controversy=20, leadership=75,
                   nhl_games_played=400, overall_target=92)
star_team = make_team("Edmonton Oilers", [star] + [
    make_player(seed=1100 + i) for i in range(19)],
    wins=6, losses=22, ot_losses=2)
lg8 = make_league()
lg8.media_narratives = [me.Narrative("leadership", "Edmonton Oilers",
                                     "Questions about the leadership in Edmonton",
                                     heat=60.0)]
stirrer = next(r for r in lg8.reporters
               if r.market == "Edmonton Oilers" and r.archetype == "stirrer")
cred0, appr0 = stirrer.credibility, stirrer.fan_approval
shut = 0
for t in range(40):
    lg8.media_recent_faces = [getattr(p, "id", None)
                              for p in star_team.roster[1:]]
    # force the stirrer: temporarily sideline the others
    keep = [r for r in lg8.reporters if r.market != "Edmonton Oilers"]
    lg8.reporters = keep + [stirrer]
    evs = me.cover_game(lg8, star_team, winner_team, winner_team,
                        star_team, (2, 5), False, date(2026, 10, 10),
                        rng=random.Random(10000 + t))
    shut += sum(1 for e in evs if e["kind"] == "shutdown")
    if not lg8.media_narratives:
        break
check("drama: composed star shuts the narrative down", shut >= 1,
      f"shutdowns={shut}")
check("drama: shutdown kills the narrative",
      not any(n.team_name == "Edmonton Oilers"
              for n in lg8.media_narratives))
check("drama: wrong reporter loses credibility + fan approval",
      stirrer.credibility < cred0 and stirrer.fan_approval < appr0,
      f"{cred0:.0f}->{stirrer.credibility:.0f} / "
      f"{appr0:.0f}->{stirrer.fan_approval:.0f}")

# Rattled kid fumbles it and the story grows.
rattled = make_player(seed=52, age=20, composure=35, controversy=40,
                      leadership=30, nhl_games_played=10)
rattled_team = make_team("Edmonton Oilers", [rattled] + [
    make_player(seed=1200 + i) for i in range(19)],
    wins=6, losses=22, ot_losses=2)
lg9 = make_league()
n0 = me.Narrative("leadership", "Edmonton Oilers",
                  "Questions about the leadership in Edmonton", heat=50.0)
lg9.media_narratives = [n0]
stirrer9 = next(r for r in lg9.reporters
                if r.market == "Edmonton Oilers" and r.archetype == "stirrer")
grew = False
for t in range(60):
    lg9.media_recent_faces = [getattr(p, "id", None)
                              for p in rattled_team.roster[1:]]
    keep = [r for r in lg9.reporters if r.market != "Edmonton Oilers"]
    lg9.reporters = keep + [stirrer9]
    me.cover_game(lg9, rattled_team, winner_team, winner_team,
                  rattled_team, (2, 5), False, date(2026, 10, 10),
                  rng=random.Random(11000 + t))
    if n0.heat > 55:
        grew = True
        break
check("drama: rattled kid fumbles -> story grows", grew,
      f"heat={n0.heat:.0f}")

# Daily tick: everything cools.
lg9b = make_league()
n = me.Narrative("hot_seat", "Toronto Maple Leafs", "Hot seat", heat=25.0)
lg9b.media_narratives = [n]
me.media_daily_tick(lg9b)
check("drama: narrative heat decays daily", n.heat == 15.0, n.heat)
for _ in range(3):
    me.media_daily_tick(lg9b)
check("drama: dead narratives are removed",
      len(lg9b.media_narratives) == 0)
b = me.CoachMediaBeef("C", "r", "R", "T")
lg9b.coach_media_beefs = [b]
for _ in range(7):
    me.media_daily_tick(lg9b)
check("drama: quiet beefs expire", len(lg9b.coach_media_beefs) == 0)

# --- 9. Rotation + routing -------------------------------------------------
lg10 = make_league()
rot_team = make_team("Toronto Maple Leafs",
                     [make_player(seed=1300 + i, overall_target=75)
                      for i in range(20)])
faces = set()
for t in range(8):
    me.cover_game(lg10, rot_team, away, rot_team, away, (3, 2), False,
                  date(2026, 10, 11), rng=random.Random(12000 + t))
    faces.add(lg10.media_recent_faces[-1] if lg10.media_recent_faces else None)
check("drama: different player every night", len(faces) >= 5,
      f"unique faces in 8 games: {len(faces)}")


class FakeApp:
    def __init__(self):
        self.news = []

    def add_news(self, line):
        self.news.append(line)


app = FakeApp()
n = me.route_events(app, [{"kind": "quote", "team": "Leafs", "player": "P",
                           "reporter": "R", "archetype": "neutral",
                           "outcome": "bland", "question": "Q?",
                           "quote": "A."},
                          {"kind": "narrative_spawn", "team": "Leafs",
                           "narrative": "Hot seat"}])
check("route: quotes + spawns -> news feed", n == 2 and len(app.news) == 2,
      app.news)
check("route: garbage never raises",
      me.route_events(FakeApp(), [{"kind": "bogus"}]) == 0)


# --- 10. Playoff context ---------------------------------------------------
print("--- playoff context + leadership ---")


def make_series(t1n, t2n, w1, w2, rnd="Division Semifinals"):
    return types.SimpleNamespace(
        team1=types.SimpleNamespace(team_name=t1n),
        team2=types.SimpleNamespace(team_name=t2n),
        team1_wins=w1, team2_wins=w2, games_played=w1 + w2,
        is_complete=False, round_name=rnd)


def make_po_league(t1n, t2n, w1, w2):
    lg = make_league()
    lg.playoff_bracket = types.SimpleNamespace(
        playoff_series={"division_semifinals":
                        [make_series(t1n, t2n, w1, w2)]})
    return lg


po_home = make_team("Toronto Maple Leafs",
                    [make_player(seed=2000 + i) for i in range(20)],
                    staff=[make_coach(seed=61, controversy=80,
                                      control_need=80)])
po_away = make_team("Boston Bruins",
                    [make_player(seed=2100 + i) for i in range(20)])

check("poctx: regular season -> None",
      me._playoff_context(make_league(), po_home, po_away) is None)
c = me._playoff_context(make_po_league("Toronto Maple Leafs",
                                       "Boston Bruins", 2, 2),
                        po_home, po_away)
check("poctx: 2-2 -> game 5, not elimination",
      c["game_number"] == 5 and not c["is_elimination"]
      and not c["is_game_7"], c)
c = me._playoff_context(make_po_league("Toronto Maple Leafs",
                                       "Boston Bruins", 3, 2),
                        po_home, po_away)
check("poctx: 3-2 -> elimination game 6",
      c["is_elimination"] and c["game_number"] == 6
      and not c["is_game_7"], c)
c = me._playoff_context(make_po_league("Toronto Maple Leafs",
                                       "Boston Bruins", 3, 3),
                        po_home, po_away)
check("poctx: 3-3 -> game 7", c["is_game_7"] and c["is_elimination"], c)

# Game 7: nothing spicy, ever. Brief respectful scrums or closed rooms.
bad = 0
bland_only = True
saw_events = 0
for t in range(60):
    lg = make_po_league("Toronto Maple Leafs", "Boston Bruins", 3, 3)
    evs = me.cover_game(lg, po_home, po_away, po_away, po_home, (1, 4),
                        False, date(2026, 5, 1),
                        rng=random.Random(20000 + t))
    saw_events += 1 if evs else 0
    for e in evs:
        if e["kind"] in ("fine", "beef", "shutdown", "narrative_poke",
                         "narrative_spawn", "defense", "shield"):
            bad += 1
        if e["kind"] == "quote" and e["outcome"] != "bland":
            bland_only = False
check("game7: no pokes/beefs/fines/outbursts/narratives", bad == 0,
      f"bad={bad}")
check("game7: quotes are respectful cliches only", bland_only)
check("game7: rooms sometimes just close", saw_events < 60,
      f"games with events: {saw_events}/60")

# Earlier playoff round: no narrative pokes, no new narratives.
pokes = spawns = 0
for t in range(40):
    lg = make_po_league("Toronto Maple Leafs", "Boston Bruins", 2, 2)
    lg.media_narratives = [me.Narrative("hot_seat", "Toronto Maple Leafs",
                                        "Hot seat", heat=70.0)]
    lg.reporters = [r for r in lg.reporters
                    if not (r.market == "Toronto Maple Leafs"
                            and r.archetype != "stirrer")]
    evs = me.cover_game(lg, po_home, po_away, po_away, po_home, (2, 3),
                        False, date(2026, 5, 1),
                        rng=random.Random(21000 + t))
    pokes += sum(1 for e in evs if e["kind"] == "narrative_poke")
    spawns += sum(1 for e in evs if e["kind"] == "narrative_spawn")
check("playoffs: stirrers don't poke narratives", pokes == 0)
check("playoffs: no new narratives spawned", spawns == 0)

# --- 11. Captain takes the bullet ------------------------------------------

def make_captain(seed, leadership=82, controversy=15, composure=80):
    c = make_player(seed=seed, leadership=leadership, composure=composure,
                    controversy=controversy, overall_target=85)
    c.role = types.SimpleNamespace(value="Captain")
    c.nhl_games_played = 700
    return c


cap = make_captain(2200)
cap_team = make_team("Toronto Maple Leafs", [cap] + [
    make_player(seed=2300 + i, overall_target=70) for i in range(19)])
for p in cap_team.roster:
    p.happiness = 60
    p.morale = 60
bullets = 0
for t in range(40):
    cap_team.media_moment_cd = {}  # isolate likelihood from cooldown
    lg = make_league()
    lg.media_narratives = [me.Narrative("leadership", "Toronto Maple Leafs",
                                        "Leadership questions", heat=50.0)]
    evs = me.cover_game(lg, cap_team, po_away, po_away, cap_team, (1, 5),
                        False, date(2026, 10, 12),
                        rng=random.Random(22000 + t))
    bullets += sum(1 for e in evs if e["kind"] == "defense")
check("leadership: captain takes the bullet after a loss", bullets >= 3,
      f"bullets={bullets}/40")
check("leadership: room happiness lifted",
      all(p.happiness > 60 for p in cap_team.roster))
check("leadership: narrative heat cooled by the stand",
      lg.media_narratives[0].heat < 50.0,
      f"heat={lg.media_narratives[0].heat:.0f}")
check("leadership: dynamics log records it",
      any(e["type"] == "leadership_stand"
          for e in cap_team.dynamics_log))

# Personality gradient: the saint captain stands up far more than the
# hothead leader wearing the C.
saint = make_captain(2210, leadership=95, controversy=5, composure=90)
hothead = make_captain(2211, leadership=78, controversy=70, composure=60)
saint_team = make_team("Toronto Maple Leafs", [saint] + [
    make_player(seed=2310 + i, overall_target=70) for i in range(19)])
hot_team = make_team("Toronto Maple Leafs", [hothead] + [
    make_player(seed=2320 + i, overall_target=70) for i in range(19)])
check("personality: saint captain >> hothead leader on bullets",
      me._bullet_likelihood(saint, saint_team, True) >
      me._bullet_likelihood(hothead, hot_team, True) + 0.20,
      f"{me._bullet_likelihood(saint, saint_team, True):.2f} vs "
      f"{me._bullet_likelihood(hothead, hot_team, True):.2f}")
sb = hb = 0
for t in range(60):
    for tm, acc in ((saint_team, "s"), (hot_team, "h")):
        tm.media_moment_cd = {}
        lg = make_league()
        evs = me.cover_game(lg, tm, po_away, po_away, tm, (1, 5), False,
                            date(2026, 10, 12),
                            rng=random.Random(33000 + t))
        n = sum(1 for e in evs if e["kind"] == "defense")
        if acc == "s":
            sb += n
        else:
            hb += n
check("personality: saint stands up more often in games", sb > hb + 8,
      f"saint={sb} hothead={hb} /60")

# Cooldown: one stand-up buys ~8 quiet games, even for a saint.
cd_team = make_team("Toronto Maple Leafs", [make_captain(2230)] + [
    make_player(seed=2340 + i, overall_target=70) for i in range(19)])
cdb = 0
for t in range(40):
    lg = make_league()
    evs = me.cover_game(lg, cd_team, po_away, po_away, cd_team, (1, 5),
                        False, date(2026, 10, 12),
                        rng=random.Random(34000 + t))
    cdb += sum(1 for e in evs if e["kind"] == "defense")
check("cadence: bullet has a cooldown, not every loss", 1 <= cdb <= 6,
      f"bullets={cdb}/40")

# Non-leader interviewed after a loss: no bullet-taking.
quiet = make_player(seed=2400, leadership=40, composure=80, controversy=15,
                    overall_target=85)
quiet.nhl_games_played = 700
quiet_team = make_team("Toronto Maple Leafs", [quiet] + [
    make_player(seed=2500 + i, overall_target=60) for i in range(19)])
nb = 0
for t in range(30):
    lg = make_league()
    lg.media_recent_faces = []  # fresh
    evs = me.cover_game(lg, quiet_team, po_away, po_away, quiet_team,
                        (1, 5), False, date(2026, 10, 12),
                        rng=random.Random(23000 + t))
    nb += sum(1 for e in evs if e["kind"] == "defense")
check("leadership: non-leaders don't take bullets", nb == 0, f"nb={nb}")

# --- 12. Coach shields his guy ----------------------------------------------
kid = make_player(seed=2600, age=20, composure=45, controversy=25,
                  leadership=30, overall_target=90)
kid.nhl_games_played = 30
kid.morale = 60
shield_coach = make_coach(seed=62, controversy=30, control_need=40,
                          name="Protector")
shield_coach.man_management = 75
shield_team = make_team("Toronto Maple Leafs", [kid] + [
    make_player(seed=2700 + i, overall_target=60) for i in range(19)],
    staff=[shield_coach])
shields = 0
lg = make_league()
lg.media_narratives = [me.Narrative("leadership", "Toronto Maple Leafs",
                                    "Leadership questions", heat=60.0)]
lg.reporters = [r for r in lg.reporters
                if not (r.market == "Toronto Maple Leafs"
                        and r.archetype != "stirrer")]
for t in range(40):
    shield_team.media_moment_cd = {}
    lg.media_recent_faces = [getattr(p, "id", None)
                             for p in shield_team.roster[1:]]
    evs = me.cover_game(lg, shield_team, po_away, po_away, shield_team,
                        (2, 4), False, date(2026, 10, 13),
                        rng=random.Random(24000 + t))
    shields += sum(1 for e in evs if e["kind"] == "shield")
check("leadership: good coach shields the kid", shields >= 2,
      f"shields={shields}/40")
check("leadership: shield cools the narrative + lifts the kid",
      lg.media_narratives[0].heat < 60.0 and kid.morale > 60,
      f"heat={lg.media_narratives[0].heat:.0f} morale={kid.morale}")

# Personality gradient on the shield, deterministic.
hi_coach = make_coach(seed=64, name="Hi")
hi_coach.man_management = 85
hi_coach.leadership = 70
lo_coach = make_coach(seed=65, name="Lo")
lo_coach.man_management = 35
lo_coach.leadership = 45
veteran = make_player(seed=2601, age=30, overall_target=85)
check("personality: players'-coach shields far more than the cold one",
      me._shield_likelihood(hi_coach, kid) >
      me._shield_likelihood(lo_coach, kid) + 0.20,
      f"{me._shield_likelihood(hi_coach, kid):.2f} vs "
      f"{me._shield_likelihood(lo_coach, kid):.2f}")
check("personality: kids get covered more than veterans",
      me._shield_likelihood(hi_coach, kid) >
      me._shield_likelihood(hi_coach, veteran) + 0.10)

# --- 13. GM public backing ---------------------------------------------------
glg = make_league()
gcoach = make_coach(seed=63, name="Hotseat")
gcoach.gm_trust = 70
gteam = make_team("Toronto Maple Leafs",
                  [make_player(seed=2800 + i) for i in range(10)],
                  staff=[gcoach])
glg.media_narratives = [me.Narrative("hot_seat", "Toronto Maple Leafs",
                                     "Coach on hot seat", heat=60.0)]
res = me.gm_public_backing(glg, gteam, "coach", date(2026, 10, 14),
                           random.Random(1))
check("gm: backing the coach cools hot seat -20",
      glg.media_narratives[0].heat == 40.0)
check("gm: coach feels the trust +3", gcoach.gm_trust == 73)
check("gm: backing event well-formed",
      res["event"]["kind"] == "backing" and "quote" in res)

plg = make_league()
tp = make_player(seed=2900, overall_target=88)
tp.morale = 55
pid = getattr(tp, "id", "x")
pteam = make_team("Toronto Maple Leafs", [tp] + [
    make_player(seed=3000 + i) for i in range(9)])
plg.media_narratives = [me.Narrative("trade_rumor", "Toronto Maple Leafs",
                                     "Trade chatter", heat=50.0,
                                     subjects=[pid])]
res = me.gm_public_backing(plg, pteam, tp, date(2026, 10, 14),
                           random.Random(1))
check("gm: backing the player cools rumor + lifts him",
      plg.media_narratives[0].heat == 35.0 and tp.morale == 57)

# Personality: steady GMs go on the record, volatile ones let guys twist.
steady_gm = types.SimpleNamespace(controversy=15)
wild_gm = types.SimpleNamespace(controversy=85)
hot = me.Narrative("hot_seat", "Toronto Maple Leafs", "Hot seat",
                   heat=80.0)
check("personality: steady GM backs far more than the volatile one",
      me._gm_backing_likelihood(steady_gm, hot) >
      me._gm_backing_likelihood(wild_gm, None) * 3,
      f"{me._gm_backing_likelihood(steady_gm, hot):.3f} vs "
      f"{me._gm_backing_likelihood(wild_gm, None):.3f}")

# User-triggered, no league at all: never crashes.
res = me.gm_public_backing(None, pteam, "room", user_triggered=True)
check("gm: user backing the room works standalone",
      res["ok"] and all(p.happiness > 0 for p in pteam.roster))

# --- 14. Intermission rally --------------------------------------------------
rally = 0
for t in range(40):
    cap_team.media_moment_cd = {}
    lg = make_league()
    evs = me.cover_game(lg, cap_team, po_away, cap_team, po_away, (3, 2),
                        False, date(2026, 10, 15),
                        rng=random.Random(25000 + t))
    rally += sum(1 for e in evs if e["kind"] == "rally")
check("leadership: intermission rally fires in tight games", rally >= 3,
      f"rallies={rally}/40")

# Personality: the voice matters -- saint captain outranks a flat coach,
# a great motivator outranks a weak captain, nobody means silence.
flat_coach = make_coach(seed=66, name="Flat")
flat_coach.motivating = 55
voice_team = make_team("Toronto Maple Leafs", [saint] + [
    make_player(seed=3100 + i, overall_target=70) for i in range(19)],
    staff=[flat_coach])
spk, _ = me._rally_speaker(voice_team)
check("personality: saint captain is the room's voice",
      spk is saint)
mot_coach = make_coach(seed=67, name="Mot")
mot_coach.motivating = 92
weak_cap = make_captain(2240, leadership=50)
weak_team = make_team("Toronto Maple Leafs", [weak_cap] + [
    make_player(seed=3200 + i, overall_target=70) for i in range(19)],
    staff=[mot_coach])
spk2, _ = me._rally_speaker(weak_team)
check("personality: great motivator outranks a weak captain",
      spk2 is mot_coach)
silent_cap = make_captain(2241, leadership=40)
mute_coach = make_coach(seed=68, name="Mute")
mute_coach.motivating = 50
quiet_team2 = make_team("Toronto Maple Leafs", [silent_cap] + [
    make_player(seed=3300 + i, overall_target=70) for i in range(19)],
    staff=[mute_coach])
spk3, _ = me._rally_speaker(quiet_team2)
check("personality: no voice, no speech", spk3 is None)
check("personality: better voice rallies more",
      me._rally_likelihood(0.95, False, 70) >
      me._rally_likelihood(0.60, False, 70) + 0.10)

rally_blow = 0
for t in range(30):
    lg = make_league()
    evs = me.cover_game(lg, cap_team, po_away, cap_team, po_away, (7, 1),
                        False, date(2026, 10, 15),
                        rng=random.Random(26000 + t))
    rally_blow += sum(1 for e in evs if e["kind"] == "rally")
check("leadership: no speeches in blowouts", rally_blow == 0)

rally_g7 = 0
for t in range(30):
    lg = make_po_league("Toronto Maple Leafs", "Boston Bruins", 3, 3)
    evs = me.cover_game(lg, cap_team, po_away, cap_team, po_away, (3, 2),
                        True, date(2026, 5, 2),
                        rng=random.Random(27000 + t))
    rally_g7 += sum(1 for e in evs if e["kind"] == "rally")
check("leadership: no speeches needed in game 7", rally_g7 == 0)

# --- 15. Key moments + cadence ------------------------------------------------
plain_lg = make_league()
base = me._key_moment_boost(plain_lg, cap_team, po_away, date(2026, 10, 5))
check("cadence: random October Tuesday is 1.0x", base == 1.0, base)
march = me._key_moment_boost(plain_lg, cap_team, po_away, date(2026, 3, 10))
check("cadence: March push matters", march == 1.25, march)
rival_lg = make_league()
rival_lg.rivalries = [{"a": ("team", "Boston Bruins"),
                       "b": ("team", "Toronto Maple Leafs"),
                       "a_name": "Boston Bruins",
                       "b_name": "Toronto Maple Leafs",
                       "kind": "team_team", "intensity": 70}]
rb = me._key_moment_boost(rival_lg, cap_team, po_away, date(2026, 10, 5))
check("cadence: blood rivalry matters", rb == 1.4, rb)
skid = make_team("Toronto Maple Leafs",
                 [make_player(seed=3400 + i) for i in range(20)],
                 wins=6, losses=22, ot_losses=2)
skb = me._key_moment_boost(plain_lg, skid, po_away, date(2026, 10, 5))
check("cadence: spiraling room matters", skb == 1.3, skb)
story_lg = make_league()
story_lg.media_narratives = [me.Narrative("hot_seat",
                                          "Toronto Maple Leafs",
                                          "Hot seat", heat=60.0)]
stb = me._key_moment_boost(story_lg, cap_team, po_away, date(2026, 10, 5))
check("cadence: active storyline matters", stb == 1.3, stb)
combo = me._key_moment_boost(rival_lg, skid, po_away, date(2026, 3, 10))
check("cadence: combined moments cap at 2.0x", combo == 2.0, combo)

# Cooldown mechanics on the clock.
t0 = make_team("X", [make_player(seed=1)])
check("cadence: moment ready when never fired",
      me._moment_ready(t0, "bullet"))
me._mark_moment(t0, "bullet")
check("cadence: not ready right after firing",
      not me._moment_ready(t0, "bullet"))
t0.media_games_covered = 8
check("cadence: ready again after 8 games",
      me._moment_ready(t0, "bullet"))


print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
