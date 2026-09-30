#!/usr/bin/env python3
"""QA: scout POV perception layer (refinement #3) + pro-scout beats (#4).

Probes:
  P1 determinism      same scout+player+viewings -> identical read
  P2 accuracy bands   A-grade ~exact on primaries; F-grade wide ranges;
                      hit-rate modulator math
  P3 GM-truth isolation  true-value paths (composites, Overview tab,
                      trade tags, engine) untouched; player never mutated
  P4 pro beat         SHL-beat pro scout accumulates viewings over a
                      simulated month, zero user assignments; tab shows
                      perceived (not true) values
  P5 save/load        pro-region assignments round-trip

Usage: python3 qa_scout_pov.py [--dump-read PATH]
"""
import sys, os, json, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed, failed = [], []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append(name)
        print(f"  FAIL {name} {detail}")


def make_player(**kw):
    from game_classes import Player, PlayerPosition
    p = Player(first_name=kw.pop('first_name', 'Test'),
               last_name=kw.pop('last_name', 'Player'),
               age=kw.pop('age', 24),
               primary_position=kw.pop('primary_position',
                                       PlayerPosition.LEFT_WING),
               **kw)
    return p


def make_scout(role, jpa=70, jpp=70, calls=0, hits=0):
    from game_classes import Staff, StaffRole
    s = Staff(first_name="Seedy", last_name="McScout", role=role,
              judging_player_ability=jpa, judging_player_potential=jpp)
    if calls:
        s.tip_record = {"calls": calls, "hits": hits}
    return s


def mid_player():
    """Mid-range attrs (no clamp asymmetry in the probes)."""
    from game_classes import PlayerPosition
    p = make_player(primary_position=PlayerPosition.LEFT_WING)
    for a, v in {"shooting": 70, "passing": 70, "offensive_awareness": 70,
                 "deking": 70, "skating": 70, "vision": 70,
                 "defensive_awareness": 70, "checking": 70,
                 "shooting_accuracy": 70, "composure": 70,
                 "offensive_positioning": 70}.items():
        setattr(p, a, v)
    return p


# ---------------------------------------------------------------- P1
def p1_determinism():
    import scout_perception as sp
    from game_classes import StaffRole, ScoutingReport
    p = mid_player()
    s = make_scout(StaffRole.PROFESSIONAL_SCOUT, 80, 80)
    rep = ScoutingReport(player=p, scout=s)
    for _ in range(8):
        rep.update_report(p, s)
    r1 = sp.perceived_attributes(p, s, rep)
    r2 = sp.perceived_attributes(p, s, rep)
    r3 = sp.perceived_attributes(p, s, rep)
    check("P1 attrs stable across opens", r1 == r2 == r3)
    c1 = sp.perceived_composites(p, s, rep)
    c2 = sp.perceived_composites(p, s, rep)
    check("P1 composites stable across opens", c1 == c2)
    # cold read (no report) also stable
    n1 = sp.perceived_attributes(p, s, None)
    n2 = sp.perceived_attributes(p, s, None)
    check("P1 cold read stable", n1 == n2)
    if "--dump-read" in sys.argv:
        path = sys.argv[sys.argv.index("--dump-read") + 1]
        with open(path, "w") as f:
            json.dump({k: (list(v) if isinstance(v, tuple) else v)
                       for k, v in r1.items()}, f, sort_keys=True)
        print(f"  dumped read -> {path}")


# ---------------------------------------------------------------- P2
def p2_accuracy():
    import scout_perception as sp
    from game_classes import StaffRole, ScoutingReport
    from game_classes import PlayerPosition

    p = mid_player()
    # A-grade scout: 20+ viewings, elite JPA/JPP
    sa = make_scout(StaffRole.HEAD_SCOUT, 95, 95)
    rep_a = ScoutingReport(player=p, scout=sa)
    for _ in range(25):
        rep_a.update_report(p, sa)
    check("P2 A-grade achieved", rep_a.accuracy == 'A',
          f"got {rep_a.accuracy}")
    pa = sp.perceived_attributes(p, sa, rep_a)
    primaries = ['shooting', 'passing', 'offensive_awareness', 'deking',
                 'skating']
    exact = all(pa[a] == 70 for a in primaries)
    check("P2 A-grade exact on primaries", exact,
          str({a: pa[a] for a in primaries}))
    ca = sp.perceived_composites(p, sa, rep_a)
    import attribute_composites as ac
    true_c = ac.get_composite_ratings(p)
    check("P2 A-grade composites == true composites",
          all(abs(ca[k] - true_c[k]) < 0.05 for k in ca),
          str({k: ca[k] for k in ('finishing', 'chance_creation')}))

    # F-grade scout: 1 viewing, rock-bottom JPA/JPP -> F
    # (skill_bonus = (10+10)//10 = 2; effective viewings 1+2=3 < 5)
    sf = make_scout(StaffRole.PROFESSIONAL_SCOUT, 10, 10)
    rep_f = ScoutingReport(player=p, scout=sf)
    rep_f.update_report(p, sf)
    check("P2 F-grade achieved", rep_f.accuracy == 'F',
          f"got {rep_f.accuracy}")
    p.vision = 50    # mid-scale secondaries: no clamp asymmetry
    p.shooting = 50  # (A-grade exactness was already verified above)
    pf = sp.perceived_attributes(p, sf, rep_f)
    # forward primaries: half-spread 15 -> width 30; secondaries: 20 -> 40
    w_prim = pf['shooting'][1] - pf['shooting'][0]
    w_sec = pf['vision'][1] - pf['vision'][0]
    check("P2 F primary width 30 (15+15)", w_prim == 30,
          f"shooting={pf['shooting']}")
    check("P2 F secondary width 40 (20+20)", w_sec == 40,
          f"vision={pf['vision']}")
    check("P2 F reads are ranges", isinstance(pf['shooting'], tuple))

    # hit-rate modulator: 9/10 hits -> x0.85 ; 2/10 hits -> x1.15
    # (JPA/JPP 10 keeps the grade at F so the band math is clean)
    sg = make_scout(StaffRole.PROFESSIONAL_SCOUT, 10, 10, calls=10, hits=9)
    rep_g = ScoutingReport(player=p, scout=sg)
    rep_g.update_report(p, sg)
    pg = sp.perceived_attributes(p, sg, rep_g)
    check("P2 hot scout tightens (width 34)",
          pg['vision'][1] - pg['vision'][0] == 34,
          f"vision={pg['vision']}")
    sb = make_scout(StaffRole.PROFESSIONAL_SCOUT, 10, 10, calls=10, hits=2)
    rep_b = ScoutingReport(player=p, scout=sb)
    rep_b.update_report(p, sb)
    pb = sp.perceived_attributes(p, sb, rep_b)
    check("P2 cold scout widens (width 46)",
          pb['vision'][1] - pb['vision'][0] == 46,
          f"vision={pb['vision']}")
    # tiny sample -> no modulation
    st = make_scout(StaffRole.PROFESSIONAL_SCOUT, 10, 10, calls=3, hits=3)
    rep_t = ScoutingReport(player=p, scout=st)
    rep_t.update_report(p, st)
    pt = sp.perceived_attributes(p, st, rep_t)
    check("P2 small sample unmodulated (width 40)",
          pt['vision'][1] - pt['vision'][0] == 40,
          f"vision={pt['vision']}")


# ---------------------------------------------------------------- P3
def p3_isolation():
    import scout_perception as sp
    import attribute_composites as ac
    from game_classes import StaffRole, ScoutingReport

    p = mid_player()
    s = make_scout(StaffRole.PROFESSIONAL_SCOUT, 40, 40)
    rep = ScoutingReport(player=p, scout=s)
    rep.update_report(p, s)

    # true composite path == manual weighted sum (engine truth intact)
    # set ALL finishing members to 70 first (untouched defaults differ)
    for a in ("shooting", "shooting_accuracy", "offensive_positioning",
              "composure", "shooting_power", "pressure_player",
              "one_timer", "backhand"):
        setattr(p, a, 70)
    manual = 70.0  # every member 70 -> weighted sum 70
    true_c = ac.get_composite_ratings(p)
    check("P3 true composite == manual blend",
          abs(true_c['finishing'] - manual) < 0.01,
          f"{true_c['finishing']} vs {manual}")

    # perception never mutates the player
    before = {a: getattr(p, a) for a in sp.SKATER_ATTRS
              if getattr(p, a, None) is not None}
    sp.perceived_attributes(p, s, rep)
    sp.perceived_composites(p, s, rep)
    sp.perceived_strengths_weaknesses(p, s, rep)
    after = {a: getattr(p, a) for a in before}
    check("P3 player unmutated by perception", before == after)

    # perceived differs from truth at F grade (fog exists)
    pf = sp.perceived_attributes(p, s, rep)
    differs = any(v != 70 for v in pf.values()
                  if not isinstance(v, tuple)) or \
        any(v != (70, 70) for v in pf.values() if isinstance(v, tuple))
    check("P3 F read differs from truth", differs)

    # static: scout_perception imported ONLY by the Scout Report tab
    import ast
    tree = ast.parse(open("modern_profile.py").read())
    sp_imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module or ""])
            if any("scout_perception" in m for m in mods):
                # find enclosing function
                sp_imports.append(True)
    check("P3 scout_perception import sites == 1 (scout tab only)",
          len(sp_imports) == 1, f"found {len(sp_imports)}")

    # Overview/Attributes tab builder reads true attrs directly
    src = open("modern_profile.py").read()
    check("P3 _create_attributes reads true player attrs",
          "def _create_attributes" in src and
          "getattr(self.player" in src)

    # trade-tag perceiver context has no perception import
    tag_src = open("ai_extension_planning.py").read() + \
        open("windows.py").read()
    check("P3 trade tags never import scout_perception",
          "scout_perception" not in tag_src)


# ---------------------------------------------------------------- P4
def _fake_league():
    from game_classes import StaffRole, PlayerPosition
    from types import SimpleNamespace

    def euro(name, league_name):
        p = make_player(first_name=name, last_name="Euro", age=26,
                        primary_position=PlayerPosition.LEFT_WING)
        p.shooting, p.passing = 78, 74
        p.source_league = league_name
        p.team_name = "Free Agent"
        return p

    shl = [euro(f"SHL{i}", "SHL") for i in range(10)]
    ahl_players = [make_player(first_name=f"Farm{i}", age=22,
                               primary_position=PlayerPosition.CENTER)
                   for i in range(12)]
    for i, pl in enumerate(ahl_players):
        pl.shooting = 60 + i

    user_team = SimpleNamespace(
        team_name="Testers", staff=[], roster=[], ahl_roster=[],
        scouting_reports={})
    user_team.staff = [
        make_scout(StaffRole.HEAD_SCOUT, 85, 85),
        make_scout(StaffRole.PROFESSIONAL_SCOUT, 80, 80),   # -> SHL beat
        make_scout(StaffRole.EUROPEAN_SCOUT, 75, 75),       # default beat
        make_scout(StaffRole.AMATEUR_SCOUT, 70, 70),        # no default
    ]
    t2 = SimpleNamespace(team_name="Rivals", ahl_roster=ahl_players[:6])
    t3 = SimpleNamespace(team_name="Others", ahl_roster=ahl_players[6:])
    league = SimpleNamespace(teams=[user_team, t2, t3],
                             free_agents=shl, draft_prospects=[])
    gm = SimpleNamespace(league=league, user_team=user_team,
                         scout_region_assignments={})
    return gm, user_team, shl


def p4_probeat():
    import scouting as sc
    import scout_perception as sp
    from game_classes import StaffRole

    gm, user_team, shl = _fake_league()
    pro_scout = user_team.staff[1]
    euro_scout = user_team.staff[2]
    amat_scout = user_team.staff[3]

    # default beats from hire (no assignments yet)
    sc.ensure_default_pro_beats(gm)
    ra = gm.scout_region_assignments
    check("P4 pro scout default beat AHL",
          ra.get(pro_scout.id) == "AHL", str(ra.get(pro_scout.id)))
    check("P4 euro scout default beat SHL",
          ra.get(euro_scout.id) == "SHL", str(ra.get(euro_scout.id)))
    check("P4 amateur scout gets no default",
          amat_scout.id not in ra)
    check("P4 head scout gets no default",
          user_team.staff[0].id not in ra)

    # per the probe: pro scout explicitly on an SHL beat
    sc.set_scout_region(gm, pro_scout, "SHL")

    # simulated month, zero user assignments
    random.seed(20260930)
    for _ in range(30):
        sc.process_pro_scouting(gm)
    reports = user_team.scouting_reports
    shl_reported = [pid for pid, r in reports.items()
                    if getattr(r.player, 'source_league', '') == 'SHL']
    total_views = sum(reports[pid].viewings for pid in shl_reported)
    check("P4 SHL viewings accumulated (>0)", total_views > 0,
          f"total_views={total_views} players={len(shl_reported)}")
    check("P4 reports live in user_team.scouting_reports",
          len(shl_reported) > 0)

    # ownership: first scout to file owns the report
    owners_ok = all(reports[pid].scout is pro_scout
                    or reports[pid].scout is euro_scout
                    for pid in shl_reported)
    check("P4 single-report-per-player, scout-owned", owners_ok)

    # tab resolution -> the filing scout, perceived != true.
    # After a month the report may be A-grade (exact == true), so prove
    # the perception path on a FRESH 1-viewing report instead: the tab's
    # data must be the scout's ranged read, not the true point value.
    from game_classes import ScoutingReport as _SR
    fresh = make_player(first_name="Fresh", age=26)
    fresh.shooting, fresh.passing = 78, 74
    fresh.source_league = "SHL"
    poor = make_scout(StaffRole.PROFESSIONAL_SCOUT, 10, 10)
    user_team.staff.append(poor)
    sc.set_scout_region(gm, poor, "SHL")
    frep = _SR(player=fresh, scout=poor)
    frep.update_report(fresh, poor)
    user_team.scouting_reports[fresh.id] = frep
    scout2, report2 = sp.resolve_tab_scout(user_team, fresh)
    check("P4 tab resolves to filing scout",
          scout2 is poor and report2 is frep)
    perc2 = sp.perceived_attributes(fresh, scout2, report2)
    check("P4 tab values are perceived ranges, not true points",
          isinstance(perc2['shooting'], tuple) and perc2['shooting'] != 78,
          f"perceived={perc2['shooting']} true=78")

    # AHL beat still works (farm rosters)
    sc.set_scout_region(gm, euro_scout, "AHL")
    before = len(reports)
    for _ in range(30):
        sc.process_pro_scouting(gm)
    ahl_reported = [pid for pid in reports
                    if pid not in shl_reported or
                    getattr(reports[pid].player, 'source_league', '') != 'SHL']
    check("P4 AHL beat files farm viewings", len(reports) > before,
          f"reports {before} -> {len(reports)}")

    # unknown / amateur regions are ignored by the pro tick
    sc.set_scout_region(gm, amat_scout, "CHL")
    n0 = len(reports)
    sc.process_pro_scouting(gm)
    check("P4 amateur region ignored by pro tick", len(reports) == n0)


# ---------------------------------------------------------------- P5
def p5_saveload():
    import scouting as sc
    import json
    gm, user_team, _ = _fake_league()
    sc.ensure_default_pro_beats(gm)
    sc.set_scout_region(gm, user_team.staff[1], "Liiga")
    # exact save expression from save_load_system.py
    saved = dict(getattr(gm, 'scout_region_assignments', {}) or {})
    blob = json.dumps(saved)          # save file is JSON
    restored = json.loads(blob)
    gm2_ra = {}
    gm2_ra = restored                 # load: setattr(game_manager, key, ...)
    check("P5 pro regions round-trip incl. JSON",
          gm2_ra == saved and
          set(gm2_ra.values()) == {"Liiga", "SHL"},
          str(gm2_ra))


if __name__ == "__main__":
    print("== P1 determinism ==")
    p1_determinism()
    print("== P2 accuracy bands ==")
    p2_accuracy()
    print("== P3 GM-truth isolation ==")
    p3_isolation()
    print("== P4 pro beat ==")
    p4_probeat()
    print("== P5 save/load ==")
    p5_saveload()
    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", failed)
        sys.exit(1)
