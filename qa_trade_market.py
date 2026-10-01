# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_trade_market.py — QA for the AI trade market (trade_market.py).

Asserts DYNAMIC properties (no fixed trade-volume counts), per Chris's
directive: sellers list more than buyers, cooldowns/caps respected,
trade-request paths resolve, deals stay cap-legal, blocks are real,
shortlist JPA bands hold, nudges fire.

Usage:  python3 qa_trade_market.py
Exit 0 = all green. Prints PASS/FAIL lines with counts.
"""
import json
import random
import sys
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import trade_market as tm
import trade_engine as te
import trade_storylines as tsl
from game_classes import Player, Team, League, Contract, DraftPick, PlayerPosition

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail and not cond else ""))


SKATER_ATTRS = [
    "skating", "shooting", "shooting_accuracy", "shooting_power", "passing",
    "passing_accuracy", "passing_creativity", "stickhandling", "deking",
    "one_timer", "slapshot", "wristshot", "backhand", "screen_shots",
    "offensive_awareness", "defensive_awareness", "hockey_iq", "vision",
    "faceoffs", "strength", "endurance", "composure", "determination",
    "teamwork", "leadership", "discipline", "consistency", "loose_puck",
    "off_the_puck",
]


def mk_player(fn, ln, pos, age, ovr, salary, yrs=2, grade="C",
              morale=70, ambition="contender"):
    p = Player(fn, ln, age, pos)
    for a in SKATER_ATTRS:
        if hasattr(p, a):
            setattr(p, a, ovr)
    p.contract = Contract(salary=salary, years_remaining=yrs)
    p.potential_grade = grade
    p.morale = morale
    p.ambition = ambition
    return p


def mk_team(name, city, conf, players, picks_by_year=None, gm_aggr=0.5):
    t = Team(name, city, "Metro", conf)
    t.roster = list(players)
    t.draft_picks = picks_by_year or {}
    t.gm_profile = SimpleNamespace(aggression=gm_aggr)
    return t


def mk_pick(team_name, year, rnd):
    return DraftPick(year=year, round=rnd, original_team=team_name,
                     current_team=team_name)


def build_league(seed=7):
    """6-team league: teams[0..1] sellers (bottom), teams[2..5] buyers (top)."""
    random.seed(seed)
    teams = []
    conf = "East"
    for i, cname in enumerate(["Ruin City", "Cellar Town"]):
        players = [mk_player(f"Sell{i}", f"Man{j}", PlayerPosition.CENTER,
                             30 + j, 74 - j, 4_000_000, morale=45)
                   for j in range(6)]
        players[0].transfer_requested = True  # one request each seller
        t = mk_team(f"Seller{i}", cname, conf, players,
                    {2027: [mk_pick(f"Seller{i}", 2027, r) for r in (1, 2, 3)]},
                    gm_aggr=0.4)
        teams.append(t)
    for i, cname in enumerate(["Top Town", "Win City", "Cupburg", "First Place"]):
        players = [mk_player(f"Buy{i}", f"Guy{j}", PlayerPosition.CENTER,
                             26, 82 - j, 6_000_000, morale=80)
                   for j in range(6)]
        pros = mk_player(f"Pro{i}", "Spect", PlayerPosition.LEFT_WING,
                         20, 72, 925_000, grade="B", morale=75)
        t = mk_team(f"Buyer{i}", cname, conf, players + [pros],
                    {2027: [mk_pick(f"Buyer{i}", 2027, r) for r in (1, 2)],
                     2028: [mk_pick(f"Buyer{i}", 2028, 1)]},
                    gm_aggr=0.7)
        teams.append(t)
    league = League("QA League", season_year=2026)
    league.teams = teams
    pts = {"Buyer0": 70, "Buyer1": 65, "Buyer2": 60, "Buyer3": 55,
           "Seller0": 30, "Seller1": 25}
    league.standings = {n: {"Points": p, "GP": 40} for n, p in pts.items()}
    league.game_results = []
    return league


def build_app(league, today):
    user_team = league.teams[2]  # Buyer0
    user_team.is_user_team = True
    return SimpleNamespace(
        league=league, user_team=user_team, current_date=today,
        game_manager=None, _trade_market_inbox=[],
        add_news=lambda text, category="Trade Market": None,
    )


def salary_total(team):
    return sum(getattr(getattr(p, "contract", None), "salary", 0) or 0
               for p in team.roster)


def clear_shortlist_store():
    """The unified shortlist persists to saves/shortlist.json (legacy
    global) and saves/shortlists/<save-key>.json (per-save, D15.5) --
    reset both between tests so they can't pollute each other."""
    import os
    import shutil
    p = os.path.join("saves", "shortlist.json")
    try:
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass
    d = os.path.join("saves", "shortlists")
    try:
        if os.path.isdir(d):
            shutil.rmtree(d)
    except Exception:
        pass


# ---------------------------------------------------------------- tests

def t_market_init_and_clear():
    league = build_league()
    m = tm.get_market(league)
    check("market lazy-inits dict with listings", isinstance(m.get("listings"), list))
    check("market has cooldown maps", isinstance(m.get("deal_cooldown"), dict))
    tm.clear_for_new_season(league)
    check("clear wipes listings", tm.get_market(league)["listings"] == [])
    check("clear wipes blocks", tm.get_trade_blocks(league) == {})


def t_json_safe():
    """Market + blocks + shortlist dicts must survive save/load (JSON types)."""
    clear_shortlist_store()
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    market = tm.get_market(league)
    tm._auto_list(app, league, market, app.current_date, False)
    team = league.teams[2]
    tm.add_to_shortlist(team, team.roster[0], added_by="user", note="need a center")
    tm.refresh_trade_blocks(app, league)
    try:
        json.dumps(tm.get_market(league))
        json.dumps(tm.get_trade_blocks(league))
        json.dumps(getattr(team, "scout_shortlist", []))
        json.dumps(tm.get_unified_targets())
        ok = True
    except TypeError as e:
        ok = False
        print("   json error:", e)
    check("market/blocks/shortlist are JSON-serializable", ok)


def t_heat_monotone():
    """Deadline heat rises monotonically toward the deadline; guardrails
    scale with it (no flat ramp mode)."""
    league = build_league()
    app = build_app(league, date(2026, 10, 1))
    days = [90, 60, 45, 30, 21, 14, 7, 1, 0]
    heats = []
    with patch.object(tm, "_days_to_deadline",
                      side_effect=lambda a, l, t: days[len(heats)]):
        for _ in days:
            heats.append(tm.deadline_heat(app, league, date(2026, 10, 1)))
    mono = all(b >= a for a, b in zip(heats, heats[1:]))
    check("heat monotone non-decreasing toward deadline", mono,
          str([round(h, 2) for h in heats]))
    check("heat ~0 far out", heats[0] < 0.05, f"{heats[0]}")
    check("heat hits 1.0 at deadline", heats[-1] == 1.0, f"{heats[-1]}")
    params = [tm._heat_params(h) for h in heats]
    check("listing caps rise with heat",
          all(b["max_team"] >= a["max_team"] and b["league_cap"] >= a["league_cap"]
              for a, b in zip(params, params[1:])))
    check("bidding window shortens with heat",
          all(b["window"] <= a["window"] for a, b in zip(params, params[1:])))
    check("escalation multiplier rises with heat",
          all(b["esc_mult"] >= a["esc_mult"] for a, b in zip(params, params[1:])))
    check("rumor cap rises with heat",
          all(b["rumor_cap"] >= a["rumor_cap"] for a, b in zip(params, params[1:])))
    check("decay multiplier rises with heat",
          all(b["decay_mult"] >= a["decay_mult"] for a, b in zip(params, params[1:])))


def t_heat_beats():
    """'Decision time' stories fire once per threshold as heat rises."""
    league = build_league()
    news = []
    app = build_app(league, date(2027, 2, 1))
    app.add_news = lambda s, category="Trade Market": news.append(s)
    market = tm.get_market(league)
    tm._heat_beat_stories(app, league, market, 0.4, app.current_date)
    check("no beat below first threshold", len(news) == 0, str(news))
    tm._heat_beat_stories(app, league, market, 0.6, app.current_date)
    check("first beat fires", len(news) == 1, str(news))
    check("first beat names decision time", "ecision time" in news[0], news[0])
    tm._heat_beat_stories(app, league, market, 0.6, app.current_date)
    check("beat not re-fired", len(news) == 1)
    tm._heat_beat_stories(app, league, market, 0.8, app.current_date)
    tm._heat_beat_stories(app, league, market, 0.95, app.current_date)
    check("all three beats fire once each", len(news) == 3, str(news))


def t_stance_flip_block():
    """A buyer->seller stance flip refreshes the block and posts news."""
    import trade_storylines as tsl
    league = build_league()
    news = []
    app = build_app(league, date(2026, 12, 15))
    app.add_news = lambda s, category="Trade Market": news.append(s)
    market = tm.get_market(league)
    team = league.teams[3]  # Buyer1
    with patch.object(tsl, "stance", return_value="buyer"):
        tm.note_situation_change(app, league, market, app.current_date)
    check("stance recorded", market.get("prev_stance", {}).get(team.team_name) == "buyer")
    n0 = len(news)
    with patch.object(tsl, "stance", return_value="seller"):
        tm.note_situation_change(app, league, market, app.current_date)
    check("flip to seller recorded",
          market.get("prev_stance", {}).get(team.team_name) == "seller")
    flip_news = [s for s in news[n0:] if "ecision time" in s and "selling" in s]
    check("stance-flip posts 'decision time' selling news", len(flip_news) >= 1,
          str(news[n0:n0 + 3]))
    blocks = tm.get_trade_blocks(league)
    check("block refreshed on flip", team.team_name in blocks)


def t_injury_block():
    """A long-term injury to a key player refreshes the block + rumor."""
    league = build_league()
    news = []
    app = build_app(league, date(2026, 12, 15))
    app.add_news = lambda s, category="Trade Market": news.append(s)
    market = tm.get_market(league)
    team = league.teams[0]  # Seller0
    key = tm._key_players(team)[0]
    key.is_injured = True
    key.games_remaining_injured = 25
    tm.note_situation_change(app, league, market, app.current_date)
    check("injury flagged once", key.id in market.get("injury_flags", []),
          str(market.get("injury_flags")))
    rumor = [s for s in news if "shopping for help" in s]
    check("injury posts shopping-for-help rumor", len(rumor) >= 1,
          str(news[:3]))
    # Short-term injuries don't move the block.
    news.clear()
    key2 = tm._key_players(team)[1]
    key2.is_injured = True
    key2.games_remaining_injured = 5
    tm.note_situation_change(app, league, market, app.current_date)
    check("short-term injury ignored", key2.id not in market.get("injury_flags", []))


def t_user_block_offer():
    """A user-block player draws a real AI bid delivered as a negotiation
    offer (never auto-sold)."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    user_team = app.user_team  # Buyer0
    piece = mk_player("Block", "Bait", PlayerPosition.LEFT_WING, 27, 78,
                      3_500_000)
    user_team.roster.append(piece)
    user_team.trade_block = [piece]
    market = tm.get_market(league)
    calls = []
    with patch("trade_negotiation.incoming_offer",
               side_effect=lambda a, pt, pkg, player_wanted=None:
               calls.append((pt.team_name, len(pkg)))) as _m:
        tm.process_market(app, league, app.current_date)
    listings = [l for l in market["listings"]
                if l.get("player_id") == piece.id and l["status"] == "open"]
    check("user block becomes a market listing",
          len(listings) == 1 and listings[0].get("source") == "user_block",
          str([(l.get("source"), l["status"]) for l in listings]))
    offered = listings[0].get("user_offer") if listings else None
    check("AI bid recorded on the listing", offered is not None,
          str(offered))
    check("incoming_offer called for the user",
          len(calls) >= 1, str(calls))
    check("piece NOT auto-traded", piece in user_team.roster)
    # Throttle: a second day doesn't spam another offer.
    calls.clear()
    with patch("trade_negotiation.incoming_offer",
               side_effect=lambda a, pt, pkg, player_wanted=None:
               calls.append(pt.team_name)):
        tm.process_market(app, league, app.current_date + timedelta(days=1))
    check("offer throttled (one per week per listing)", len(calls) == 0,
          str(calls))


def t_headliner_package():
    """Superstar pieces need packages: light offers fail the overlay,
    real packages pass."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    seller = league.teams[0]
    # NOTE: Player init randomizes a few attrs outside the fixture's pinned
    # set, so overall_rating() carries noise -- fixtures sit well clear of
    # the 85/83 headliner bar.
    star = mk_player("Quinn", "Hugheslike", PlayerPosition.DEFENSE, 25, 94,
                     9_000_000, yrs=4)
    seller.roster.append(star)
    check("fixture is a headliner", tm._is_headliner(star))
    bidder = league.teams[3]
    # Light offer: one good roster player -- rejected.
    light = [mk_player("Good", "Player", PlayerPosition.CENTER, 28, 82,
                       5_000_000, yrs=3)]
    ok, why = tm._headliner_package_ok(app, league, star, seller, bidder,
                                       light)
    check("light offer on headliner rejected", ok is False, why)
    # Real package: young roster player + 1st + prospect -- accepted.
    young = mk_player("Young", "Gun", PlayerPosition.LEFT_WING, 22, 80,
                      3_000_000, yrs=3)
    pros = mk_player("Top", "Prospect", PlayerPosition.CENTER, 20, 74,
                     925_000, yrs=3, grade="A")
    first = mk_pick(bidder.team_name, 2027, 1)
    ok2, why2 = tm._headliner_package_ok(app, league, star, seller, bidder,
                                         [young, pros, first])
    check("headliner package accepted", ok2 is True, why2)
    # Rental discount: pending-UFA headliner, prospect/young + early pick.
    rental = mk_player("Rent", "Alstar", PlayerPosition.RIGHT_WING, 30, 90,
                       8_000_000, yrs=1)
    check("rental fixture is a headliner", tm._is_headliner(rental))
    second = mk_pick(bidder.team_name, 2027, 2)
    ok3, why3 = tm._headliner_package_ok(app, league, rental, seller,
                                         bidder, [pros, second])
    check("rental package accepted (2 assets + early pick)", ok3 is True, why3)
    # Non-headliner: overlay stays out of the way.
    mid = mk_player("Mid", "Sixer", PlayerPosition.CENTER, 28, 70,
                    4_000_000, yrs=2)
    check("non-headliner fixture below the bar",
          tm._is_headliner(mid) is False, f"ovr={mid.overall_rating()}")
    ok4, _w4 = tm._headliner_package_ok(app, league, mid, seller, bidder,
                                        light)
    check("non-headliner unaffected", ok4 is True)


def t_headliner_exception():
    """The Hall<->Larsson 1-for-1 exception: young + controllable +
    at the seller's clear #1 need."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    seller = league.teams[0]
    hall = mk_player("Taylor", "Halllike", PlayerPosition.LEFT_WING, 24, 90,
                     6_000_000, yrs=4)
    seller.roster.append(hall)
    check("hall fixture is a headliner", tm._is_headliner(hall))
    bidder = league.teams[3]
    larsson = mk_player("Adam", "Larssonlike", PlayerPosition.DEFENSE, 23, 86,
                        4_166_666, yrs=5)
    with patch.object(te, "team_needs", return_value=["RD"]):
        ok, why = tm._headliner_package_ok(app, league, hall, seller,
                                           bidder, [larsson])
    check("young/controllable/at-need 1-for-1 accepted", ok is True, why)
    # Same shape but NOT at a positional need -> still needs a package.
    with patch.object(te, "team_needs", return_value=["C"]):
        ok2, why2 = tm._headliner_package_ok(app, league, hall, seller,
                                             bidder, [larsson])
    check("1-for-1 off-need rejected", ok2 is False, why2)


def t_headliner_holdout():
    """An accepted-but-light bid on a headliner becomes a holdout counter,
    not an execution."""
    league = build_league()
    app = build_app(league, date(2027, 1, 10))
    market = tm.get_market(league)
    seller = league.teams[0]
    star = mk_player("Quinn", "Hugheslike", PlayerPosition.DEFENSE, 25, 94,
                     9_000_000, yrs=4)
    seller.roster.append(star)
    listing = tm.list_piece(app, league, seller, star, source="seller_list",
                            today=app.current_date)
    check("headliner listed", listing is not None)
    if not listing:
        return
    light = [mk_player("Good", "Player", PlayerPosition.CENTER, 28, 82,
                       5_000_000, yrs=3)]
    buyer = league.teams[3]
    resp = SimpleNamespace(decision="accept", want_added=[], will_add=[])
    with patch.object(te, "ai_consider_trade", return_value=resp), \
         patch.object(tm, "build_bid", return_value=list(light)):
        tm._evaluate_round(app, league, market, listing, app.current_date,
                           False)
    check("light accept converted to holdout, not traded",
          listing["status"] == "open" and "holding out" in listing.get("note", ""),
          f"status={listing['status']} note={listing.get('note')}")


def t_unified_shortlist():
    """Legacy store migrates once into the ONE unified surface; no dupes."""
    clear_shortlist_store()
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    market = tm.get_market(league)
    team = app.user_team
    p1, p2 = team.roster[0], team.roster[1]
    team.scout_shortlist = [
        {"player_id": p1.id, "added_by": "user", "date": "2026-11-01",
         "note": "need scoring"},
        {"player_id": p2.id, "added_by": "Old Scout", "date": "2026-11-02",
         "note": "SUGGESTED: fast skater"},
    ]
    moved = tm.migrate_shortlist_once(app, league, team, market)
    check("legacy entries migrated", moved == 2, f"moved={moved}")
    check("legacy store retired", team.scout_shortlist == [])
    uni = tm.get_unified_targets(league)
    check("unified surface holds both entries", len(uni) == 2,
          str([(t["player_name"], t["notes"][:40]) for t in uni]))
    check("no duplicate player ids", len({t["player_id"] for t in uni}) == 2)
    moved2 = tm.migrate_shortlist_once(app, league, team, market)
    check("migration never re-runs", moved2 == 0)
    check("re-adding migrated player rejected",
          tm.add_target(p1, league=league) is False)
    # Scout suggestion lands on the same surface with attribution.
    p3 = team.roster[2]
    check("scout add works", tm.add_target(p3, source="New Scout",
                                           note="(High confidence): wheels",
                                           league=league) is True)
    uni2 = tm.get_unified_targets(league)
    kinds = {tm._target_source(t["notes"])[0] for t in uni2}
    check("user + scout entries coexist on one surface",
          kinds == {"user", "scout"}, str(kinds))


def t_trade_request_autolist():
    league = build_league()
    app = build_app(league, date(2026, 11, 5))
    market = tm.get_market(league)
    seller = league.teams[0]  # Seller0, has a request
    req = [p for p in seller.roster if getattr(p, "transfer_requested", False)]
    check("fixture has a trade request", len(req) == 1)
    tm._auto_list(app, league, market, app.current_date, False)
    listed = [l for l in market["listings"] if l["player_id"] == req[0].id]
    check("trade request auto-listed year-round",
          len(listed) == 1 and listed[0]["source"] == "trade_request",
          f"listed={len(listed)}")
    tm._auto_list(app, league, market, app.current_date, False)
    listed2 = [l for l in market["listings"] if l["player_id"] == req[0].id]
    check("no duplicate listings for same player", len(listed2) == 1)


def t_baseline_listing_caps():
    league = build_league()
    app = build_app(league, date(2026, 10, 15))
    market = tm.get_market(league)
    seller = league.teams[0]
    for _ in range(6):  # more passes than the cap allows
        tm._auto_list(app, league, market, app.current_date, False)
    n = sum(1 for l in market["listings"]
            if l["seller"] == seller.team_name and l["status"] == "open")
    check("baseline max listings/team respected",
          n <= tm.MAX_ACTIVE_LISTINGS_BASELINE, f"open={n}")
    check("baseline league cap respected",
          sum(1 for l in market["listings"] if l["status"] == "open")
          <= tm.MAX_OPEN_LISTINGS_LEAGUE_BASELINE)


def t_build_bid_sane():
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    seller, buyer = league.teams[0], league.teams[2]
    piece = seller.roster[1]
    ask = te.player_trade_value(piece)
    assets = tm.build_bid(app, league, buyer, piece, seller, ask)
    check("build_bid returns assets", assets is not None and len(assets) > 0)
    if assets:
        owned = all(getattr(a, "current_team", buyer.team_name) == buyer.team_name
                    or a in buyer.roster for a in assets)
        check("bid assets owned by bidder", owned)
        check("bid is cap-legal for bidder",
              te._cap_ok_after(buyer, assets, [piece]))
        offer = sum(te.asset_value(a) for a in assets)
        check("bid sized toward ask", offer >= ask * 0.8,
              f"offer={offer:.0f} ask={ask:.0f}")


def t_full_round_executes():
    """End-to-end: listing -> bid -> executes via execute_trade gate."""
    league = build_league()
    app = build_app(league, date(2026, 12, 10))
    seller, buyer = league.teams[0], league.teams[2]
    piece = seller.roster[1]
    listing = tm.list_piece(app, league, seller, piece, source="seller_list",
                            today=app.current_date)
    check("listing created", listing is not None)
    if not listing:
        return
    ask_v = listing["ask_points"]
    assets = tm.build_bid(app, league, buyer, piece, seller, ask_v)
    check("bid built for round", assets is not None and len(assets) > 0)
    if not assets:
        return
    moved = tm._execute_market_deal(app, league, listing, piece, seller,
                                    buyer, assets, today=app.current_date)
    check("deal executed through execute_trade gate", moved is True)
    if moved:
        check("piece moved to buyer",
              piece in buyer.roster and piece not in seller.roster)
        check("seller still cap-legal", te._cap_ok_after(seller, [], []))
        check("buyer still cap-legal", te._cap_ok_after(buyer, [], []))
        m = tm.get_market(league)
        check("deal cooldown stamped (seller)",
              seller.team_name in m["deal_cooldown"])
        check("deal cooldown stamped (buyer)",
              buyer.team_name in m["deal_cooldown"])
        check("listing marked traded", listing["status"] == "traded")


def t_cooldown_blocks_relist():
    league = build_league()
    app = build_app(league, date(2026, 12, 10))
    market = tm.get_market(league)
    seller = league.teams[0]
    market["deal_cooldown"][seller.team_name] = "2026-12-24"
    check("_on_cooldown true within window",
          tm._on_cooldown(market, seller.team_name, date(2026, 12, 10)))
    check("_on_cooldown false after window",
          not tm._on_cooldown(market, seller.team_name, date(2026, 12, 25)))


def t_sellers_list_more_than_buyers():
    """Dynamic property: over a simulated stretch, sellers list more."""
    league = build_league()
    app = build_app(league, date(2026, 10, 20))
    counts = {}
    day = date(2026, 10, 20)
    for _ in range(45):
        app.current_date = day
        before = {(l["seller"], l["player_id"])
                  for l in tm.get_market(league)["listings"]}
        tm.process_market(app, league, day)
        after = {(l["seller"], l["player_id"])
                 for l in tm.get_market(league)["listings"]}
        for team, _pid in after - before:
            counts[team] = counts.get(team, 0) + 1
        day += timedelta(days=1)
    sellers = sum(counts.get(f"Seller{i}", 0) for i in (0, 1))
    buyers = sum(counts.get(f"Buyer{i}", 0) for i in range(4))
    check("sellers originate more listings than buyers over 45 days",
          sellers > buyers, f"sellers={sellers} buyers={buyers} counts={counts}")
    check("at least one listing happened", sellers + buyers > 0, str(counts))


def t_request_resolution_paths():
    """All four trade-request outcomes are reachable and terminal."""
    league = build_league()
    app = build_app(league, date(2026, 11, 1))
    market = tm.get_market(league)
    seller = league.teams[0]

    # Path 1 -- TRADED: executing the deal clears the request flag.
    req = [p for p in seller.roster if getattr(p, "transfer_requested", False)][0]
    listing = tm.list_piece(app, league, seller, req, source="trade_request",
                            today=app.current_date)
    buyer = league.teams[2]
    assets = tm.build_bid(app, league, buyer, req, seller, listing["ask_points"])
    moved = tm._execute_market_deal(app, league, listing, req, seller, buyer,
                                    assets, today=app.current_date)
    check("path 1 (traded): request clears on execution",
          moved and not getattr(req, "transfer_requested", False))

    # Path 2 -- RESCINDED: club turns buyer, roll forced to hit.
    p2 = seller.roster[2]
    p2.transfer_requested = True
    listing2 = tm.list_piece(app, league, seller, p2, source="trade_request",
                             today=app.current_date)
    with patch("trade_storylines.stance", return_value="buyer"), \
         patch("random.random", return_value=0.0):
        tm._resolve_trade_requests(app, league, market, app.current_date, False)
    check("path 2 (rescinded): flag cleared, listing pulled",
          not getattr(p2, "transfer_requested", False)
          and listing2["status"] == "pulled"
          and listing2["note"] == "request rescinded")

    # Path 3 -- DEADLINE FALLOUT: deadline passed, still untraded.
    p3 = seller.roster[3]
    p3.transfer_requested = True
    listing3 = tm.list_piece(app, league, seller, p3, source="trade_request",
                             today=app.current_date)
    with patch.object(tm, "_deadline_passed", return_value=True):
        tm._resolve_trade_requests(app, league, market, app.current_date, False)
    check("path 3 (deadline fallout): fallout stamped once",
          listing3.get("fallout_done") is True)

    # Path 4 -- PULLED: 85+ OVR core piece, roll forced to hit.
    p4 = mk_player("Core", "Star", PlayerPosition.CENTER, 28, 88, 8_000_000)
    seller.roster.append(p4)
    p4.transfer_requested = True
    listing4 = tm.list_piece(app, league, seller, p4, source="trade_request",
                             today=app.current_date)
    with patch("random.random", return_value=0.01):
        tm._resolve_trade_requests(app, league, market, app.current_date, False)
    check("path 4 (pulled): seller pulls, request stays live",
          listing4["status"] == "pulled"
          and listing4["note"] == "seller pulled"
          and getattr(p4, "transfer_requested", False) is True)


def t_trade_blocks_real():
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    tm.refresh_trade_blocks(app, league)
    blocks = tm.get_trade_blocks(league)
    check("blocks generated for league",
          isinstance(blocks, dict) and len(blocks) > 0)
    all_resolve = True
    for tname, ids in blocks.items():
        for pid in ids:
            p, t = tm.resolve_player(league, pid)
            if p is None or t is None or t.team_name != tname:
                all_resolve = False
    check("every block id resolves to a real player on that team", all_resolve)
    sellers_blocked = any(len(blocks.get(f"Seller{i}", [])) > 0 for i in (0, 1))
    check("sellers surface real blocks", sellers_blocked,
          str({k: len(v) for k, v in blocks.items()}))
    # user block mirrors into league.trade_blocks
    user_team = app.user_team
    up = user_team.roster[0]
    user_team.trade_block = [{"player_id": up.id, "date": "2026-12-01",
                              "note": "listening"}]
    tm.refresh_trade_blocks(app, league)
    check("user block mirrored league-wide",
          tm.get_trade_blocks(league).get(user_team.team_name) == [up.id])
    note = tm.block_availability_note(app, league, up.id)
    check("availability note is truthful",
          isinstance(note, str) and len(note) > 0, note)


def t_shortlist_crud():
    clear_shortlist_store()
    league = build_league()
    team = league.teams[2]
    p = team.roster[0]
    check("add_to_shortlist", tm.add_to_shortlist(team, p, note="x") is True)
    check("duplicate add rejected", tm.add_to_shortlist(team, p) is False)
    check("get_shortlist returns entry", len(tm.get_shortlist(team)) == 1)
    check("remove_from_shortlist", tm.remove_from_shortlist(team, p.id) is True)
    check("shortlist empty after remove", tm.get_shortlist(team) == [])


def t_scout_suggestions_jpa():
    """JPA bands: elite scouts hit, poor scouts ghost (existing machinery)."""
    from analytics_scouting import _detect_chance, _false_positive_chance
    elite_hit = _detect_chance(20, 15)
    poor_hit = _detect_chance(1, 15)
    elite_ghost = _false_positive_chance(20)
    poor_ghost = _false_positive_chance(1)
    check("elite scout hit rate ~90%", elite_hit >= 0.85, f"{elite_hit}")
    check("poor scout hit rate low", poor_hit <= 0.25, f"{poor_hit}")
    check("elite scout ghost rate low", elite_ghost <= 0.10, f"{elite_ghost}")
    check("poor scout ghost rate high", poor_ghost >= 0.35, f"{poor_ghost}")


def t_scout_suggestions_flow():
    clear_shortlist_store()
    league = build_league()
    app = build_app(league, date(2027, 1, 5))
    elite = SimpleNamespace(role="Pro Scout", first_name="Elite",
                            last_name="Eye",
                            judging_potential_accuracy=19,
                            judging_ability_accuracy=18)
    poor = SimpleNamespace(role="Amateur Scout", first_name="Poor",
                           last_name="Guess",
                           judging_potential_accuracy=3,
                           judging_ability_accuracy=4)
    app.user_team.staff = [elite, poor]
    n = tm.refresh_scout_suggestions(app, league)
    check("refresh_scout_suggestions never crashes, returns int",
          isinstance(n, int))
    sug = [e for e in tm.get_shortlist(app.user_team)
           if e.get("added_by") not in ("user",)]
    check("suggestions attributed to scouts (when any)",
          all(e.get("added_by") for e in sug))
    # Unified surface: suggestions carry the scout's confidence band in
    # the notes, never the truth flag.
    uni = tm.get_unified_targets(league)
    sug_notes = [t["notes"] for t in uni
                 if t["notes"].startswith("SUGGESTED by ")]
    check("suggestion notes carry scout name + confidence band",
          all("confidence" in n for n in sug_notes) if sug_notes else True,
          str(sug_notes[:2]))
    check("one unified surface: no duplicate player ids",
          len({t["player_id"] for t in uni}) == len(uni))


def t_nudges_bounded():
    clear_shortlist_store()
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    tm.refresh_trade_blocks(app, league)
    user_team = app.user_team
    blocks = tm.get_trade_blocks(league)
    target_pid = None
    for tname, ids in blocks.items():
        if tname != user_team.team_name and ids:
            target_pid = ids[0]
            break
    if target_pid is None:
        check("nudge fixture: a block exists to target", False)
        return
    p, _t = tm.resolve_player(league, target_pid)
    tm.add_to_shortlist(user_team, p, note="want him")
    tm.check_shortlist_nudges(app, league, today=app.current_date)
    m = tm.get_market(league)
    check("nudge stamped once",
          m["shortlist_nudges"].get(str(p.id)) == "2026-12-01")
    tm.check_shortlist_nudges(app, league, today=app.current_date)
    check("nudge not re-fired same day",
          m["shortlist_nudges"].get(str(p.id)) == "2026-12-01")


def t_no_cap_illegal_after_sim():
    """Every executed market deal leaves both clubs cap-legal."""
    league = build_league()
    app = build_app(league, date(2026, 11, 1))
    random.seed(99)
    day = date(2026, 11, 1)
    for _ in range(30):
        app.current_date = day
        tm.process_market(app, league, day)
        day += timedelta(days=1)
    bad = [t.team_name for t in league.teams
           if salary_total(t) > t.salary_cap]
    check("no team pushed over the cap by market deals", not bad, str(bad))


def t_need_fit_positional():
    """Bidders match positional need via team_needs() short codes."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    check("_pos_code short codes", tm._pos_code(league.teams[0].roster[0]) == "C")
    seller = league.teams[0]
    # Buyer1..3 run all-center rosters -> LW is among their weakest groups.
    lw = mk_player("Wing", "Er", PlayerPosition.LEFT_WING, 29, 76, 3_500_000)
    seller.roster.append(lw)
    listing = tm.list_piece(app, league, seller, lw, source="seller_list",
                            today=app.current_date)
    bnames = [t.team_name for t in
              tm._find_bidders(app, league, listing, app.current_date, False)]
    check("need-fit piece draws needy buyers",
          "Buyer1" in bnames and "Buyer2" in bnames, str(bnames))
    # A 73 OVR center fills no buyer need (C is their strongest group,
    # below the 84 BPA override) -> no need-fit bids.
    c_piece = seller.roster[1]
    listing2 = tm.list_piece(app, league, seller, c_piece,
                             source="seller_list", today=app.current_date)
    bnames2 = [t.team_name for t in
               tm._find_bidders(app, league, listing2, app.current_date, False)]
    check("non-need average piece draws no buyer bids",
          not any(n.startswith("Buyer") for n in bnames2), str(bnames2))


def t_seller_eligible_bubble():
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    team = league.teams[0]
    league.game_results = [
        {"home_team": team.team_name, "away_team": "Buyer0",
         "home_score": 1, "away_score": 4},
    ] * 4
    check("bubble team on losing skid is seller-eligible",
          tm._seller_eligible(app, team, "bubble", False) is True)
    league.game_results = []
    check("bubble team without skid is not seller-eligible",
          tm._seller_eligible(app, team, "bubble", False) is False)


# ---------------------------------------------------------------------------
# Iteration 3 (2026-09-29): marquee attention, return vision, buyer risk.
# ---------------------------------------------------------------------------
EXTRA_OVR_ATTRS = ["aggressiveness", "anticipation", "balance", "bodycheck",
                   "checking", "faceoff_wins", "pokecheck", "pressure_player",
                   "shot_blocking"]


def mk_exact(fn, ln, pos, age, ovr, salary, yrs=2, grade="C", morale=70):
    """Deterministic-OvR fixture: pins every attribute overall_rating()
    reads, so the rating is exact and seed-stable (LW weights sum 1.2)."""
    p = mk_player(fn, ln, pos, age, ovr, salary, yrs, grade, morale)
    for a in EXTRA_OVR_ATTRS:
        if hasattr(p, a):
            try:
                setattr(p, a, ovr)
            except Exception:
                pass
    return p


def t_marquee_attention():
    """A star on the block pulls league-wide eyes: headline news, an
    extended window, an expanded bidder pool (even with no positional
    need), a bidding-war rumor, and multiple rounds. The sub-84 marquee
    (reputation + trade request) isolates the expansion from the 84+
    BPA override."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    stories = []
    app.add_news = stories.append
    market = tm.get_market(league)
    seller = league.teams[0]  # Seller0
    # 90-OVR star (LW: 75 x 1.2 = 90): marquee by rating alone.
    star = mk_exact("Star", "Player", PlayerPosition.LEFT_WING, 26, 75,
                    9_000_000, yrs=3, grade="A")
    seller.roster.append(star)
    check("fixture star ovr 90", star.overall_rating() == 90,
          f"ovr={star.overall_rating()}")
    listing = tm.list_piece(app, league, seller, star, source="seller_list",
                            today=app.current_date)
    check("marquee star listed", listing is not None)
    if not listing:
        return
    check("marquee flagged", listing.get("marquee") is True)
    check("is_marquee(star)", tm.is_marquee(listing, star) is True)
    check("marquee headline fired",
          any("BLOCKBUSTER WATCH" in s for s in stories))
    # Sub-84 marquee: 75 OVR (63 x 1.2) but rep 90 + a trade request.
    agit = mk_exact("Big", "Name", PlayerPosition.LEFT_WING, 31, 63,
                    5_000_000, yrs=2)
    agit.reputation = 90
    agit.transfer_requested = True
    seller.roster.append(agit)
    check("fixture agitator ovr 75", agit.overall_rating() == 75,
          f"ovr={agit.overall_rating()}")
    listing_b = tm.list_piece(app, league, seller, agit,
                              source="trade_request",
                              today=app.current_date)
    check("request marquee flagged", listing_b.get("marquee") is True)
    check("is_marquee(request)", tm.is_marquee(listing_b, agit) is True)
    check("request headline fired",
          sum(1 for s in stories if "BLOCKBUSTER WATCH" in s) == 2)
    # Plain 75-OVR depth piece: not marquee (window baseline). Listed by
    # the other seller so the per-team cap doesn't eat the comparison.
    depth = mk_exact("Depth", "Guy", PlayerPosition.LEFT_WING, 28, 63,
                     2_000_000, yrs=1)
    seller2 = league.teams[1]  # Seller1
    seller2.roster.append(depth)
    listing_c = tm.list_piece(app, league, seller2, depth,
                              source="seller_list", today=app.current_date)
    check("plain depth listed", listing_c is not None)
    if not listing_c:
        return
    check("non-marquee not flagged", not listing_c.get("marquee"))
    check("is_marquee(depth) false",
          tm.is_marquee(listing_c, depth) is False)
    d_star = (date.fromisoformat(listing["bidding_close"])
              - date.fromisoformat(listing["listed_day"])).days
    d_plain = (date.fromisoformat(listing_c["bidding_close"])
               - date.fromisoformat(listing_c["listed_day"])).days
    check("marquee window extended +3d",
          d_star - d_plain == tm.MARQUEE_WINDOW_BONUS_DAYS,
          f"star={d_star}d plain={d_plain}d")
    # Bidder pool: nobody needs a LW, but every buyer kicks the tires on
    # the marquee name. The plain depth piece draws no one.
    bnames = {"Buyer1", "Buyer2", "Buyer3"}
    with patch.object(te, "team_needs", return_value=["G", "C", "RD"]):
        got_b = {getattr(b, "team_name", "?") for b in
                 tm._find_bidders(app, league, listing_b, app.current_date,
                                  False)}
        got_c = tm._find_bidders(app, league, listing_c, app.current_date,
                                 False)
    check("marquee expanded pool: all buyers bid", got_b == bnames,
          f"got={sorted(got_b)}")
    check("non-marquee: no need-fit bidders", len(got_c) == 0,
          f"got={len(got_c)}")
    # Rounds: war rumor on round 0, listing stays open across rounds,
    # and the note surfaces whose package fits the seller's vision.
    pkg = [mk_pick("Buyer1", 2027, 2)]
    resp = SimpleNamespace(decision="counter", want_added=[], will_add=[])
    ctx = [patch.object(te, "ai_consider_trade", return_value=resp),
           patch.object(tm, "build_bid", return_value=list(pkg)),
           patch("random.random", return_value=0.0),
           patch.object(te, "team_needs", return_value=["G", "C", "RD"])]
    # Rounds run on the next days (one round per listing per day; the rumor
    # flood cap is per-day and reads the app's clock).
    _d2 = app.current_date + timedelta(days=1)
    app.current_date = _d2
    with ctx[0], ctx[1], ctx[2], ctx[3]:
        tm._evaluate_round(app, league, market, listing_b, _d2, False)
    check("marquee war rumor fired",
          any("BIDDING WAR" in s for s in stories))
    check("round 1: still open", listing_b["status"] == "open"
          and listing_b["rounds"] == 1,
          f"status={listing_b['status']} rounds={listing_b['rounds']}")
    check("vision-leader note",
          "fits the vision" in listing_b.get("note", ""),
          listing_b.get("note", ""))
    app.current_date = _d2 + timedelta(days=1)
    with ctx[0], ctx[1], ctx[2], ctx[3]:
        tm._evaluate_round(app, league, market, listing_b, _d2 + timedelta(days=1),
                           False)
    check("round 2: multi-round war", listing_b["status"] == "open"
          and listing_b["rounds"] == 2,
          f"status={listing_b['status']} rounds={listing_b['rounds']}")


def t_quiet_nonstar():
    """A 75-OVR depth piece draws only need-fit interest: one bidder, no
    war rumor, quiet resolution."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    stories = []
    app.add_news = stories.append
    market = tm.get_market(league)
    seller = league.teams[0]
    piece = mk_exact("Quiet", "Depth", PlayerPosition.LEFT_WING, 29, 63,
                     1_500_000, yrs=1)
    seller.roster.append(piece)
    listing = tm.list_piece(app, league, seller, piece, source="seller_list",
                            today=app.current_date)
    check("depth listed", listing is not None)
    if not listing:
        return
    check("not marquee", not listing.get("marquee")
          and tm.is_marquee(listing, piece) is False)

    def _needs(team):
        return ["LW", "C", "G"] \
            if getattr(team, "team_name", "") == "Buyer1" \
            else ["G", "C", "RD"]
    with patch.object(te, "team_needs", side_effect=_needs):
        bidders = tm._find_bidders(app, league, listing, app.current_date,
                                   False)
    got = {getattr(b, "team_name", "?") for b in bidders}
    check("only need-fit team bids", got == {"Buyer1"}, f"got={sorted(got)}")
    resp = SimpleNamespace(decision="accept", want_added=[], will_add=[])
    with patch.object(te, "ai_consider_trade", return_value=resp), \
         patch.object(te, "team_needs", side_effect=_needs):
        tm._evaluate_round(app, league, market, listing, app.current_date,
                           False)
    check("quiet resolution: traded", listing["status"] == "traded",
          f"status={listing['status']}")
    check("no war rumor for depth",
          not any("BIDDING WAR" in s for s in stories))
    check("piece moved", piece in league.teams[3].roster)


def t_return_vision():
    """The seller's return vision re-ranks offers: a rebuilding seller
    takes the futures package over a richer veteran deal; a contender
    takes immediate help. Raw asset value is only the tiebreak."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    rebuilder = league.teams[0]  # Seller0, stance seller
    contender = league.teams[3]  # Buyer1, stance buyer
    vet = mk_exact("Old", "Veteran", PlayerPosition.CENTER, 32, 75,
                   7_000_000, yrs=2)
    picks = [mk_pick("X", 2027, 2), mk_pick("X", 2027, 3)]
    vet_raw = te.asset_value(vet)
    picks_raw = sum(te.asset_value(p) for p in picks)
    check("fixture: veteran raw > picks raw", vet_raw > picks_raw,
          f"vet={vet_raw:.0f} picks={picks_raw:.0f}")
    v_vet_reb = tm.score_offer_for_seller(app, league, rebuilder, vet,
                                          contender, [vet])
    v_picks_reb = tm.score_offer_for_seller(app, league, rebuilder, vet,
                                            contender, picks)
    check("rebuilder prefers futures", v_picks_reb > v_vet_reb,
          f"picks={v_picks_reb:.0f} vet={v_vet_reb:.0f}")
    v_vet_con = tm.score_offer_for_seller(app, league, contender, vet,
                                          rebuilder, [vet])
    v_picks_con = tm.score_offer_for_seller(app, league, contender, vet,
                                            rebuilder, picks)
    check("contender prefers immediate help", v_vet_con > v_picks_con,
          f"vet={v_vet_con:.0f} picks={v_picks_con:.0f}")


def t_buyer_risk():
    """Situational risk: a desperate buyer overpays and answers counters
    it would otherwise walk from; a patient buyer holds its number."""
    league = build_league()
    app = build_app(league, date(2026, 12, 1))
    seller = league.teams[0]
    buyer = league.teams[3]  # Buyer1
    # Unit: the desperation scale itself.
    with patch.object(tsl, "stance", return_value="bubble"), \
         patch.object(tsl, "_streak", return_value=-5):
        d = tm._buyer_desperation(app, buyer)
    check("desperate: bubble + slide", d >= 0.6, f"d={d:.2f}")
    with patch.object(tsl, "stance", return_value="buyer"), \
         patch.object(tsl, "_streak", return_value=0):
        p = tm._buyer_desperation(app, buyer)
    check("patient: buyer + even keel", p <= 0.2, f"d={p:.2f}")
    # build_bid: same ask, the desperate buyer sizes above it.
    buyer.draft_picks = {
        2027: [mk_pick("Buyer1", 2027, 2), mk_pick("Buyer1", 2027, 3),
               mk_pick("Buyer1", 2027, 3)],
    }
    piece = mk_exact("Target", "Man", PlayerPosition.CENTER, 27, 70,
                     4_000_000, yrs=2)
    seller.roster.append(piece)
    with patch.object(tm, "_buyer_desperation", return_value=1.0), \
         patch.object(tsl, "situational_context",
                      return_value={"greed_mult": 1.0}):
        desp_assets = tm.build_bid(app, league, buyer, piece, seller, 350)
    with patch.object(tm, "_buyer_desperation", return_value=0.0), \
         patch.object(tsl, "situational_context",
                      return_value={"greed_mult": 1.0}):
        pat_assets = tm.build_bid(app, league, buyer, piece, seller, 350)
    dv = sum(te.asset_value(a) for a in desp_assets)
    pv = sum(te.asset_value(a) for a in pat_assets)
    check("desperate outbids patient on same ask", dv > pv,
          f"desperate={dv:.0f} patient={pv:.0f}")
    # _escalate_bid: the desperate buyer answers the counter; the patient
    # buyer walks at its number.
    listing = {"bids": [], "rounds": 1}
    with patch.object(tm, "_buyer_desperation", return_value=1.0), \
         patch.object(tm, "_gm_boldness", return_value=0.9), \
         patch.object(tsl, "situational_context",
                      return_value={"greed_mult": 1.0}), \
         patch("random.random", return_value=0.35), \
         patch.object(tm, "build_bid", return_value=list(desp_assets)):
        esc_desp = tm._escalate_bid(app, league, listing, buyer, piece,
                                    seller, 350, esc_mult=1.0)
    with patch.object(tm, "_buyer_desperation", return_value=0.0), \
         patch.object(tm, "_gm_boldness", return_value=0.1), \
         patch.object(tsl, "situational_context",
                      return_value={"greed_mult": 1.0}), \
         patch("random.random", return_value=0.35), \
         patch.object(tm, "build_bid", return_value=list(pat_assets)):
        esc_pat = tm._escalate_bid(app, league, listing, buyer, piece,
                                   seller, 350, esc_mult=1.0)
    check("desperate escalates", esc_desp is not None and len(esc_desp) > 0)
    check("patient walks", esc_pat is None)


def _mk_results(team, player, pts_list):
    """Recent-form fixture: per-game points lists -> game_results entries
    with per-player game_stats the market's perception reader consumes."""
    out = []
    for i, pts in enumerate(pts_list):
        out.append({
            "date": date(2026, 11, 1) + timedelta(days=i),
            "home_team": SimpleNamespace(team_name=team.team_name),
            "away_team": SimpleNamespace(team_name="Elsewhere"),
            "game_stats": {player.id: {"g": pts, "a": 0}},
        })
    return out


def t_player_conscious():
    """The market weighs the person, not just the rating: recent
    production shapes perception (scout-voiced, never raw math), contract
    worth shapes demand, and ambitions shape destinations."""
    league = build_league()
    app = build_app(league, date(2026, 12, 10))
    seller, seller1 = league.teams[0], league.teams[1]
    # Two 81-OVR defensemen (attr 70): buyers need LD second behind RW.
    # The slumper only draws teams with a glaring hole -- none here.
    prod = mk_exact("Hot", "Hand", PlayerPosition.LEFT_DEFENSE, 26, 70,
                    4_500_000, yrs=3)
    slump = mk_exact("Cold", "Snap", PlayerPosition.LEFT_DEFENSE, 26, 70,
                     4_500_000, yrs=3)
    check("fixture 81 ovr pair",
          prod.overall_rating() == 81 and slump.overall_rating() == 81)
    seller.roster.extend([prod, slump])
    for p in (prod, slump):  # respectable season totals isolate the window
        p.stats.games_played = 40
        p.stats.goals = 12
        p.stats.assists = 18
    league.game_results = (_mk_results(seller, prod, [2] * 12)
                           + _mk_results(seller, slump, [0] * 12))
    pf, pnote = tm.perception_discount(app, league, prod)
    sf, snote = tm.perception_discount(app, league, slump)
    check("producer earns a premium", pf > 1.0, f"f={pf}")
    check("slumper is discounted", sf < 1.0, f"f={sf}")
    check("buyer-beware note is scout-voiced",
          "buyer beware" in snote and "=" not in snote and "%" not in snote,
          snote)
    check("premium note carries no formulas",
          "full freight" in pnote and "=" not in pnote and "%" not in pnote,
          pnote)
    lp = tm.list_piece(app, league, seller, prod, source="seller_list",
                       today=app.current_date)
    ls = tm.list_piece(app, league, seller, slump, source="seller_list",
                       today=app.current_date)
    check("scout brief stamped on slumping listing",
          bool(ls.get("scout_brief")), str(ls.get("scout_brief")))
    bp = tm._find_bidders(app, league, lp, app.current_date, ramp=False)
    bs = tm._find_bidders(app, league, ls, app.current_date, ramp=False)
    check("producer draws bidders", len(bp) >= 2, f"n={len(bp)}")
    check("slumping 81 draws fewer bidders", len(bs) < len(bp),
          f"slump={len(bs)} prod={len(bp)}")
    # Softer offers: same ask, the slumper's package prices lower.
    random.seed(7)
    bid_p = tm.build_bid(app, league, league.teams[3], prod, seller, 400)
    random.seed(7)
    bid_s = tm.build_bid(app, league, league.teams[3], slump, seller, 400)
    vp = sum(te.asset_value(a) for a in (bid_p or []))
    vs = sum(te.asset_value(a) for a in (bid_s or []))
    check("slumper draws a softer offer", 0 < vs < vp, f"{vs:.0f} vs {vp:.0f}")
    # Bad contract: 81-OVR at $12M against a ~$4.5M fair value.
    anchor = mk_exact("Big", "Ticket", PlayerPosition.LEFT_DEFENSE, 28, 70,
                      12_000_000, yrs=4)
    seller1.roster.append(anchor)
    wr, wnote = tm.contract_worth(anchor)
    check("anchor contract recognized", wr < 0.65, f"wr={wr:.2f}")
    check("anchor note is scout-voiced",
          "sweetener" in wnote and "$" not in wnote, wnote)
    la = tm.list_piece(app, league, seller1, anchor, source="seller_list",
                       today=app.current_date)
    check("sweetener attached to move the contract",
          la is not None and la.get("sweetener") is not None)
    if la is not None:
        ba = tm._find_bidders(app, league, la, app.current_date, ramp=False)
        check("toxic contract draws no bidders without a glaring hole",
              len(ba) == 0, f"n={len(ba)}")
    # Ambitions: a cup-chaser who asked out wants a buyer, not a bubble
    # team -- until deadline pressure loosens his list.
    chaser = mk_exact("Chase", "Cup", PlayerPosition.RIGHT_WING, 27, 70,
                      4_500_000, yrs=2)
    chaser.ambition = "cup"
    chaser.transfer_requested = True
    seller1.roster.append(chaser)
    lc = tm.list_piece(app, league, seller1, chaser, source="trade_request",
                       today=app.current_date)
    check("cup-chaser listed", lc is not None)
    check("cup-chaser won't go to a rebuilder (unit)",
          tm._destination_appeal(chaser, "seller")[0] is False)
    check("cup-chaser fine with a buyer (unit)",
          tm._destination_appeal(chaser, "buyer")[0] is True)
    check("ice-time wants opportunity (unit)",
          tm._preferred_destination_types(
              SimpleNamespace(ambition="ice_time")) == ["seller", "bubble"])
    if lc is not None:
        real_stance = tsl.stance

        def fake_stance(a, tname):
            return "bubble" if tname == "Buyer3" else real_stance(a, tname)

        with patch.object(tsl, "stance", fake_stance):
            calm_names = [t.team_name for t in tm._find_bidders(
                app, league, lc, app.current_date, ramp=False)]
            b_ramp = tm._find_bidders(app, league, lc, app.current_date,
                                      ramp=True)
        check("requester's list excludes the bubble team",
              "Buyer3" not in calm_names, str(calm_names))
        check("deadline pressure loosens the list",
              "Buyer3" in [t.team_name for t in b_ramp],
              str([t.team_name for t in b_ramp]))


def t_clause_red_tape():
    """Clauses are red tape on every market path: NMC blocks without
    consent, M-NTC refusal lists bite, one conversation per destination,
    user sales never pre-roll consent, and the engine stays the final
    backstop."""
    league = build_league()
    app = build_app(league, date(2026, 12, 10))
    seller0, seller1 = league.teams[0], league.teams[1]
    buyer0, buyer1 = league.teams[2], league.teams[3]
    # Engine truth: happy star on a contender refuses; miserable accepts.
    star = mk_exact("Happy", "Star", PlayerPosition.LEFT_WING, 28, 76,
                    9_000_000, morale=95)
    star.happiness = 95
    star.ambition = "cup"
    star.contract.no_movement_clause = True
    buyer0.roster.append(star)
    ok, why = te.will_waive_ntc(star, buyer0, seller0, league=league)
    check("happy star on contender rejects waiver", ok is False, why)
    mis = mk_exact("Sad", "Sack", PlayerPosition.RIGHT_WING, 29, 70,
                   5_000_000, morale=25)
    mis.happiness = 20
    mis.contract.no_movement_clause = True
    seller1.roster.append(mis)
    ok2, why2 = te.will_waive_ntc(mis, seller1, buyer0, league=league)
    check("miserable player on seller accepts waiver", ok2 is True, why2)
    # Market: the NMC veto blocks interest until consent is given.
    listing = tm.list_piece(app, league, seller1, mis, source="seller_list",
                            today=app.current_date)
    check("NMC piece listed", listing is not None)
    if listing is None:
        return
    bidders = tm._find_bidders(app, league, listing, app.current_date,
                               ramp=False)
    check("consent opens the market", len(bidders) >= 1,
          f"n={len(bidders)}")
    check("one waiver record per consenting destination",
          sorted(listing.get("waived_for", []))
          == sorted(t.team_name for t in bidders),
          str(listing.get("waived_for")))
    # One conversation per destination: re-matching rolls nothing new for
    # destinations already on record (a destination that refused the first
    # time may be asked again -- that's a new conversation, not a re-roll).
    calls = []
    real_waive = te.will_waive_ntc

    def counting(p, f, t=None, **kw):
        calls.append(getattr(t, "team_name", t))
        return real_waive(p, f, t, **kw)

    recorded = set(listing.get("waived_for", []) or [])
    with patch.object(te, "will_waive_ntc", counting):
        tm._find_bidders(app, league, listing, app.current_date, ramp=False)
    check("no double-roll for recorded destinations",
          not any(c in recorded for c in calls), str(calls))
    # Execution gate: a vetoed destination with no waiver record dies here,
    # before the engine -- and a recorded waiver stamps genuine consent.
    random.seed(3)
    assets = tm.build_bid(app, league, buyer1, mis, seller1,
                          listing["ask_points"])
    check("bid built for gated execution", bool(assets))
    listing["waived_for"] = []
    dead = tm._execute_market_deal(app, league, listing, mis, seller1,
                                   buyer1, list(assets or []),
                                   today=app.current_date)
    check("vetoed deal dies at the market gate", dead is False)
    check("piece stays put", mis in seller1.roster)
    check("gate names the refusal",
          "refused to waive" in listing.get("note", ""),
          listing.get("note", ""))
    listing["waived_for"] = [buyer1.team_name]
    listing["status"] = "open"
    moved = tm._execute_market_deal(app, league, listing, mis, seller1,
                                    buyer1, list(assets or []),
                                    today=app.current_date)
    check("recorded waiver lets the deal through", moved is True)
    check("waiver spent by the engine (one transaction)",
          getattr(mis.contract, "ntc_waiver_for", "") == "")
    # M-NTC: the refusal-list destination is rejected without consent.
    lg = mk_exact("List", "Guy", PlayerPosition.RIGHT_WING, 28, 70,
                  5_000_000, morale=85)
    lg.happiness = 85
    lg.contract.no_trade_clause = True
    lg.contract.modified_ntc_teams = 10
    lg.contract.no_trade_list = ["Buyer1"]
    seller0.roster.append(lg)
    check("refusal-list veto fires",
          len(te.trade_vetoes(seller0, buyer1, [lg])) == 1)
    ll = tm.list_piece(app, league, seller0, lg, source="seller_list",
                       today=app.current_date)
    if ll is not None:
        bl = tm._find_bidders(app, league, ll, app.current_date, ramp=False)
        check("refusal-list team excluded from bidders",
              "Buyer1" not in [t.team_name for t in bl],
              str([t.team_name for t in bl]))
        check("no waiver recorded for the refusal team",
              "Buyer1" not in (ll.get("waived_for") or []))
    # User's own block: consent is never pre-rolled; the offer still goes
    # out with a pending-consent flag for a real interaction.
    league2 = build_league()
    app2 = build_app(league2, date(2026, 12, 10))
    user_team = app2.user_team
    up = mk_exact("User", "Asset", PlayerPosition.RIGHT_WING, 27, 70,
                  5_000_000)
    up.happiness = 90
    up.morale = 90
    up.contract.no_movement_clause = True
    user_team.roster.append(up)
    user_team.trade_block = [up]
    calls2 = []
    with patch.object(te, "will_waive_ntc", counting), \
         patch("trade_negotiation.incoming_offer",
               side_effect=lambda *a, **k: calls2.append(1)):
        tm.process_market(app2, league2, app2.current_date)
    ul = [x for x in tm.get_market(league2)["listings"]
          if x.get("player_id") == up.id]
    check("user NMC block listed", len(ul) == 1)
    if ul:
        check("no silent waiver pre-roll for user sale",
              not ul[0].get("waived_for"), str(ul[0].get("waived_for")))
        check("offer still delivered to the user", len(calls2) >= 1)
        check("pending-consent flagged for the interaction",
              bool((ul[0].get("user_offer") or {}).get("pending_consent")),
              str((ul[0].get("user_offer") or {}).get("pending_consent")))
        check("piece not auto-traded", up in user_team.roster)


def main():
    random.seed(20260929)
    tests = [
        t_market_init_and_clear, t_json_safe, t_trade_request_autolist,
        t_baseline_listing_caps, t_build_bid_sane, t_full_round_executes,
        t_cooldown_blocks_relist, t_sellers_list_more_than_buyers,
        t_request_resolution_paths, t_trade_blocks_real, t_shortlist_crud,
        t_scout_suggestions_jpa, t_scout_suggestions_flow, t_nudges_bounded,
        t_no_cap_illegal_after_sim, t_need_fit_positional,
        t_seller_eligible_bubble,
        # Refinement pass (2026-09-29): heat, engagement, headliners, unified.
        t_heat_monotone, t_heat_beats, t_stance_flip_block, t_injury_block,
        t_user_block_offer, t_headliner_package, t_headliner_exception,
        t_headliner_holdout, t_unified_shortlist,
        # Iteration 3 (2026-09-29): marquee, return vision, buyer risk.
        t_marquee_attention, t_quiet_nonstar, t_return_vision, t_buyer_risk,
        # Iteration 4 (2026-09-29): person-conscious interest, clause tape.
        t_player_conscious, t_clause_red_tape,
    ]
    for t in tests:
        print(f"\n--- {t.__name__} ---")
        try:
            t()
        except Exception as e:
            FAIL.append(t.__name__)
            print(f"FAIL: {t.__name__} raised {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc(limit=3)
    clear_shortlist_store()  # don't leave saves/shortlist.json dirty
    print(f"\n==== {len(PASS)} passed, {len(FAIL)} failed ====")
    if FAIL:
        print("FAILED:", FAIL)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
