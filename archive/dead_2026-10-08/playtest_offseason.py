# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
# playtest_offseason.py -- development rollover, lottery, draft, ELCs, FA,
# extensions, coaching carousel (monkey-patched onto SeasonDriver)
import random, traceback
from datetime import date
from playtest_driver import (StoryLog, nhl_teams, get_team, ensure_lineup, ovr,
                             USER_TEAM_NAME, STRATEGIES)
from playtest_season import SeasonDriver
from game_classes import PlayerPosition, Contract
import draft_night

# ------------------------------------------------------- season rollover
def _offseason(self):
    s, lg, user = self.story, self.lg, self.user
    s.add(self.n, date(self.year + 1, 4, 20), "offseason", ["game_classes"],
          "Offseason begins", "")
    # 0. coaching carousel FIRST: end_of_season() zeroes lg.standings, so
    # any points-based logic must run before the rollover.
    self._coaching_carousel()
    # 0b. draft lottery BEFORE the wipe too: draft_lottery reads
    # lg.standings points/wins, which end_of_season() zeroes. Running it
    # after the wipe gave every team identical (zero) odds and a fixed
    # draft order. The game's own flow lotteries before the rollover.
    try:
        lg.simulate_draft_lottery(self.year + 1)
        s.add(self.n, date(self.year + 1, 5, 10), "lottery", ["draft_lottery"],
              "Draft lottery held", "")
    except Exception as e:
        s.bug(self.n, "lottery", f"simulate_draft_lottery failed: {e}", False,
              "game_classes.py:7558")
    # 1. development + aging + ELC slides + contract rollover
    try:
        lg.end_of_season()
        s.add(self.n, date(self.year + 1, 4, 21), "development",
              ["prospect_development", "game_classes"],
              "Development rollover complete (aging, ELC slides, farm evals)", "")
    except Exception as e:
        s.bug(self.n, "end_of_season", f"lg.end_of_season failed: {e}\n"
              f"{traceback.format_exc()[-400:]}", False, "game_classes.py:6220")
    # 2. retirements flavor (old players hang them up)
    try:
        retired = 0
        for t in nhl_teams(lg):
            for p in list(t.roster):
                if getattr(p, "age", 0) >= 39 and random.random() < 0.5:
                    t.roster.remove(p)
                    retired += 1
                    if t is user:
                        s.add(self.n, date(self.year + 1, 5, 1), "retirement",
                              ["game_classes"],
                              f"{p.full_name} retires at {p.age}", "")
        if retired:
            s.add(self.n, date(self.year + 1, 5, 1), "retirement", ["game_classes"],
                  f"{retired} players retire league-wide", "")
    except Exception as e:
        s.bug(self.n, "retirements", f"{e}", False, "")
    # 3. draft lottery -- moved to step 0b (before end_of_season zeroes
    # lg.standings); see above.
    # 4. entry draft
    self._entry_draft()
    # 5. sign ELCs (user team + AI)
    self._sign_elcs()
    # 6. free agency
    self._free_agency()
    # 7. extensions
    self._extensions()
    # 8. roll the calendar
    try:
        lg.season_year = self.year + 1
        lg.initialize_standings()
        lg.generate_schedule(lg.season_year)
    except Exception as e:
        s.bug(self.n, "new season setup", f"{e}", False, "")

SeasonDriver._offseason = _offseason

# ------------------------------------------------------------ entry draft
def _entry_draft(self):
    s, lg, user = self.story, self.lg, self.user
    try:
        from draft_generator import generate_draft_class
        lg.draft_prospects = generate_draft_class(
            num_prospects=224, quality="Normal")
        lg.draft_prospects_year = self.year + 1
    except Exception as e:
        s.bug(self.n, "draft class", f"generate_draft_class failed: {e}", False,
              "draft_generator.py")
        return
    # user scouting flavor: scout the top prospects
    try:
        import analytics_scouting as asc
        s.add(self.n, date(self.year + 1, 6, 1), "scouting",
              ["analytics_scouting"],
              "Amateur scouting meetings: board stacked", "")
    except Exception:
        pass
    try:
        picks = draft_night.conduct_entry_draft(lg, self.year + 1, app=None,
                                                seed=1000 + self.n)
    except Exception as e:
        s.bug(self.n, "entry draft",
              f"conduct_entry_draft failed: {e}\n{traceback.format_exc()[-400:]}",
              False, "draft_night.py:248")
        return
    mine = [(o, p) for (tn, o, p) in picks if tn == user.team_name]
    for o, p in mine[:7]:
        s.add(self.n, date(self.year + 1, 6, 28), "draft_pick",
              ["draft_night", "draft_generator"],
              f"Toronto drafts {p.full_name} at #{o} "
              f"({p.primary_position.name}, {getattr(p, 'potential_grade', '?')})",
              "")
    # draft-day trades flavor
    try:
        import draft_day_trades as ddt
        ddt.run_draft_day_trading(lg, self.year + 1, app=None, max_deals=2)
    except Exception:
        pass
    s.add(self.n, date(self.year + 1, 6, 28), "draft",
          ["draft_night"],
          f"Entry draft complete: {len(picks)} picks made", "")

SeasonDriver._entry_draft = _entry_draft

# --------------------------------------------------------------- ELCs
def _sign_elcs(self):
    s, lg, user = self.story, self.lg, self.user
    signed = 0
    try:
        for t in nhl_teams(lg):
            for p in list(getattr(t, "prospects", [])):
                if getattr(p, "drafted_year", None) == self.year + 1:
                    try:
                        ok = lg.sign_drafted_prospect(t, p)
                        if ok:
                            signed += 1
                            if t is user:
                                s.add(self.n, date(self.year + 1, 7, 5), "elc",
                                      ["game_classes"],
                                      f"Toronto signs {p.full_name} to ELC", "")
                    except Exception:
                        pass
        s.add(self.n, date(self.year + 1, 7, 5), "elc", ["game_classes"],
              f"{signed} ELCs signed league-wide", "")
    except Exception as e:
        s.bug(self.n, "ELC signings", f"{e}", False, "game_classes.py:6989")

SeasonDriver._sign_elcs = _sign_elcs

# -------------------------------------------------------- free agency
def _free_agency(self):
    s, lg, user = self.story, self.lg, self.user
    try:
        from salary_cap_system import base_ask_dollars
    except Exception:
        base_ask_dollars = None
    # expire contracts -> free agents
    try:
        for t in nhl_teams(lg):
            for p in list(t.roster):
                c = getattr(p, "contract", None)
                if c is not None and getattr(c, "years_remaining", 1) <= 0:
                    t.roster.remove(p)
                    lg.free_agents.append(p)
    except Exception as e:
        s.bug(self.n, "FA expiry", f"{e}", False, "")
    # sign: each team fills to 21 skaters + 2 goalies
    total_signed = 0
    user_signed = []
    for t in nhl_teams(lg):
        try:
            need_f = 13 - len([p for p in t.roster if p.primary_position.name in
                               ("LEFT_WING", "CENTER", "RIGHT_WING")])
            need_d = 7 - len([p for p in t.roster if p.primary_position.name in
                              ("LEFT_DEFENSE", "RIGHT_DEFENSE", "DEFENSE")])
            need_g = 2 - len([p for p in t.roster
                              if p.primary_position.name == "GOALIE"])
            need = max(0, need_f) + max(0, need_d) + max(0, need_g)
            if need <= 0:
                continue
            cap = getattr(t, "cap_space", 50_000_000)
            # sort FAs by overall, take affordable fits
            cands = sorted(lg.free_agents, key=ovr, reverse=True)
            for p in cands:
                if need <= 0 or cap <= 1_000_000:
                    break
                ask = base_ask_dollars(int(ovr(p)), getattr(p, "age", 27)) \
                    if base_ask_dollars else int(ovr(p) * 90000)
                ask = min(ask, int(cap * 0.6))
                if ask < 775_000:
                    ask = 775_000
                yrs = 1 if getattr(p, "age", 27) >= 34 else random.randint(1, 4)
                p.contract = Contract(salary=ask, years_remaining=yrs)
                t.add_player(p, "roster")
                try:
                    lg.free_agents.remove(p)
                except ValueError:
                    pass
                cap -= ask
                need -= 1
                total_signed += 1
                if t is user:
                    user_signed.append((p.full_name, ask, yrs, p.primary_position.name))
        except Exception as e:
            s.bug(self.n, "FA signing", f"{t.team_name}: {e}", False, "")
            continue
    for name, ask, yrs, pos in user_signed[:6]:
        s.add(self.n, date(self.year + 1, 7, 10), "signing",
              ["salary_cap_system"],
              f"FA signing: {name} ({pos}) {yrs}y ${ask/1e6:.2f}M", "")
    s.add(self.n, date(self.year + 1, 7, 15), "free_agency",
          ["salary_cap_system", "ai_team_management"],
          f"Free agency: {total_signed} signings league-wide", "")
    # user-team big-fish behavior per strategy
    if self.strategy in ("win-now", "all-in") and user_signed:
        s.add(self.n, date(self.year + 1, 7, 10), "storyline", ["media_engine"],
              "Toronto active on July 1", f"Signed {len(user_signed)} free agents.")

SeasonDriver._free_agency = _free_agency

# ---------------------------------------------------------- extensions
def _extensions(self):
    s, lg, user = self.story, self.lg, self.user
    try:
        from salary_cap_system import base_ask_dollars
    except Exception:
        base_ask_dollars = None
    extended = 0
    for t in nhl_teams(lg):
        try:
            cap = getattr(t, "cap_space", 50_000_000)
            for p in t.roster:
                c = getattr(p, "contract", None)
                if c is None or getattr(c, "years_remaining", 9) != 1:
                    continue
                if getattr(p, "age", 30) >= 36 or ovr(p) < 72:
                    continue
                ask = base_ask_dollars(int(ovr(p)), getattr(p, "age", 28)) \
                    if base_ask_dollars else int(ovr(p) * 95000)
                if ask > cap - 2_000_000:
                    continue
                yrs = random.randint(2, 5)
                p.contract = Contract(salary=ask, years_remaining=yrs)
                cap -= ask
                extended += 1
                if t is user:
                    s.add(self.n, date(self.year + 1, 8, 1), "extension",
                          ["salary_cap_system"],
                          f"Extension: {p.full_name} {yrs}y ${ask/1e6:.2f}M", "")
        except Exception:
            continue
    s.add(self.n, date(self.year + 1, 8, 5), "extensions",
          ["salary_cap_system"], f"{extended} extensions signed league-wide", "")

SeasonDriver._extensions = _extensions

# ---------------------------------------------------- coaching carousel
def _coaching_carousel(self):
    s, lg, user = self.story, self.lg, self.user
    # rank teams; bottom-5 GMs get itchy, Cup miss + bad year = hot seat
    order = sorted(nhl_teams(lg), key=lambda t: lg.standings[t.team_name]["Points"])
    fired = 0
    champ_name = getattr(getattr(self, "_champ", None), "team_name", "")
    for t in order[:6]:
        if t.team_name == champ_name:
            continue  # never fire the Cup champion's coach
        if lg.standings[t.team_name]["Points"] >= 95:
            continue  # 95+ point teams keep their coach
        if random.random() < 0.5:
            try:
                import dressing_room as dr
                out = dr.fire_coach(t, reason="fired",
                                    date_str=str(date(self.year + 1, 6, 1)),
                                    league=lg)
                if out:
                    fired += 1
                    nm = out.get("name", "coach")
                    s.add(self.n, date(self.year + 1, 6, 2), "coaching",
                          ["dressing_room", "reputation_system"],
                          f"{t.team_name} fire {nm}",
                          str(out.get("room_reaction", ""))[:180])
                    if t is user:
                        s.add(self.n, date(self.year + 1, 6, 2), "coaching",
                              ["dressing_room"],
                              "LEAFS FIRE THE COACH — Toronto media frenzy", "")
            except Exception as e:
                s.bug(self.n, "fire_coach", f"{t.team_name}: {e}", False,
                      "dressing_room.py:3236")
    # user hot seat: miss playoffs twice running or sub-.500 = danger
    try:
        pts = lg.standings[user.team_name]["Points"]
        if pts < 85 and self.strategy == "win-now" and random.random() < 0.4:
            import dressing_room as dr
            out = dr.fire_coach(user, reason="fired",
                                date_str=str(date(self.year + 1, 6, 1)), league=lg)
            if out:
                s.add(self.n, date(self.year + 1, 6, 3), "coaching",
                      ["dressing_room", "media_engine"],
                      f"LEAFS FIRE {out.get('name','THE COACH')} after {pts}-pt season",
                      "Ownership loses patience.")
    except Exception:
        pass
    if fired:
        s.add(self.n, date(self.year + 1, 6, 10), "coaching", ["dressing_room"],
              f"Coaching carousel: {fired} coaches fired league-wide", "")

SeasonDriver._coaching_carousel = _coaching_carousel
