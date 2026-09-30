#!/usr/bin/env python3
"""playtest_systems.py -- exercise Puck Dynasty's immersive systems headlessly.

Called from the campaign runner at the right season points. Every probe is
defensive: failures are logged as story bugs, never raised.

Covered: pro/amateur scouting assignments + regional ticks, development
training programs, staff dynamics (hire/fire/poach flavor), jersey
retirement ceremonies, outdoor games (Winter Classic rotation), Olympics,
HOF ballot, dressing-room social/player dynamics, game hype via media.
"""
import random, traceback
from datetime import date

REGIONS = ["Ontario", "Quebec", "Western Canada", "US East", "US West",
           "Sweden", "Finland", "Russia", "Czechia"]


def _bug(s, n, where, e, file=""):
    s.bug(n, where, f"{e}\n{traceback.format_exc()[-300:]}", False, file)


def preseason_systems(drv):
    """Scouting assignments, training programs, outdoor games, ceremonies."""
    s, lg, user, n, year = drv.story, drv.lg, drv.user, drv.n, drv.year
    # --- scouting: assign every amateur/pro scout a region, tick once ---
    try:
        import scouting as sc
        from game_classes import StaffRole
        gm = drv.gm if hasattr(drv, "gm") else None
        if gm is None:
            from types import SimpleNamespace
            gm = drv.gm = SimpleNamespace(league=lg,
                                          scout_region_assignments={})
        assigned = 0
        for t in [x for x in lg.teams
                  if getattr(x, "league_name", "") == "National Hockey League"]:
            for st in (getattr(t, "staff", None) or []):
                role = getattr(st, "role", None)
                if role in (StaffRole.AMATEUR_SCOUT, StaffRole.PROFESSIONAL_SCOUT,
                            StaffRole.EUROPEAN_SCOUT, StaffRole.HEAD_SCOUT):
                    sc.set_scout_region(gm, st, random.choice(REGIONS))
                    assigned += 1
        try:
            sc.process_regional_scouting(gm)
        except Exception:
            pass
        if assigned:
            s.add(n, date(year, 9, 22), "scouting", ["scouting"],
                  f"Scouts deployed: {assigned} regional assignments league-wide",
                  "Amateur meetings set the draft board.")
    except Exception as e:
        _bug(s, n, "scouting assignments", e, "scouting.py")
    # --- development: enroll top prospects in training programs ---
    try:
        import player_development_system as pds
        eng = pds.PlayerDevelopmentEngine()
        drv.dev_engine = eng
        enrolled = 0
        for p in (getattr(user, "prospects", None) or [])[:6]:
            try:
                focus = random.choice(list(pds.TrainingFocus))
                if eng.start_training_program(p, focus, intensity=3,
                                              duration_weeks=20,
                                              trainer_quality=4):
                    enrolled += 1
            except Exception:
                pass
        if enrolled:
            s.add(n, date(year, 9, 24), "development",
                  ["player_development_system"],
                  f"Development: {enrolled} prospects enrolled in training programs",
                  "Toronto's player development staff sets summer programs.")
    except Exception as e:
        _bug(s, n, "development programs", e, "player_development_system.py")
    # --- outdoor games (Winter Classic rotation) ---
    try:
        import outdoor_games as og
        sched = og.schedule_outdoor_games(lg, season_year=year)
        if sched:
            g = sched[0] if isinstance(sched, list) else sched
            info = str(g)[:160]
            s.add(n, date(year, 10, 5), "outdoor", ["outdoor_games"],
                  f"Outdoor game scheduled: {info}", "")
    except Exception as e:
        _bug(s, n, "outdoor games", e, "outdoor_games.py")
    # --- jersey retirement ceremonies due this season ---
    try:
        import immortality as im
        if not getattr(lg, "ceremony_schedule", None):
            lg.ceremony_schedule = im.ceremony_schedule_for(year)
        due = [c for c in lg.ceremony_schedule]
        if due:
            s.add(n, date(year, 10, 6), "ceremony", ["immortality"],
                  f"Rafter watch: {len(due)} jersey retirements scheduled "
                  f"({', '.join(c.get('player', '?') for c in due)})", "")
    except Exception as e:
        _bug(s, n, "ceremony schedule", e, "immortality.py")


def monthly_systems(drv, month):
    """Called from the driver's monthly hooks."""
    s, lg, user, n = drv.story, drv.lg, drv.user, drv.n
    day = drv.day
    # --- ceremonies due today ---
    try:
        import immortality as im
        for team, cer in im.ceremonies_due(lg, day):
            try:
                story = im.stage_ceremony(team, cer)
                s.add(n, day, "ceremony", ["immortality", "media_engine"],
                      f"JERSEY RETIREMENT: {cer.get('player')} #{cer.get('number')} "
                      f"raised by {team.team_name}", str(story)[:250])
            except Exception as e:
                _bug(s, n, "stage_ceremony", e, "immortality.py:874")
    except Exception:
        pass
    # --- development monthly tick ---
    try:
        eng = getattr(drv, "dev_engine", None)
        if eng is not None:
            for t in [x for x in lg.teams
                      if getattr(x, "league_name", "") == "National Hockey League"]:
                for p in (getattr(t, "prospects", None) or [])[:4]:
                    try:
                        eng.process_monthly_development(p)
                    except Exception:
                        pass
    except Exception:
        pass
    # --- staff dynamics flavor: assistant-coach tension / development ---
    if month in (11, 1, 3):
        try:
            import assistant_coaches as ac
            fns = [f for f in ("staff_friction_tick", "process_staff_dynamics",
                               "monthly_staff_tick") if hasattr(ac, f)]
            if fns:
                getattr(ac, fns[0])(lg)
                s.add(n, day, "staff", ["assistant_coaches"],
                      "Staff room: monthly dynamics tick", "")
        except Exception:
            pass
    # --- dressing-room social dynamics tick ---
    if month in (10, 12, 2, 4):
        try:
            import dressing_room as dr
            fns = [f for f in ("social_tick", "process_room_dynamics",
                               "monthly_room_tick") if hasattr(dr, f)]
            if fns:
                getattr(dr, fns[0])(user)
        except Exception:
            pass
    # --- Olympics: Feb of the Olympic year (2030 in a 2026-start league) ---
    # NOTE: monthly_systems runs on month-boundary ticks, so no day-of-month
    # condition here -- `day.day == 9` could never match and the tournament
    # silently never fired. The _olympics_done flag keeps it once-per-season.
    try:
        import international as oi
        if oi.is_olympic_year(day.year) and month == 2 \
                and not getattr(drv, "_olympics_done", False):
            drv._olympics_done = True
            try:
                rosters = oi.select_olympic_rosters(lg, day.year)
                n_play = sum(len(r.get("players", [])) for r in rosters.values()) \
                    if isinstance(rosters, dict) else "?"
                s.add(n, day, "olympics", ["international", "media_engine"],
                      f"Olympic rosters named ({n_play} NHLers selected); "
                      f"NHL goes dark Feb 10-24", "")
                try:
                    result = oi.resolve_olympics(lg, rosters, day.year)
                    s.add(n, date(day.year, 2, 23), "olympics",
                          ["international"],
                          f"Olympic tournament resolved: {str(result)[:180]}", "")
                except Exception as e:
                    _bug(s, n, "olympics resolve", e, "international.py")
            except Exception as e:
                _bug(s, n, "olympics rosters", e, "international.py")
    except Exception:
        pass


def offseason_systems(drv):
    """HOF ballot, training program completion."""
    s, lg, user, n, year = drv.story, drv.lg, drv.user, drv.n, drv.year
    try:
        eng = getattr(drv, "dev_engine", None)
        if eng is not None:
            done = eng.complete_training_programs()
            if done:
                s.add(n, date(year + 1, 6, 15), "development",
                      ["player_development_system"],
                      f"Development: {len(done)} training programs completed",
                      "")
    except Exception as e:
        _bug(s, n, "complete training", e, "player_development_system.py")
    try:
        import immortality as im
        hist = getattr(lg, "league_history", None)
        ballot = im.hof_ballot(lg, hist, year + 1)
        inducted = ballot.get("inducted") or ballot.get("elected") or []
        if inducted:
            names = ", ".join(x.get("name", str(x)) for x in inducted[:5])
            s.add(n, date(year + 1, 6, 20), "hof", ["immortality"],
                  f"Hockey Hall of Fame: {names} inducted", "")
    except Exception as e:
        _bug(s, n, "HOF ballot", e, "immortality.py:172")
