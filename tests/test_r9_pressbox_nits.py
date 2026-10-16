#!/usr/bin/env python3
"""R9: Press Box correctness nits (S item).

Three nits in daily_news.py, all covered here. Conventions: synthetic
SimpleNamespace app/team/player fixtures (same shape as the R8a-h tests);
assertions on premises, not phrasing. Rumor/backup firings are asserted
via the (entity_key, story_type) marks in app._daily_news_recent -- the
same marks the engine uses for variety suppression -- so the checks don't
depend on template wording.

Nit 1 -- global "Unknown Player/Team" post-render guard: any RENDERED story
carrying a placeholder name/team is suppressed at the _generate choke
point (fail closed, logged, never surfaced, not counted in `added`).

Nit 2 -- trade-rumor gate is position-aware (_rumor_pts_bar): forwards
(C/LW/RW) keep the 0.50 pts/gp bar; defensemen (D/LD/RD) get 0.30; goalies
and unknown positions get no bar (fail closed). A shutdown D-man at
0.40 pts/gp is on-role, not underperforming, and must not be framed as
trade bait.

Nit 3 -- backup-goalie bucket mirrors the presser's crease-controversy
gate (media_engine._maybe_spawn_narrative): the team's goalies are sorted
by save_percentage and the story fires only if the NAMED goalie is the top
one and top - second > 0.010. A .918 backup behind a .925 starter is not
a controversy; a team with fewer than two sane goalies can't have one.
"""
import sys
import os
import types
import random
import logging
from datetime import date

_REPO = os.environ.get(
    "R9_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

import daily_news as dn


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed += 1
check.failed = 0


DAY = date(2027, 1, 15)  # mid-season news day


def mkplayer(name, pos="C", ovr=80, gp=20, goals=0, assists=0,
             svp=None, years=3, pid=None):
    if name is None:
        first, last = None, None
    else:
        parts = name.split()
        first, last = parts[0], " ".join(parts[1:]) or parts[0]
    p = types.SimpleNamespace(first_name=first, last_name=last)
    p.id = pid if pid is not None else abs(hash(name)) % 10 ** 9
    p.primary_position = pos  # plain string: _pos falls back to str(pp)
    p.overall = float(ovr)
    p.stats = types.SimpleNamespace(games_played=gp, goals=goals,
                                    assists=assists, save_percentage=svp)
    p.contract = types.SimpleNamespace(years_remaining=years)
    return p


def mkteam(name, players):
    # No games_played attr -> scratch-watch block skips (team_gp < 10).
    return types.SimpleNamespace(team_name=name, roster=list(players))


def mkapp(*teams):
    return types.SimpleNamespace(
        league=types.SimpleNamespace(teams=list(teams)),
        _daily_news_recent={})


def rumor_mark(app, p):
    return (f"player:{p.id}", "rumor") in app._daily_news_recent


def backup_mark(app, p):
    return (f"player:{p.id}", "backup") in app._daily_news_recent


def run_controversies(app, seed=777):
    return dn._controversies(app, DAY, random.Random(seed))


def run_depth(app, seed=777):
    return dn._depth_stories(app, DAY, random.Random(seed))


# ---------------------------------------------------------------------------
# Nit 1: _story_has_unknown_entity truth table
# ---------------------------------------------------------------------------
check("unknown: 'Unknown Player' detected",
      dn._story_has_unknown_entity("RUMOR MILL: Unknown Player is done."))
check("unknown: 'Unknown Team' detected",
      dn._story_has_unknown_entity("Big win for Unknown Team tonight."))
check("unknown: clean story passes",
      not dn._story_has_unknown_entity("The Blades beat the Wolves 3-2."))
check("unknown: empty string passes",
      not dn._story_has_unknown_entity(""))
check("unknown: None passes (no crash)",
      not dn._story_has_unknown_entity(None))
check("unknown: non-string passes (no crash)",
      not dn._story_has_unknown_entity(12345))
check("unknown: case-sensitive (lowercase passes)",
      not dn._story_has_unknown_entity("unknown player scored twice"))
check("unknown: marker mid-sentence detected",
      dn._story_has_unknown_entity("Coach benched Unknown Player again."))

# ---------------------------------------------------------------------------
# Nit 1: _generate post-render guard (fail closed, logged, never surfaced)
# ---------------------------------------------------------------------------


def _generate_with(story_lists, day=DAY):
    """Run dn._generate with _GENERATORS monkeypatched to canned lists."""
    added_to = []
    app = types.SimpleNamespace(
        league=types.SimpleNamespace(teams=[]),
        _daily_news_recent={},
        add_news=lambda s: added_to.append(s))
    logged = []

    class _H(logging.Handler):
        def emit(self, record):
            logged.append(record.getMessage())

    logger = logging.getLogger("daily_news")
    h = _H()
    logger.addHandler(h)
    old_gens = dn._GENERATORS
    try:
        dn._GENERATORS = [
            (f"gen{i}", (lambda stories: (lambda a, gd, r: list(stories)))(s), 1.0)
            for i, s in enumerate(story_lists)
        ]
        n = dn._generate(app, day)
    finally:
        dn._GENERATORS = old_gens
        logger.removeHandler(h)
    return n, added_to, logged


n, added_to, logged = _generate_with(
    [["RUMOR MILL: Unknown Player is a target -- the Unknown Team star "
      "has just 5 points in 20 games."],
     ["The Blades practiced hard today."]])
check("guard: Unknown story never reaches add_news",
      added_to == ["The Blades practiced hard today."])
check("guard: `added` excludes the suppressed story", n == 1)
check("guard: suppression is logged",
      any("suppressed" in m and "Unknown Player" in m for m in logged))

n2, added2, logged2 = _generate_with(
    [["Unknown Team wins again, says Unknown Player."],
     ["Quiet day around the league."]])
check("guard: Unknown Team story suppressed too", added2 == ["Quiet day around the league."])
check("guard: team-marker suppression logged",
      any("suppressed" in m and "Unknown Team" in m for m in logged2))

n3, added3, _ = _generate_with(
    [["The Blades beat the Wolves 3-2."],
     ["Goalie duel in Halifax ends 1-0."]])
check("guard: clean stories all surface",
      sorted(added3) == sorted(["The Blades beat the Wolves 3-2.",
                                "Goalie duel in Halifax ends 1-0."]) and n3 == 2)

# Reviewer C (adversarial) finding: non-string story objects carrying the
# markers sailed through the guard to add_news, counted and unlogged.
# Fail-closed now: suppressed, logged, uncounted, never surfaced.
n4, added4, logged4 = _generate_with(
    [[["RUMOR MILL: Unknown Player is done."]],
     ["The Blades practiced hard today."]])
check("guard: non-string (list) story never reaches add_news",
      added4 == ["The Blades practiced hard today."])
check("guard: non-string story not counted in `added`", n4 == 1)
check("guard: non-string suppression is logged",
      any("suppressed" in m for m in logged4))

n5, added5, logged5 = _generate_with(
    [[("x", "Unknown Team wins")],
     ["Quiet day around the league."]])
check("guard: non-string (tuple) story suppressed too",
      added5 == ["Quiet day around the league."] and n5 == 1)

n6, added6, _ = _generate_with(
    [[{"t": "Unknown Player"}],
     ["Mild day around the league."]])
check("guard: non-string (dict) story suppressed too",
      added6 == ["Mild day around the league."] and n6 == 1)

# _tname strips whitespace-only names -> "Unknown Team" (mirrors _pname).
check("tname: whitespace-only team_name -> Unknown Team",
      dn._tname(types.SimpleNamespace(team_name="   ")) == "Unknown Team")
check("tname: real team name untouched",
      dn._tname(types.SimpleNamespace(team_name="Blades")) == "Blades")
check("tname: padded real name stripped",
      dn._tname(types.SimpleNamespace(team_name="  Blades  ")) == "Blades")
check("tname: None -> Unknown Team",
      dn._tname(types.SimpleNamespace(team_name=None)) == "Unknown Team")

# Whitespace-named team: backup story fails closed at the bucket.
w_g1 = mkplayer("Starter Real", pos="G", ovr=84, gp=25, svp=0.905)
w_g2 = mkplayer("Backup Real", pos="G", ovr=80, gp=8, svp=0.931)
app = mkapp(mkteam("   ", [w_g1, w_g2]))
stories = run_depth(app)
check("bucket: whitespace team_name -> no backup story", stories == [])

# ---------------------------------------------------------------------------
# Nit 2: _rumor_pts_bar unit checks
# ---------------------------------------------------------------------------
check("bar: C -> 0.50", dn._rumor_pts_bar(mkplayer("A B", pos="C")) == 0.50)
check("bar: LW -> 0.50", dn._rumor_pts_bar(mkplayer("A B", pos="LW")) == 0.50)
check("bar: RW -> 0.50", dn._rumor_pts_bar(mkplayer("A B", pos="RW")) == 0.50)
check("bar: D -> 0.30", dn._rumor_pts_bar(mkplayer("A B", pos="D")) == 0.30)
check("bar: LD -> 0.30", dn._rumor_pts_bar(mkplayer("A B", pos="LD")) == 0.30)
check("bar: RD -> 0.30", dn._rumor_pts_bar(mkplayer("A B", pos="RD")) == 0.30)
check("bar: G -> None (goalies excluded)",
      dn._rumor_pts_bar(mkplayer("A B", pos="G")) is None)
check("bar: blank position -> None (fail closed)",
      dn._rumor_pts_bar(mkplayer("A B", pos="")) is None)

# ---------------------------------------------------------------------------
# Nit 2: trade-rumor gate behavior
# ---------------------------------------------------------------------------
# Shutdown D-man at 0.40 pts/gp: on-role, NOT underperforming -> silent.
d_shutdown = mkplayer("Doug Shutdown", pos="LD", ovr=84, gp=20,
                      goals=3, assists=5, years=3)  # 8 pts / 20 = 0.40
app = mkapp(mkteam("Blades", [d_shutdown]))
stories = run_controversies(app)
check("rumor: shutdown D (0.40 ppg) NOT framed as trade bait",
      not rumor_mark(app, d_shutdown) and len(stories) == 0)

# Slumping offensive D-man at 0.20 pts/gp: genuinely underperforming -> fires.
d_slump = mkplayer("Otto Fensive", pos="RD", ovr=86, gp=20,
                   goals=1, assists=3, years=3)  # 4 pts / 20 = 0.20
app = mkapp(mkteam("Blades", [d_slump]))
stories = run_controversies(app)
check("rumor: slumping D (0.20 ppg) still eligible",
      rumor_mark(app, d_slump) and len(stories) == 1)
check("rumor: slumping-D story names him and his team",
      "Otto Fensive" in stories[0] and "Blades" in stories[0])

# D-man exactly at the 0.30 bar: strict < -> silent.
d_edge = mkplayer("Edge Case", pos="D", ovr=84, gp=20,
                  goals=2, assists=4, years=3)  # 6 pts / 20 = 0.30
app = mkapp(mkteam("Blades", [d_edge]))
stories = run_controversies(app)
check("rumor: D at exactly 0.30 ppg silent (strict <)",
      not rumor_mark(app, d_edge) and len(stories) == 0)

# D-man just under the bar fires.
d_under = mkplayer("Just Under", pos="LD", ovr=84, gp=20,
                   goals=2, assists=3, years=4)  # 5 pts / 20 = 0.25
app = mkapp(mkteam("Blades", [d_under]))
run_controversies(app)
check("rumor: D at 0.25 ppg fires", rumor_mark(app, d_under))

# Slumping forward at 0.40 ppg: under the 0.50 bar -> fires (unchanged).
f_slump = mkplayer("Fred Slump", pos="C", ovr=85, gp=20,
                   goals=3, assists=5, years=3)  # 0.40
app = mkapp(mkteam("Blades", [f_slump]))
run_controversies(app)
check("rumor: slumping forward (0.40 ppg) still fires",
      rumor_mark(app, f_slump))

# Producing forward at 0.60 ppg: above the bar -> silent.
f_prod = mkplayer("Pete Produce", pos="RW", ovr=85, gp=20,
                  goals=5, assists=7, years=3)  # 0.60
app = mkapp(mkteam("Blades", [f_prod]))
stories = run_controversies(app)
check("rumor: producing forward (0.60 ppg) silent",
      not rumor_mark(app, f_prod) and len(stories) == 0)

# Goalie with 0 points: old gate fired (0/20 < 0.5); now excluded entirely.
g_rumor = mkplayer("Gary Goalie", pos="G", ovr=85, gp=20,
                   goals=0, assists=0, svp=0.910, years=3)
app = mkapp(mkteam("Blades", [g_rumor]))
stories = run_controversies(app)
check("rumor: 85 OVR goalie with 0 pts NOT trade bait",
      not rumor_mark(app, g_rumor) and len(stories) == 0)

# Unknown position: fail closed, no rumor even at rock-bottom production.
u_pos = mkplayer("Mystery Man", pos="", ovr=88, gp=20,
                 goals=0, assists=1, years=3)
app = mkapp(mkteam("Blades", [u_pos]))
stories = run_controversies(app)
check("rumor: blank position fails closed",
      not rumor_mark(app, u_pos) and len(stories) == 0)

# Low-OVR forward still excluded by the OVR floor.
f_low = mkplayer("Low Talent", pos="C", ovr=74, gp=20,
                 goals=1, assists=2, years=3)
app = mkapp(mkteam("Blades", [f_low]))
stories = run_controversies(app)
check("rumor: 74 OVR forward below OVR floor stays silent",
      not rumor_mark(app, f_low) and len(stories) == 0)

# ---------------------------------------------------------------------------
# Nit 3: _team_goalie_svps unit checks
# ---------------------------------------------------------------------------
g1 = mkplayer("Starter Sam", pos="G", gp=25, svp=0.925)
g2 = mkplayer("Backup Bob", pos="G", gp=8, svp=0.930)
sk = mkplayer("Skater Sid", pos="C", gp=20, goals=5, assists=5)
t1 = mkteam("Blades", [g1, g2, sk])
t2 = mkteam("Wolves", [mkplayer("Other Otto", pos="G", gp=20, svp=0.900)])
players = [(g1, t1), (g2, t1), (sk, t1)] + [(p, t2) for p in t2.roster]
svps = dn._team_goalie_svps(players, t1)
check("svps: two sane goalies ranked",
      len(svps) == 2 and all(any(g[0] is x for g in svps) for x in (g1, g2)))
check("svps: skaters excluded", all("G" in dn._pos(g[0]).upper() for g in svps))
check("svps: team isolation (no cross-team mixing)",
      dn._team_goalie_svps(players, t2) != svps
      and len(dn._team_goalie_svps(players, t2)) == 1)

# Junk numerics are dropped, never ranked.
gj1 = mkplayer("Junk Inf", pos="G", gp=8, svp=float("inf"))
gj2 = mkplayer("Junk Nan", pos="G", gp=8, svp=float("nan"))
gj3 = mkplayer("Junk None", pos="G", gp=8, svp=None)
gj4 = mkplayer("Junk High", pos="G", gp=8, svp=1.5)
gj5 = mkplayer("Junk Neg", pos="G", gp=8, svp=-0.2)
tj = mkteam("Junkers", [gj1, gj2, gj3, gj4, gj5])
pj = [(p, tj) for p in tj.roster]
check("svps: inf/nan/None/>1/<0 all dropped", dn._team_goalie_svps(pj, tj) == [])

# ---------------------------------------------------------------------------
# Nit 3: backup-goalie bucket behavior
# ---------------------------------------------------------------------------
# Case A: .918 backup behind a .925 starter -- NOT a controversy.
starter_a = mkplayer("Starter Al", pos="G", ovr=84, gp=25, svp=0.925)
backup_a = mkplayer("Backup Al", pos="G", ovr=80, gp=8, svp=0.918)
app = mkapp(mkteam("Blades", [starter_a, backup_a]))
stories = run_depth(app)
check("backup: .918 backup behind .925 starter stays silent",
      not backup_mark(app, backup_a) and not backup_mark(app, starter_a)
      and len(stories) == 0)

# Case B: .930 backup out-saving a .905 starter -- controversy fires.
starter_b = mkplayer("Starter Bo", pos="G", ovr=84, gp=25, svp=0.905)
backup_b = mkplayer("Backup Bo", pos="G", ovr=80, gp=8, svp=0.930)
app = mkapp(mkteam("Blades", [starter_b, backup_b]))
stories = run_depth(app)
check("backup: .930 backup out-saving .905 starter fires",
      backup_mark(app, backup_b) and len(stories) == 1)
check("backup: story names the backup and carries no placeholders",
      "Backup Bo" in stories[0] and "Unknown" not in stories[0])

# Case C: lone goalie with great numbers -- no comparison possible.
lone = mkplayer("Lone Lou", pos="G", ovr=82, gp=8, svp=0.940)
app = mkapp(mkteam("Blades", [lone]))
stories = run_depth(app)
check("backup: single goalie cannot spark a controversy",
      not backup_mark(app, lone) and len(stories) == 0)

# Case D: near-miss trap -- gap 0.008 <= 0.010 -> silent.
starter_d = mkplayer("Starter Dan", pos="G", ovr=84, gp=25, svp=0.922)
backup_d = mkplayer("Backup Dan", pos="G", ovr=80, gp=8, svp=0.930)
app = mkapp(mkteam("Blades", [starter_d, backup_d]))
stories = run_depth(app)
check("backup: 0.008 gap (near-miss) stays silent",
      not backup_mark(app, backup_d) and len(stories) == 0)

# Boundary note: an "exact" 0.010 gap is not constructible with decimal
# literals in binary floating point (0.931 - 0.921 == 0.010000000000000009),
# so the gate deliberately mirrors the presser's plain-float `> 0.010`
# semantics instead of inventing its own epsilon. The near-miss traps use
# cleanly sub-threshold gaps.
starter_e = mkplayer("Starter Ed", pos="G", ovr=84, gp=25, svp=0.921)
backup_e = mkplayer("Backup Ed", pos="G", ovr=80, gp=8, svp=0.930)
app = mkapp(mkteam("Blades", [starter_e, backup_e]))
stories = run_depth(app)
check("backup: 0.009 gap (near-miss) stays silent",
      not backup_mark(app, backup_e) and len(stories) == 0)

# Case F: just over the boundary fires (0.011).
starter_f = mkplayer("Starter Fay", pos="G", ovr=84, gp=25, svp=0.920)
backup_f = mkplayer("Backup Fay", pos="G", ovr=80, gp=8, svp=0.931)
app = mkapp(mkteam("Blades", [starter_f, backup_f]))
run_depth(app)
check("backup: 0.011 gap fires", backup_mark(app, backup_f))

# Case G: starter's svp is junk (inf) -- dropped from ranking, backup alone.
starter_g = mkplayer("Starter Gus", pos="G", ovr=84, gp=25, svp=float("inf"))
backup_g = mkplayer("Backup Gus", pos="G", ovr=80, gp=8, svp=0.930)
app = mkapp(mkteam("Blades", [starter_g, backup_g]))
stories = run_depth(app)
check("backup: junk starter svp -> no ranking, no story",
      not backup_mark(app, backup_g) and len(stories) == 0)

# Case H: third goalie between them -- named goalie must still be top.
# mid (0.935) out-saves backup (0.915) by 0.020: mid fires, backup silent.
starter_h = mkplayer("Starter Hal", pos="G", ovr=84, gp=25, svp=0.905)
mid_h = mkplayer("Mid Hal", pos="G", ovr=79, gp=6, svp=0.935)
backup_h = mkplayer("Backup Hal", pos="G", ovr=80, gp=8, svp=0.915)
app = mkapp(mkteam("Blades", [starter_h, mid_h, backup_h]))
stories = run_depth(app)
check("backup: not-top goalie stays silent even with a big team gap",
      not backup_mark(app, backup_h))
check("backup: the actual top goalie fires",
      backup_mark(app, mid_h) and len(stories) == 1
      and "Mid Hal" in stories[0])

# Case I: backup below the 0.915 floor -- old absolute gate still holds.
starter_i = mkplayer("Starter Ivy", pos="G", ovr=84, gp=25, svp=0.890)
backup_i = mkplayer("Backup Ivy", pos="G", ovr=80, gp=8, svp=0.910)
app = mkapp(mkteam("Blades", [starter_i, backup_i]))
stories = run_depth(app)
check("backup: sub-0.915 backup stays silent despite out-saving starter",
      not backup_mark(app, backup_i) and len(stories) == 0)

# ---------------------------------------------------------------------------
# Nit 1b: bucket-level fail-closed (the _generate guard is the backstop).
# A slumping star / out-saving backup with placeholder names must produce
# NO story from the bucket itself -- verified FAIL pre-fix (the probe
# caught both buckets rendering "Unknown Player" stories), PASS post-fix.
# ---------------------------------------------------------------------------
u_rumor = mkplayer(None, pos="C", ovr=88, gp=20, goals=2, assists=2, years=3)
app = mkapp(mkteam("Blades", [u_rumor]))
stories = run_controversies(app)
check("bucket: Unknown-named slumping forward -> no rumor story",
      stories == [] and not rumor_mark(app, u_rumor))

u_rumor2 = mkplayer("Real Name", pos="C", ovr=88, gp=20, goals=2, assists=2,
                    years=3)
app = mkapp(mkteam(None, [u_rumor2]))
stories = run_controversies(app)
check("bucket: slumping forward on Unknown team -> no rumor story",
      stories == [])

u_g1 = mkplayer("Starter Real", pos="G", ovr=84, gp=25, svp=0.905)
u_g2 = mkplayer(None, pos="G", ovr=80, gp=8, svp=0.931)
app = mkapp(mkteam("Blades", [u_g1, u_g2]))
stories = run_depth(app)
check("bucket: Unknown-named out-saving backup -> no backup story",
      stories == [] and not backup_mark(app, u_g2))

u_g3 = mkplayer("Starter Real", pos="G", ovr=84, gp=25, svp=0.905)
u_g4 = mkplayer("Backup Real", pos="G", ovr=80, gp=8, svp=0.931)
app = mkapp(mkteam("", [u_g3, u_g4]))
stories = run_depth(app)
check("bucket: backup on Unknown team -> no backup story", stories == [])

# ---------------------------------------------------------------------------
# Crash battery: never raises
# ---------------------------------------------------------------------------
check("app=None -> []", dn._depth_stories(None, DAY, random.Random(1)) == [])
check("controversies app=None -> []",
      dn._controversies(None, DAY, random.Random(1)) == [])
app = types.SimpleNamespace(league=None, _daily_news_recent={})
check("league=None -> []", run_depth(app) == [])
bare = types.SimpleNamespace()
check("bare app -> []", dn._depth_stories(bare, DAY, random.Random(1)) == [])
check("bar junk player -> None", dn._rumor_pts_bar(types.SimpleNamespace()) is None)
check("svps empty players -> []", dn._team_goalie_svps([], mkteam("X", [])) == [])

def test_script_checks_all_pass():
    """Aggregate: every module-level check() above recorded zero failures.

    The file's historical script convention runs its checks at import; this
    test makes the result visible to pytest instead of only to the script's
    exit code.
    """
    assert check.failed == 0, f"{check.failed} check(s) failed"


if __name__ == "__main__":
    print()
    if check.failed:
        print(f"{check.failed} FAILURES")
        sys.exit(1)
    print("ALL CHECKS PASSED")
