#!/usr/bin/env python3
"""R8b: trade-deadline week bucket tests (S item).

Bucket under test: daily_news._trade_deadline_stories + its window/buyer/
seller/trade-report helpers. Conventions: synthetic SimpleNamespace
app/team/player fixtures (same shape as the R8a tests); assertions on
premises, not phrasing.

The deadline DATE is canonical: trade_deadline_manager.trade_deadline_date
(last regular-season game - 40 days; March 8 fallback) -- the same
function the Trade Deadline Center's manager reads. The bucket fires only
on deadline-7..deadline inclusive.
"""
import sys
import os
import types
import random
from datetime import date, timedelta

_REPO = os.environ.get("R8B_REPO", os.path.expanduser("~/workspace/hockey-manager"))
sys.path.insert(0, _REPO)

import daily_news as dn


def rec(gp, pace):
    pts = round(pace * gp)
    w = pts // 2
    otl = pts % 2
    return w, gp - w - otl, otl


def mkplayer(fn, ln, pos, yrs, ovr):
    return types.SimpleNamespace(
        first_name=fn, last_name=ln,
        primary_position=types.SimpleNamespace(value=pos),
        contract=types.SimpleNamespace(years_remaining=yrs),
        overall=ovr)


def full_roster(n_f=12, n_d=6, n_g=2, yrs=2, ovr=78):
    roster = []
    for i in range(n_f):
        roster.append(mkplayer(f"F{i}", "Winger", "LW", yrs, ovr))
    for i in range(n_d):
        roster.append(mkplayer(f"D{i}", "Blueliner", "LD", yrs, ovr))
    for i in range(n_g):
        roster.append(mkplayer(f"G{i}", "Tender", "G", yrs, ovr))
    return roster


def mkteam(name, w, l, otl, roster=None, cap_space=5_000_000):
    return types.SimpleNamespace(
        team_name=name, conference="Eastern", division="Atlantic",
        league_name="National Hockey League",
        wins=w, losses=l, ot_losses=otl,
        roster=roster if roster is not None else full_roster(),
        cap_space=cap_space)


def mkapp(teams, last_game=date(2027, 4, 10), season_year=2026,
          season_len=82, schedule=True):
    sched = ([{"league": "NHL", "date": last_game}] if schedule else [])
    lg = types.SimpleNamespace(teams=teams, season_year=season_year,
                               schedule=sched)
    return types.SimpleNamespace(league=lg, season_games_count=season_len,
                                 _daily_news_recent={})


def mkdeal(date_str, a, b, summary="Aces acquire Chip Skater from Dogs."):
    return types.SimpleNamespace(
        date=date_str, team_a=a, team_b=b,
        a_gave=["Chip Skater"], b_gave=["3rd round pick"],
        summary=summary)


# 9-team pool: buyers = Aces/Bees/Cats (top third), sellers worst-first =
# Ibex/Hogs/Gulls (bottom third). gp 64-70: median 68 >= 40, spread 6 <= 15.
def pool(chip_team="Ibex"):
    teams = [
        mkteam("Aces", *rec(70, 1.36), roster=full_roster(n_d=3)),  # 95 pts, D-short
        mkteam("Bees", *rec(68, 1.29)),                             # 88
        mkteam("Cats", *rec(66, 1.21)),                             # 80
        mkteam("Dogs", *rec(68, 1.06)),                             # 72
        mkteam("Elks", *rec(64, 1.00)),                             # 64
        mkteam("Fins", *rec(66, 0.91)),                             # 60
        mkteam("Gulls", *rec(68, 0.76)),                            # 52
        mkteam("Hogs", *rec(66, 0.73)),                             # 48
        mkteam("Ibex", *rec(64, 0.62)),                             # 40
    ]
    if chip_team:
        cellar = next(t for t in teams if t.team_name == chip_team)
        chip = mkplayer("Chip", "Skater", "C", 0, 84)
        cellar.roster = [chip] + cellar.roster
    return teams


DEADLINE = date(2027, 3, 1)  # 2027-04-10 minus 40 days
DDSTR = DEADLINE.strftime("%b %d")  # every frame template renders the date


def is_frame(s):
    """Frame-story detector robust to template choice (all four frame
    templates render the deadline date; no other story type does)."""
    return DDSTR in s


def fire_all(app, start, days):
    """Run the bucket over consecutive days; return all stories seen."""
    seen = []
    for d in range(days):
        seen.extend(dn._trade_deadline_stories(
            app, start + timedelta(days=d), random.Random(100 + d)))
    return seen


def test_window_gate_fires_on_deadline_day():
    app = mkapp(pool())
    stories = dn._trade_deadline_stories(app, DEADLINE, random.Random(1))
    assert stories, "bucket must fire on deadline day"


def test_window_gate_fires_deadline_minus_7():
    app = mkapp(pool())
    stories = dn._trade_deadline_stories(
        app, date(2027, 2, 22), random.Random(1))
    assert stories, "bucket must fire 7 days before the deadline"


def test_window_gate_silent_deadline_minus_8():
    app = mkapp(pool())
    assert dn._trade_deadline_stories(
        app, date(2027, 2, 21), random.Random(1)) == []


def test_window_gate_silent_after_deadline():
    app = mkapp(pool())
    assert dn._trade_deadline_stories(
        app, date(2027, 3, 2), random.Random(1)) == []


def test_window_gate_offseason():
    app = mkapp(pool())
    assert dn._trade_deadline_stories(
        app, date(2027, 7, 10), random.Random(1)) == []


def test_window_gate_gp_spread_distrust():
    teams = pool()
    teams[0].wins, teams[0].losses, teams[0].ot_losses = rec(30, 1.36)
    app = mkapp(teams)
    assert dn._trade_deadline_stories(app, DEADLINE,
                                      random.Random(1)) == []


def test_deadline_derived_from_real_schedule():
    # The canonical derivation: last regular-season game minus 40 days.
    app = mkapp(pool(), last_game=date(2027, 4, 15))
    assert dn._td_deadline(app) == date(2027, 3, 6)
    # ...so the window tracks the schedule, not a hardcoded date.
    assert dn._trade_deadline_stories(
        app, date(2027, 2, 27), random.Random(1))  # deadline - 7
    assert dn._trade_deadline_stories(
        app, date(2027, 2, 26), random.Random(1)) == []  # deadline - 8


def test_deadline_fallback_march_8():
    # No schedule: March 8 of the season's end year (season_year + 1).
    app = mkapp(pool(), schedule=False)
    assert dn._td_deadline(app) == date(2027, 3, 8)
    stories = dn._trade_deadline_stories(app, date(2027, 3, 5),
                                         random.Random(1))
    assert stories, "fallback window must still fire"


def test_frame_countdown_true():
    # 3 days before the deadline: the frame story must say "3 days away"
    # and name the real points leader and the real cellar team.
    app = mkapp(pool())
    stories = dn._trade_deadline_stories(app, date(2027, 2, 26),
                                         random.Random(2))
    frame = [s for s in stories if is_frame(s)]
    assert frame, stories
    s = frame[0]
    assert "3 days away" in s, s
    assert "Aces" in s and "95" in s, s          # real leader, real pts
    assert "Ibex" in s and "40" in s, s          # real cellar, real pts
    assert "47-22-1" in s and "20-44-0" in s, s  # real records


def test_frame_says_today_on_deadline_day():
    app = mkapp(pool())
    stories = dn._trade_deadline_stories(app, DEADLINE, random.Random(2))
    frame = [s for s in stories if is_frame(s)]
    assert frame and "is TODAY" in frame[0], stories


def test_buyer_is_top_third():
    # Aces/Bees/Cats are the top third by points; a buyer story must name
    # one of them (with its true record), never a mid-table club.
    app = mkapp(pool())
    stories = fire_all(app, date(2027, 2, 26), 4)
    buyer = [s for s in stories if "BUYER WATCH" in s or "is buying" in s
             or "Deadline buyers" in s]
    assert buyer, stories
    assert any("Aces" in s and "47-22-1" in s for s in buyer), buyer
    assert not any("Dogs" in s or "Elks" in s or "Fins" in s
                   for s in buyer), buyer


def test_buyer_need_matches_roster():
    # Aces are D-short (3 defensemen vs the 12F/6D/2G complement): the
    # buyer story must say blue-line help, not invent another need.
    app = mkapp(pool())
    stories = fire_all(app, date(2027, 2, 26), 4)
    aces = [s for s in stories if "Aces" in s and
            ("BUYER" in s or "buying" in s or "buyers" in s)]
    assert aces, stories
    assert any("blue-line help" in s for s in aces), aces


def test_buyer_cap_clause_true():
    # Aces carry $5M in cap space: the clause must render the real figure.
    app = mkapp(pool())
    stories = fire_all(app, date(2027, 2, 26), 4)
    aces = [s for s in stories if "Aces" in s and "cap space" in s]
    assert aces, stories
    assert all("$5.0M" in s for s in aces), aces


def test_seller_is_bottom_third():
    # Ibex/Hogs/Gulls are the bottom third; a seller story must name one
    # of them with its true record, never a mid-table club.
    app = mkapp(pool())
    stories = fire_all(app, date(2027, 2, 22), 8)
    seller = [s for s in stories if "SELLER WATCH" in s or "sellers" in s
              or "Rental market" in s]
    assert seller, stories
    assert any("Ibex" in s and "20-44-0" in s for s in seller), seller
    assert not any("Dogs" in s or "Elks" in s or "Fins" in s
                   for s in seller), seller


def test_seller_names_real_expiring_chip():
    # The chip named must be a real Ibex roster player on a real expiring
    # contract (years_remaining == 0), with true name and OVR.
    app = mkapp(pool())
    stories = fire_all(app, date(2027, 2, 22), 8)
    ibex = [s for s in stories if "Ibex" in s and
            ("SELLER" in s or "Rental" in s)]
    assert ibex, stories
    assert any("Chip Skater" in s and "84 OVR" in s for s in ibex), ibex


def test_seller_silent_without_rentals():
    # Nobody on an expiring deal: the seller story must stay silent rather
    # than invent a chip.
    teams = pool(chip_team=None)
    for t in teams:
        for p in t.roster:
            p.contract.years_remaining = 2
    app = mkapp(teams)
    stories = fire_all(app, date(2027, 2, 22), 8)
    assert not any("SELLER WATCH" in s or "Rental market" in s
                   for s in stories), stories


def test_trade_report_names_real_deal():
    # A real CompletedTrade in the window: the story names both real clubs
    # and the real summary.
    app = mkapp(pool())
    app.trade_history = [mkdeal("2027-02-25 15:30:00", "Aces", "Dogs")]
    stories = fire_all(app, DEADLINE, 1)
    deal = [s for s in stories
            if "aces" in s.lower() and "dogs" in s.lower()
            and ("deal" in s.lower() or "trade" in s.lower())]
    assert deal, stories
    assert "Chip Skater" in deal[0], deal


def test_trade_report_ignores_unknown_teams():
    # A trade naming a club outside the live league is not league activity.
    app = mkapp(pool())
    app.trade_history = [mkdeal("2027-02-25 15:30:00", "Aces",
                                "Springfield Isotopes")]
    stories = fire_all(app, DEADLINE, 1)
    assert not any("DEADLINE DEAL" in s for s in stories), stories
    assert not any("Isotopes" in s for s in stories), stories


def test_trade_report_ignores_bad_date():
    # An unparseable trade date can't be placed in the window: silent.
    app = mkapp(pool())
    app.trade_history = [mkdeal("sometime last week", "Aces", "Dogs")]
    stories = fire_all(app, DEADLINE, 1)
    assert not any("DEADLINE DEAL" in s for s in stories), stories


def test_trade_report_ignores_stale_date():
    # A January deal is real but outside the deadline window: silent.
    app = mkapp(pool())
    app.trade_history = [mkdeal("2027-01-10", "Aces", "Dogs")]
    stories = fire_all(app, DEADLINE, 1)
    assert not any("DEADLINE DEAL" in s for s in stories), stories


def test_trade_report_falls_back_to_asset_lists():
    # No summary text: the story renders the real asset lists instead.
    app = mkapp(pool())
    app.trade_history = [mkdeal("2027-02-25", "Aces", "Dogs", summary="")]
    stories = fire_all(app, DEADLINE, 1)
    deal = [s for s in stories
            if "aces" in s.lower() and "dogs" in s.lower()
            and ("deal" in s.lower() or "trade" in s.lower())]
    assert deal, stories
    assert "Aces gets Chip Skater" in deal[0], deal
    assert "Dogs gets 3rd round pick" in deal[0], deal


def test_no_unknown_team_rendered():
    teams = pool()
    teams[1] = types.SimpleNamespace(
        team_name=None, conference="Eastern", division="Atlantic",
        league_name="National Hockey League",
        wins=42, losses=22, ot_losses=4,
        roster=full_roster(), cap_space=5_000_000)
    app = mkapp(teams)
    stories = fire_all(app, date(2027, 2, 22), 8)
    assert not any("Unknown Team" in s for s in stories), stories


def test_no_unknown_player_rendered():
    # The cellar team's only expiring player is nameless: the seller story
    # must stay silent rather than render "Unknown Player".
    teams = pool(chip_team=None)
    ibex = next(t for t in teams if t.team_name == "Ibex")
    ghost = types.SimpleNamespace(
        first_name="", last_name="",
        primary_position=types.SimpleNamespace(value="C"),
        contract=types.SimpleNamespace(years_remaining=0), overall=84)
    ibex.roster = [ghost] + ibex.roster
    app = mkapp(teams)
    stories = fire_all(app, date(2027, 2, 22), 8)
    assert not any("Unknown Player" in s for s in stories), stories
    assert not any("Ibex" in s and ("SELLER" in s or "Rental" in s)
                   for s in stories), stories


def test_once_per_season_per_team():
    # Frame + buyer stories fire once per season; the next day must not
    # repeat the same teams' stories.
    app = mkapp(pool())
    d1 = dn._trade_deadline_stories(app, date(2027, 2, 26), random.Random(3))
    assert d1
    d2 = dn._trade_deadline_stories(app, date(2027, 2, 27), random.Random(4))
    assert not any("Aces" in s for s in d2), d2
    assert not any(is_frame(s) for s in d2), d2


def test_max_two_stories_per_day():
    app = mkapp(pool())
    app.trade_history = [mkdeal("2027-02-25 15:30:00", "Aces", "Dogs")]
    stories = dn._trade_deadline_stories(app, DEADLINE, random.Random(5))
    assert len(stories) <= 2, stories


def test_never_raises_on_garbage():
    app = types.SimpleNamespace()
    assert dn._trade_deadline_stories(app, DEADLINE,
                                      random.Random(1)) == []
    assert dn._trade_deadline_stories(app, None, random.Random(1)) == []


def test_duplicate_team_names_no_cross_contamination():
    # Two clubs sharing "Aces": the buyer story must carry the GOOD Aces'
    # record and the seller story the BAD Aces' record (identity is the
    # object, never the name).
    good = mkteam("Aces", 45, 20, 5, roster=full_roster(n_d=3))
    bad = mkteam("Aces", 15, 45, 4)
    bad.roster = [mkplayer("Chip", "Skater", "C", 0, 84)] + bad.roster
    teams = [good,
             mkteam("Bees", *rec(68, 1.29)),
             mkteam("Cats", *rec(66, 1.21)),
             mkteam("Dogs", *rec(68, 1.06)),
             mkteam("Elks", *rec(64, 1.00)),
             mkteam("Fins", *rec(66, 0.91)),
             mkteam("Gulls", *rec(68, 0.76)),
             mkteam("Hogs", *rec(66, 0.73)),
             bad]
    app = mkapp(teams)
    stories = fire_all(app, date(2027, 2, 22), 8)
    buyer = [s for s in stories if "Aces" in s and
             ("BUYER" in s or "buying" in s or "buyers" in s)]
    assert buyer and any("45-20-5" in s for s in buyer), buyer
    assert not any("15-45-4" in s for s in buyer), buyer
    seller = [s for s in stories if "Aces" in s and
              ("SELLER" in s or "Rental" in s)]
    assert seller and any("15-45-4" in s for s in seller), seller
    assert not any("45-20-5" in s for s in seller), seller


def test_buyers_sellers_split_matches_manager_rule():
    # Independent check: the split is top/bottom third by (pts, wins).
    teams = pool()
    app = mkapp(teams)
    rows = dn._pr_pool_records(
        [t for t in teams
         if getattr(t, "league_name", "") == "National Hockey League"], 82)
    buyers, sellers = dn._td_buyers_sellers(rows)
    ranked = sorted(rows, key=lambda r: (-r[2], -r[5], r[4]))
    assert [r[4] for r in buyers] == [r[4] for r in ranked[:3]]
    assert [r[4] for r in sellers] == [r[4] for r in ranked[-3:]][::-1]


def test_frame_deadline_day_no_zero_days():
    # REV-B: template 2 renders "{days} to the deadline" -- on deadline
    # day that must never read "0 days to the deadline".
    app = mkapp(pool())
    for seed in range(40):
        stories = dn._trade_deadline_stories(app, DEADLINE,
                                             random.Random(seed))
        assert not any("0 days to the deadline" in s for s in stories), \
            stories
        app._daily_news_recent = {}


def test_trade_report_ignores_self_trade():
    # REV-C: a team_a == team_b record is degenerate, not a deal.
    app = mkapp(pool())
    app.trade_history = [mkdeal("2027-02-25 15:30:00", "Aces", "Aces")]
    stories = fire_all(app, DEADLINE, 1)
    assert not any("Aces and Aces" in s for s in stories), stories


def test_trade_report_ignores_blocked_summary():
    # REV-C: execute_trade's BLOCKED preflight records ("No assets
    # moved.") are not completed deals.
    app = mkapp(pool())
    blocked = mkdeal("2027-02-25 15:30:00", "Aces", "Dogs",
                     summary="BLOCKED: Aces would be unable to dress a full "
                             "lineup after this trade. No assets moved.")
    app.trade_history = [blocked]
    stories = fire_all(app, DEADLINE, 1)
    assert not any("BLOCKED" in s for s in stories), stories
    deal = [s for s in stories
            if "aces" in s.lower() and "dogs" in s.lower()
            and ("deal" in s.lower() or "trade" in s.lower())]
    assert not deal, stories


def test_trade_report_ignores_future_dated_trade():
    # REV-C observation: a trade dated after the current game day (but
    # within the window) hasn't happened yet from the reader's
    # perspective -- it must stay silent until its date arrives.
    app = mkapp(pool())
    app.trade_history = [mkdeal("2027-02-28 15:30:00", "Aces", "Dogs")]
    early = dn._trade_deadline_stories(app, date(2027, 2, 26),
                                       random.Random(1))
    deal = [s for s in early
            if "aces" in s.lower() and "dogs" in s.lower()
            and ("deal" in s.lower() or "trade" in s.lower())]
    assert not deal, early
    # ...but it fires once its date is reached.
    app._daily_news_recent = {}
    on_time = dn._trade_deadline_stories(app, date(2027, 2, 28),
                                         random.Random(2))
    deal = [s for s in on_time
            if "aces" in s.lower() and "dogs" in s.lower()
            and ("deal" in s.lower() or "trade" in s.lower())]
    assert deal, on_time


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
