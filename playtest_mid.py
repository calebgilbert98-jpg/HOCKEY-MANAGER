
# playtest_mid.py -- all-star, playoffs, awards (monkey-patched onto SeasonDriver)
import random, traceback
from playtest_driver import (StoryLog, nhl_teams, get_team, ensure_lineup, ovr,
                             distribute_stats, apply_standings, USER_TEAM_NAME)
from playtest_season import SeasonDriver
from quick_sim import AdvancedGameSim
import playoff_system
def _all_star(self):
    s, lg = self.story, self.lg
    try:
        import all_star as AS
        rosters = AS.select_all_star_rosters(lg, season_year=self.year)
        coaches = AS.select_all_star_coaches(lg)
        toronto_as = []
        for div in rosters.values():
            for key in ("captain", "skaters", "goalies"):
                ps = div.get(key)
                ps = [ps] if key == "captain" else (ps or [])
                for p in ps:
                    t = self._tm(p)
                    if t == USER_TEAM_NAME:
                        toronto_as.append(p.full_name)
        n_sel = sum(1 + len(v.get("skaters", [])) + len(v.get("goalies", []))
                    for v in rosters.values())
        s.add(self.n, self.day, "allstar",
              ["all_star", "media_engine"],
              f"All-Star rosters named ({n_sel} players)"
              + (f"; Toronto sends: {', '.join(toronto_as)}" if toronto_as else "; no Leafs selected"),
              "")
        try:
            result = AS.play_all_star_game(rosters)
            s.add(self.n, self.day, "allstar", ["all_star"],
                  f"All-Star Game: {result}", "")
        except Exception as e:
            s.bug(self.n, "all-star game", f"{e}", False, "all_star.py:440")
    except Exception as e:
        s.bug(self.n, "all-star", f"all_star failed: {e}", False, "all_star.py")

SeasonDriver._all_star = _all_star

# -------------------------------------------------------------- playoffs
def _playoffs(self):
    s, lg, user = self.story, self.lg, self.user
    try:
        bracket = playoff_system.PlayoffBracket(lg)
        bracket.generate_playoff_bracket()
    except Exception as e:
        s.bug(self.n, "playoffs", f"bracket build failed: {e}", False,
              "playoff_system.py")
        return None
    qualified = [t.team_name for t in bracket.eastern_teams + bracket.western_teams]
    if user.team_name not in qualified:
        s.add(self.n, self.day, "playoffs", ["playoff_system"],
              "Toronto misses the playoffs",
              f"Finished outside the top 8 in the East.")
        return None
    s.add(self.n, self.day, "playoffs", ["playoff_system"],
          "Toronto makes the playoffs", "")
    champ = None
    rnd = "wild_card"
    try:
        while True:
            series_list = bracket.playoff_series.get(rnd, [])
            if not series_list:
                break
            for series in series_list:
                t1 = series.team1 if hasattr(series, "team1") else series.teams[0]
                t2 = series.team2 if hasattr(series, "team2") else series.teams[1]
                w1 = w2 = 0
                gn = 0
                while w1 < 4 and w2 < 4 and gn < 7:
                    gn += 1
                    # 2-2-1-1-1: alternate home ice crudely
                    home, away = (t1, t2) if gn in (1, 2, 5, 7) else (t2, t1)
                    ensure_lineup(home); ensure_lineup(away)
                    sim = AdvancedGameSim(home, away)
                    try:
                        winner, loser, scores, events, notable = sim.run()
                    except Exception:
                        winner = home if random.random() < 0.55 else away
                        scores = (3, 2)
                    hs, ag = scores
                    distribute_stats(home, away, hs, ag)
                    if winner is t1:
                        w1 += 1
                    else:
                        w2 += 1
                    try:
                        series.add_game_result(winner is t1,
                                             {"score": scores, "game": gn})
                    except Exception:
                        pass
                    if home is user or away is user:
                        s.add(self.n, self.day, "playoff_game",
                              ["playoff_system", "sim"],
                              f"Playoff G{gn}: Toronto {'wins' if winner is user else 'loses'} "
                              f"{max(hs, ag)}-{min(hs, ag)} vs "
                              f"{(away if home is user else home).team_name} "
                              f"(series {w1 if user is t1 else w2}-"
                              f"{w2 if user is t1 else w1})", "")
                sw = t1 if w1 == 4 else t2
                if rnd == "stanley_cup_final":
                    champ = sw
                    s.add(self.n, self.day, "cup", ["playoff_system"],
                          f"STANLEY CUP CHAMPION: {sw.team_name} "
                          f"({max(w1, w2)}-{min(w1, w2)} over "
                          f"{(t2 if sw is t1 else t1).team_name})", "")
                if user in (t1, t2):
                    s.add(self.n, self.day, "playoff_series",
                          ["playoff_system"],
                          f"Toronto {'WINS' if sw is user else 'LOSES'} "
                          f"round ({max(w1, w2)}-{min(w1, w2)}) vs "
                          f"{(t2 if user is t1 else t1).team_name}",
                          "Stanley Cup Playoffs.")
            try:
                bracket.advance_to_next_round(rnd)
            except Exception as e:
                s.bug(self.n, "playoffs", f"advance_to_next_round failed: {e}",
                      False, "playoff_system.py")
                break
            order = ["wild_card", "division_semifinals", "division_finals",
                     "stanley_cup_final"]
            nxt = order[order.index(rnd) + 1] if rnd in order and order.index(rnd) + 1 < len(order) else None
            if nxt is None:
                break
            rnd = nxt
        champ = champ or getattr(bracket, "stanley_cup_champion", None)
        if champ is not None and not any(e["kind"] == "cup" for e in s.events
                                         if e["season"] == self.n):
            s.add(self.n, self.day, "cup", ["playoff_system"],
                  f"STANLEY CUP CHAMPION: {champ.team_name}", "")
    except Exception as e:
        s.bug(self.n, "playoffs", f"playoff sim failed: {e}\n"
              f"{traceback.format_exc()[-400:]}", False, "playoff_system.py")
    return champ

SeasonDriver._playoffs = _playoffs

# ---------------------------------------------------------------- awards
def _awards(self):
    s, lg = self.story, self.lg
    try:
        players = [p for t in nhl_teams(lg) for p in t.roster
                   if p.primary_position.name != "GOALIE"]
        goalies = [p for t in nhl_teams(lg) for p in t.roster
                   if p.primary_position.name == "GOALIE"]
        pts = lambda p: p.stats.goals + p.stats.assists
        art = max(players, key=pts) if players else None
        rocket = max(players, key=lambda p: p.stats.goals) if players else None
        def gaa(g):
            gp = g.stats.games_played or 1
            return g.stats.goals_against / gp
        vez = min([x for x in goalies if x.stats.games_played >= 20], key=gaa,
                  default=None)
        # rookie: under-26, <25 prior GP feel via age + low career games
        rook_c = [p for p in players if getattr(p, "age", 99) <= 23
                  and p.stats.games_played >= 30]
        calder = max(rook_c, key=pts) if rook_c else None
        if art:
            s.add(self.n, self.day, "awards", ["awards_race"],
                  f"Art Ross: {art.full_name} ({self._tm(art)}) — "
                  f"{art.stats.goals}G {art.stats.assists}A", "")
        if rocket:
            s.add(self.n, self.day, "awards", ["awards_race"],
                  f"Rocket Richard: {rocket.full_name} ({self._tm(rocket)}) — "
                  f"{rocket.stats.goals} goals", "")
        if vez:
            s.add(self.n, self.day, "awards", ["awards_race"],
                  f"Vezina: {vez.full_name} ({self._tm(vez)}) — "
                  f"{gaa(vez):.2f} GAA", "")
        if calder:
            s.add(self.n, self.day, "awards", ["awards_race"],
                  f"Calder: {calder.full_name} ({self._tm(calder)}) — "
                  f"{pts(calder)} pts as a rookie", "")
        # fan favourite: Toronto's top scorer
        tf = [p for p in self.user.roster if p.primary_position.name != "GOALIE"]
        if tf:
            fav = max(tf, key=pts)
            s.add(self.n, self.day, "fan_favourite",
                  ["reputation_system"],
                  f"Toronto fan favourite: {fav.full_name} ({pts(fav)} pts)", "")
    except Exception as e:
        s.bug(self.n, "awards", f"awards computation failed: {e}", False,
              "awards_race.py")

def _tm(self, p):
    for t in nhl_teams(self.lg):
        if p in t.roster:
            return t.team_name
    return "?"

SeasonDriver._awards = _awards
SeasonDriver._tm = _tm
