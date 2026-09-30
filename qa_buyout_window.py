# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: the June 15-30 buyout window (buyout_window.py).

- AI teams: cap-strapped + dead weight -> bought out; comfortable teams,
  NMC holders, franchise pieces -> untouched.
- User team: nothing auto-executed; interactive inbox message queued with
  the math; apply_buyout_decision executes through the shared helper.
- execute_buyout writes the same cap-hit schedule the calculator used to.
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import buyout_window as bw
from game_classes import Team, Player, Contract


def make_player(name, age, ovr, salary, yrs_left, nmc=False, elc=False):
    from game_classes import PlayerPosition
    first, _, last = name.partition(" ")
    p = Player(first or name, last or "X", age, PlayerPosition.CENTER)
    p.age = age
    p.id = f"id-{name}"
    p.team_name = "X"
    p.overall_rating = lambda ovr=ovr: ovr  # instance shadow for the fake
    c = Contract()
    c.salary = salary
    c.years_remaining = yrs_left
    c.no_movement_clause = nmc
    c.entry_level = elc
    p.contract = c
    return p


def make_team(name, players, user=False):
    t = Team(name, name, "D", "C")
    t.league_name = "National Hockey League"
    t.roster = list(players)
    t.is_user_team = user
    return t


def cap_space_of(team):
    from salary_cap_system import cap_breakdown
    return int(cap_breakdown(team).get("space", 0))


passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {detail}")


def main():
    # --- AI team 1: cap-strapped ($2M space) with a dead-weight vet ------
    vet = make_player("Washed Vet", 33, 76, 6_000_000, 2)
    filler = [make_player(f"F{i}", 27, 82, 6_400_000, 3) for i in range(15)]
    # 15 x 6.4M + 6M = 102M -> ~2M space under 104M
    t1 = make_team("Strapped", [vet] + filler)
    s1 = cap_space_of(t1)
    print(f"  (Strapped space: ${s1:,})")

    # --- AI team 2: comfortable ($30M+ space), same dead-weight profile --
    vet2 = make_player("Washed Vet 2", 33, 76, 6_000_000, 2)
    cheap = [make_player(f"C{i}", 25, 76, 4_500_000, 3) for i in range(15)]
    t2 = make_team("Comfortable", [vet2] + cheap)
    s2 = cap_space_of(t2)
    print(f"  (Comfortable space: ${s2:,})")

    # --- AI team 3: strapped but the vet has an NMC ----------------------
    vet3 = make_player("NMC Vet", 34, 75, 6_500_000, 2, nmc=True)
    t3 = make_team("NMC Club", [vet3] + [make_player(f"N{i}", 27, 82, 6_400_000, 3)
                                        for i in range(15)])

    # --- AI team 4: strapped but the expensive guy is a star ------------
    star = make_player("Franchise Star", 29, 90, 11_000_000, 4)
    t4 = make_team("Star Club", [star] + [make_player(f"S{i}", 27, 82, 5_800_000, 3)
                                         for i in range(15)])

    # --- User team: one candidate ---------------------------------------
    uvet = make_player("User Vet", 32, 77, 5_500_000, 2)
    ut = make_team("User Club", [uvet] + [make_player(f"U{i}", 26, 79, 5_000_000, 3)
                                          for i in range(15)], user=True)

    inbox = []

    class FakeApp:
        def __init__(self, league):
            self.league = league
            self.user_team = ut

        def send_email_to_user(self, msg):
            inbox.append(msg)

        def add_news(self, txt):
            pass

    league = SimpleNamespace(teams=[t1, t2, t3, t4, ut],
                             season_year=2026, user_team=ut,
                             free_agents=[])
    app = FakeApp(league)

    import random
    summary = bw.process_buyout_window(league, app=app,
                                       rng=random.Random(7))

    bought = {(b["team"], b["player"]) for b in summary["ai_buyouts"]}
    print(f"  (buyouts: {sorted(bought)})")

    check("strapped team's dead weight bought out",
          ("Strapped", "Washed Vet") in bought, str(bought))
    check("comfortable team untouched",
          not any(t == "Comfortable" for t, _ in bought), str(bought))
    check("NMC player not bought out",
          not any(t == "NMC Club" for t, _ in bought), str(bought))
    check("franchise star not bought out",
          not any(t == "Star Club" for t, _ in bought), str(bought))
    check("vet removed from roster + became FA",
          vet not in t1.roster and vet.team_name == "Free Agent")

    # Cap-hit schedule written, keyed to the window year (2027).
    hits = getattr(t1, "buyout_cap_hits", {}) or {}
    check("dead-cap hits keyed to window year",
          2027 in hits and hits[2027] > 0, str(hits))
    # Buyout math: 2/3 of remaining salary over 2x term.
    # 33yo: 2/3 * 12M = 8M over 4 yrs = 2M/yr; year-1 savings 6M-2M=4M.
    check("buyout math sane",
          hits.get(2027) == 2_000_000, f"2027 hit={hits.get(2027)}")
    y1 = [b for b in summary["ai_buyouts"]
          if b["team"] == "Strapped"][0]["savings_y1"]
    check("year-1 savings reported", y1 == 4_000_000, f"savings={y1}")

    # --- User team: message queued, nothing executed --------------------
    check("user inbox message queued",
          len(inbox) == 1 and inbox[0].action_type == "buyout_window",
          f"inbox={len(inbox)}")
    msg = inbox[0]
    check("message requires response",
          bool(msg.requires_response))
    check("user vet NOT auto-bought-out",
          uvet in ut.roster and uvet.team_name != "Free Agent")
    cards = (msg.action_data or {}).get("cards", [])
    check("candidate card has the math",
          cards and cards[0]["player_id"] == "id-User Vet"
          and cards[0]["dead_weight"] is True
          and cards[0]["savings_y1"] > 0
          and cards[0]["annual_dead"] > 0,
          str(cards[0] if cards else cards))

    # --- apply_buyout_decision executes via the shared helper -----------
    class FakeMainApp(FakeApp):
        def update_all_views(self):
            pass

    mapp = FakeMainApp(league)
    mapp.user_team = ut
    # bind the real method
    from types import MethodType
    mapp.apply_buyout_decision = MethodType(
        __import__("main").HockeyManagerGUI.apply_buyout_decision, mapp)
    mapp._find_inbox_player = MethodType(
        __import__("main").HockeyManagerGUI._find_inbox_player, mapp)

    ok = mapp.apply_buyout_decision(msg, "id-User Vet", True)
    check("buyout decision executes", ok is True)
    for cd in list((msg.action_data or {}).get("cards", [])):
        pid = str(cd.get("player_id"))
        if pid not in ((msg.action_data or {}).get("decided", {}) or {}):
            mapp.apply_buyout_decision(msg, pid, False)
    check("user vet bought out",
          uvet not in ut.roster and uvet.team_name == "Free Agent")
    uhits = getattr(ut, "buyout_cap_hits", {}) or {}
    check("user dead-cap hits written", uhits.get(2027, 0) > 0, str(uhits))
    check("message marked done when all decided",
          bool(msg.action_done))

    # --- shared helper == calculator math --------------------------------
    from windows import buyout_schedule
    total, annual, byears, rows = buyout_schedule(
        make_player("Math Check", 33, 76, 6_000_000, 2))
    check("calculator math unchanged (2/3 over 2x term)",
          total == 8_000_000 and annual == 2_000_000 and byears == 4,
          f"{total} {annual} {byears}")

    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
