# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# playtest_season.py -- SeasonDriver: preseason, regular season, trade deadline
import random, traceback
from datetime import date
from playtest_driver import (StoryLog, nhl_teams, get_team, ensure_lineup, ovr,
                             distribute_stats, apply_standings, USER_TEAM_NAME)
from quick_sim import AdvancedGameSim, best_lines, flatten_lineup

# ---------------------------------------------------------------- season driver
class SeasonDriver:
    def __init__(self, league, season_no, strategy, story):
        self.lg = league
        self.n = season_no
        self.strategy = strategy
        self.story = story
        self.user = get_team(league, USER_TEAM_NAME)
        self.year = getattr(league, "season_year", 2026)
        self.day = None
        self.trades_made = []
        self.signings = []

    # ------------------------------------------------------------ preseason
    def preseason(self):
        s = self.story
        s.add(self.n, date(self.year, 9, 20), "preseason", ["coach_practice"],
              f"Camp opens: {self.strategy} year in Toronto",
              f"Strategy: {self.strategy}. Roster: {len(self.user.roster)} players.")
        # practices: a few attribute drills via coach_practice if headless-safe
        try:
            import coach_practice as cp
            drills = 0
            for attr in ("skating", "shooting", "defense"):
                try:
                    r = cp.attribute_drill(attr)
                    if r:
                        drills += 1
                except Exception:
                    pass
            s.add(self.n, date(self.year, 9, 25), "practice", ["coach_practice"],
                  f"Camp drills run ({drills} focus areas)",
                  "Practices held before opening night.")
        except Exception as e:
            s.bug(self.n, "preseason practices", f"coach_practice failed: {e}",
                  False, "coach_practice")
        # opening team talk
        try:
            import dressing_room as dr
            out = dr.give_talk(self.user, "fired-up",
                               {"situation": "pregame", "score_state": "tied",
                                "rival": False, "streak": 0})
            s.add(self.n, date(self.year, 10, 1), "team_talk", ["dressing_room"],
                  f"Opening-night team talk: {out.get('outcome', '?')}",
                  str(out.get("note", ""))[:200])
        except Exception as e:
            s.bug(self.n, "team talk", f"give_talk failed: {e}", False,
                  "dressing_room.py:1647")
        for t in nhl_teams(self.lg):
            ensure_lineup(t)

    # ------------------------------------------------------- regular season
    def regular_season(self):
        lg, s, user = self.lg, self.story, self.user
        games = [e for e in lg.schedule if isinstance(e, dict)
                 and not e.get("preseason")
                 and getattr(e.get("home_team"), "league_name", "") == "National Hockey League"]
        games.sort(key=lambda e: e["date"])
        s.add(self.n, games[0]["date"], "season_start", ["schedule"],
              f"Opening night: {len(games)}-game slate",
              f"{user.team_name} opens the {self.year}-{self.year+1} campaign.")
        last_month = None
        ugp = 0  # user games played
        for i, gm in enumerate(games):
            home, away = gm["home_team"], gm["away_team"]
            self.day = gm["date"]
            # refresh lineups when injuries hit (cheap: every game for user, weekly for AI)
            if home is user or away is user or i % 7 == 0:
                ensure_lineup(home)
                ensure_lineup(away)
            try:
                sim = AdvancedGameSim(home, away, league=lg)
                winner, loser, scores, events, notable = sim.run()
            except Exception as e:
                s.bug(self.n, "game sim",
                      f"AdvancedGameSim crashed {home.team_name} vs {away.team_name}: {e}",
                      False, "quick_sim.py")
                continue
            hs, ag = scores
            distribute_stats(home, away, hs, ag)
            # OT detection: match production (main.py) -- any GOAL or
            # SHOOTOUT GOAL with period > 3. Raw events are wrong here:
            # late-3rd-period shots/dekes leak into period 4 when the
            # clock crosses 3600 mid-shift.
            went_ot = any(isinstance(_e, dict) and _e.get("period", 0) > 3
                          for _e in (notable or []))
            apply_standings(lg, home, away, hs, ag, went_ot=went_ot)
            # analytics-hub feed: per-game record on both clubs
            try:
                shots = [{"team": (e.get("team") or ""),
                          "period": e.get("period", 1),
                          "time": e.get("time", 0),
                          "xg": 0.08}
                         for e in (events or []) if e.get("event") == "Shot"]
                rec = {"home": home.team_name, "away": away.team_name,
                       "score": (hs, ag), "date": str(self.day),
                       "shots": shots, "entries": [],
                       "momentum": [{"period": 1, "time": 0,
                                     "momentum": "neutral", "trigger": ""}]}
                for t in (home, away):
                    ag_list = getattr(t, "analytics_games", None)
                    if ag_list is None:
                        ag_list = t.analytics_games = []
                    ag_list.append(rec)
            except Exception:
                pass
            # injury recovery tick
            for t in (home, away):
                for p in t.roster:
                    if getattr(p, "is_injured", False):
                        p.games_remaining_injured = max(
                            0, getattr(p, "games_remaining_injured", 1) - 1)
                        if p.games_remaining_injured == 0:
                            p.is_injured = False
            # user-game story capture
            if home is user or away is user:
                ugp += 1
                self._user_game_story(sim, home, away, hs, ag, events, notable)
            # monthly GM hooks
            month = self.day.month
            if month != last_month:
                last_month = month
                self._monthly_hooks(month, ugp)
        s.add(self.n, self.day, "season_end", ["standings"],
              f"Regular season ends: Toronto "
              f"{lg.standings[user.team_name]['W']}-"
              f"{lg.standings[user.team_name]['L']}-"
              f"{lg.standings[user.team_name]['OTL']}",
              "")

    def _user_game_story(self, sim, home, away, hs, ag, events, notable):
        s, user = self.story, self.user
        opp = away if home is user else home
        us, them = (hs, ag) if home is user else (ag, hs)
        won = us > them
        # iconic-game detection (brawls, comebacks, goalie fights, milestones)
        try:
            import iconic_games as ig
            entry = ig.detect_and_record(home, away, hs, ag, sim)
            if entry:
                s.add(self.n, self.day, "iconic",
                      ["iconic_games", "rivalry_engine"],
                      f"ICONIC GAME: {entry.get('label', entry.get('kind', '?'))} "
                      f"vs {opp.team_name} ({us}-{them})",
                      str(entry.get("narrative", entry))[:300])
        except Exception:
            pass
        # rivalry-night chain: tension -> brawl roll -> record -> fallout
        try:
            from reputation_system import (game_tension, brawl_probability,
                                           record_brawl_game)
            rivs = getattr(self.lg, "rivalries", None) or []
            tension = game_tension(home, away, rivs)
            if tension >= 30:
                bp = brawl_probability(tension, blowout=abs(us - them) >= 4)
                if random.random() < bp:
                    recs = record_brawl_game(rivs, home, away, None, None,
                                             aggressor=random.choice(["a", "b"]),
                                             fights=random.randint(3, 5))
                    s.add(self.n, self.day, "brawl",
                          ["rivalry_engine", "controversy_system",
                           "reputation_system"],
                          f"LINE BRAWL vs {opp.team_name} (tension {tension})",
                          (recs[1].get("story", "") if len(recs) > 1 else "")[:220])
        except Exception:
            pass
        # blowouts / thrillers
        if abs(us - them) >= 5:
            s.add(self.n, self.day, "game", ["sim"],
                  f"{'Rout!' if won else 'Humiliated'} {us}-{them} vs {opp.team_name}",
                  f"Toronto {'wins' if won else 'loses'} big.")
        elif abs(us - them) == 1:
            s.add(self.n, self.day, "game", ["sim"],
                  f"{'Thriller!' if won else 'Heartbreaker'} {us}-{them} vs {opp.team_name}",
                  "One-goal game.")
        # brawls / rivalry flashes from events
        try:
            for e in (events or []):
                ev = str(e.get("event", ""))
                if "rawl" in ev or "ight" in ev:
                    s.add(self.n, self.day, "brawl",
                          ["rivalry_engine", "sim"],
                          f"Line brawl vs {opp.team_name} ({us}-{them})",
                          str(e.get("details", e))[:220])
                    break
        except Exception:
            pass
        # hat tricks / notable
        try:
            for ne in (notable or []):
                if isinstance(ne, dict) and ne.get("event") in ("Hat Trick",):
                    p = ne.get("player")
                    s.add(self.n, self.day, "milestone", ["sim"],
                          f"HAT TRICK: {p.full_name} vs {opp.team_name}",
                          f"{us}-{them} final.")
        except Exception:
            pass

    def _monthly_hooks(self, month, ugp):
        s, user, lg = self.story, self.user, self.lg
        # waivers across the league
        try:
            import waiver_logic as wl
            wl.process_ai_waivers(lg, app=None)
        except Exception as e:
            s.bug(self.n, "waivers", f"process_ai_waivers failed: {e}", False,
                  "waiver_logic.py")
        # morale snapshot for the user team
        try:
            import dressing_room as dr
            room = getattr(user, "dressing_room", None)
            if room is not None:
                s.add(self.n, self.day, "morale", ["dressing_room", "morale"],
                      f"Room check (month {month}): morale snapshot taken", "")
        except Exception:
            pass
        # analytics hub: monthly department briefing
        if month % 3 == 1:
            try:
                import analytics_hub as ah
                games = ah.team_games(user)
                if games:
                    rec = games[-1]
                    s.add(self.n, self.day, "analytics",
                          ["analytics_hub"],
                          f"Analytics briefing: {ah.game_label(rec, user.team_name)} "
                          f"({len(games)} games tracked)", "")
            except Exception as e:
                s.bug(self.n, "analytics hub", f"{e}", False, "analytics_hub.py")
        # press conference every other month
        if month % 2 == 0:
            try:
                import media_engine as me
                me.ensure_media_state(lg)
                s.add(self.n, self.day, "presser", ["media_engine"],
                      f"Monthly presser: {self.strategy} message",
                      "GM faces the Toronto media.")
            except Exception as e:
                s.bug(self.n, "presser", f"media_engine failed: {e}", False,
                      "media_engine.py")
        # trade deadline (March): user + AI moves
        if month == 3 and not getattr(self, "_deadline_done", False):
            self._deadline_done = True
            self._trade_deadline()
        # All-Star (February)
        if month == 2 and not getattr(self, "_asg_done", False):
            self._asg_done = True
            self._all_star()

    # ------------------------------------------------------- trade deadline
    def _trade_deadline(self):
        s, lg, user = self.story, self.lg, self.user
        s.add(self.n, self.day, "deadline", ["trade_engine"],
              f"Trade deadline: Toronto is {self.strategy}", "")
        try:
            import trade_engine as te
        except Exception as e:
            s.bug(self.n, "trades", f"trade_engine import failed: {e}", False,
                  "trade_engine.py")
            return
        # user-team move per strategy
        try:
            if self.strategy in ("win-now", "all-in"):
                self._user_buy(te)
            elif self.strategy == "rebuild":
                self._user_sell(te)
            else:
                s.add(self.n, self.day, "deadline", ["trade_engine"],
                      "Toronto stands pat at the deadline", "Retool year: no moves.")
        except Exception as e:
            s.bug(self.n, "user trade", f"deadline trade failed: {e}\n"
                  f"{traceback.format_exc()[-400:]}", False, "trade_engine.py:1807")
        # a few AI deadline deals for league flavor
        try:
            self._ai_deadline_deals(te, n=3)
        except Exception as e:
            s.bug(self.n, "AI trades", f"AI deadline deals failed: {e}", False,
                  "trade_engine.py")

    def _user_buy(self, te):
        s, lg, user = self.story, self.lg, self.user
        # find best available veteran on a selling team
        sellers = [t for t in nhl_teams(lg)
                   if lg.standings[t.team_name]["Points"] < lg.standings[user.team_name]["Points"] - 10]
        if not sellers:
            return
        seller = max(sellers, key=lambda t: lg.standings[t.team_name]["Points"])
        cands = [p for p in seller.roster
                 if p.primary_position.name != "GOALIE" and ovr(p) >= 78
                 and not getattr(p.contract, "no_movement_clause", False)]
        if not cands:
            return
        target = max(cands, key=ovr)
        # price: our 1st-round pick + a prospect
        picks = [pk for pk in user.get_picks_for_year(self.year + 1)
                 if getattr(pk, "round", 0) == 1]
        if not picks:
            return
        pick = picks[0]
        res = te.execute_trade(user, seller, [pick], [target],
                               date_str=str(self.day), league=lg)
        summary = getattr(res, "summary", "")
        if "BLOCKED" in summary and "salary cap" in summary:
            # fallback: salary-neutral hockey trade (roster player + pick)
            s.add(self.n, self.day, "trade_blocked", ["trade_engine"],
                  f"Deadline buy blocked: {target.full_name}", summary[:200])
            return self._user_swap(te, seller, target, pick)
        if "BLOCKED" in summary:
            s.add(self.n, self.day, "trade_blocked", ["trade_engine"],
                  f"Deadline buy blocked: {target.full_name}", summary[:200])
        else:
            self.trades_made.append((target.full_name, seller.team_name))
            ensure_lineup(user)
            s.add(self.n, self.day, "trade", ["trade_engine"],
                  f"TRADE: Toronto acquires {target.full_name} ({ovr(target):.0f}) "
                  f"from {seller.team_name} for 1st-round pick",
                  summary[:220])

    def _user_swap(self, te, seller, target, pick):
        """Salary-neutral fallback: move a comparable-salary roster player
        with the pick so the cap stays legal."""
        s, lg, user = self.story, self.lg, self.user
        tsal = getattr(getattr(target, "contract", None), "salary", 0) or 0
        mates = [p for p in user.roster
                 if p.primary_position.name != "GOALIE"
                 and abs((getattr(getattr(p, "contract", None), "salary", 0) or 0) - tsal) < 2_000_000
                 and ovr(p) < ovr(target)]
        if not mates:
            return
        mate = max(mates, key=ovr)
        res = te.execute_trade(user, seller, [mate, pick], [target],
                               date_str=str(self.day), league=lg)
        summary = getattr(res, "summary", "")
        if "BLOCKED" not in summary:
            self.trades_made.append((target.full_name, seller.team_name))
            ensure_lineup(user)
            s.add(self.n, self.day, "trade", ["trade_engine"],
                  f"TRADE: Toronto acquires {target.full_name} ({ovr(target):.0f}) "
                  f"from {seller.team_name} for {mate.full_name} + 1st-round pick",
                  summary[:220])
        else:
            s.add(self.n, self.day, "trade_blocked", ["trade_engine"],
                  f"Swap also blocked: {target.full_name}", summary[:200])

    def _user_sell(self, te):
        s, lg, user = self.story, self.lg, self.user
        # move the best pending-UFA veteran for picks
        vets = [p for p in user.roster
                if getattr(getattr(p, "contract", None), "years_remaining", 9) <= 1
                and ovr(p) >= 75 and p.primary_position.name != "GOALIE"]
        if not vets:
            vets = sorted([p for p in user.roster if p.primary_position.name != "GOALIE"],
                          key=ovr, reverse=True)[:1]
        if not vets:
            return
        target = max(vets, key=ovr)
        buyers = [t for t in nhl_teams(lg)
                  if lg.standings[t.team_name]["Points"] > lg.standings[user.team_name]["Points"] + 10]
        if not buyers:
            return
        buyer = max(buyers, key=lambda t: lg.standings[t.team_name]["Points"])
        picks = [pk for pk in buyer.get_picks_for_year(self.year + 1)
                 if getattr(pk, "round", 0) in (1, 2)]
        if not picks:
            return
        res = te.execute_trade(buyer, user, [picks[0]], [target],
                               date_str=str(self.day), league=lg)
        summary = getattr(res, "summary", "")
        if "BLOCKED" not in summary:
            self.trades_made.append((target.full_name, "to " + buyer.team_name))
            ensure_lineup(user)
            s.add(self.n, self.day, "trade", ["trade_engine"],
                  f"TRADE: Toronto sells {target.full_name} ({ovr(target):.0f}) "
                  f"to {buyer.team_name} for a pick", summary[:220])

    def _ai_deadline_deals(self, te, n=3):
        lg, s = self.lg, self.story
        made = 0
        teams = nhl_teams(lg)
        for _ in range(n * 6):
            if made >= n:
                break
            a, b = random.sample(teams, 2)
            if a is self.user or b is self.user:
                continue
            pa = [p for p in a.roster if p.primary_position.name != "GOALIE"
                  and 74 <= ovr(p) <= 82]
            pb = [p for p in b.roster if p.primary_position.name != "GOALIE"
                  and 74 <= ovr(p) <= 82]
            if not pa or not pb:
                continue
            res = te.execute_trade(a, b, [random.choice(pa)], [random.choice(pb)],
                                   date_str=str(self.day), league=lg)
            if "BLOCKED" not in getattr(res, "summary", ""):
                made += 1
                s.add(self.n, self.day, "trade", ["trade_engine"],
                      f"Deadline deal: {a.team_name} ↔ {b.team_name}", "")
