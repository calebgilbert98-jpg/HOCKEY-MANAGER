"""trade_market.py -- AI trade market: listings, bidding wars, trade blocks,
trade-request shopping, and the scouting shortlist.

ADDITIVE layer over Caleb's trade engine. This module CALLS INTO:
  trade_engine: player_trade_value, asset_value, team_needs,
      scout_adjusted_value, trade_vetoes, will_waive_ntc, _cap_ok_after,
      ai_consider_trade, execute_trade
  trade_storylines: stance, ai_initiative_odds, situational_context,
      _rivalry_intensity, _streak
  analytics_scouting: scout_value_tips (JPA-scaled correctness)
  trade_deadline_manager: trade_deadline_date

It never modifies those modules, never reimplements valuation, and never
moves a player except through execute_trade (the single authoritative gate
for cap, clauses, retention, and ownership).

Chris's directives (2026-09-29): NO fixed trade-volume targets -- volume is
dynamic and situation-driven. Full regular-season trading with anti-overboard
guardrails (per-team deal cooldowns, listing caps). League-wide trade-block
board (user + AI). Scouting shortlist for the user and their scouting staff.

Storage: plain dicts on the league object (save/load safe):
  league.trade_market = {
      "listings": [listing...], "seq": int,
      "deal_cooldown": {team_name: iso_date},    # can't INITIATE until after
      "relist_cooldown": {player_id: iso_date},  # can't relist until after
      "rumor_log": [iso_date...],               # rumor flood control
      "shortlist_nudges": {player_id: iso_date},
  }
  league.trade_blocks = {team_name: [player_id, ...]}
  team.scout_shortlist = [{player_id, added_by, date, note}]

A listing:
  {"id", "seller", "player_id", "ask_points", "listed_day", "bidding_close",
   "bids": [{"team", "assets": [asset refs], "round", "day", "status"}],
   "status": "open"|"traded"|"expired"|"pulled",
   "source": "seller_list"|"trade_request"|"agitator"|"soft_sell",
   "rounds": int, "last_round_day": iso, "note": str}

Asset refs inside bids are stored as ("player", id) / ("pick", id) tuples and
resolved at evaluation time, so save/load never pickles live objects.
"""

from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Tuning knobs (all module-level; Chris approves changes)
# ---------------------------------------------------------------------------
RAMP_DAYS = 21                     # deadline ramp length
DEAL_COOLDOWN_DAYS = 14            # per-team initiate cooldown, baseline
DEAL_COOLDOWN_RAMP_DAYS = 7        # per-team initiate cooldown, ramp
MAX_ACTIVE_LISTINGS_BASELINE = 2   # per team, outside the ramp
MAX_ACTIVE_LISTINGS_RAMP = 3       # per team, inside the ramp
MAX_OPEN_LISTINGS_LEAGUE_BASELINE = 12
MAX_OPEN_LISTINGS_LEAGUE_RAMP = 24
BIDDING_WINDOW_BASELINE_DAYS = 7
BIDDING_WINDOW_RAMP_DAYS = 4
RUMOR_CAP_PER_DAY = 3
MIN_BIDDERS_FOR_WAR_RUMOR = 3
ESCALATION_BASE = 0.55             # x boldness x desperation
ASK_DECAY_PER_DAY = 0.02           # final 5 days of ramp only
RELIST_COOLDOWN_DAYS = 14
SHORTLIST_NUDGE_COOLDOWN_DAYS = 14
SHORTLIST_MAX = 25
MAX_AI_BLOCK_SIZE = 5
MAX_BID_ASSETS = 3                 # sanity cap on offer size
TRADE_REQUEST_MONTHLY_CAP = 2      # mirrors headlines.py cap for agitators

NHL = "National Hockey League"


# ---------------------------------------------------------------------------
# Date helpers (ISO strings on the wire; date objects in logic)
# ---------------------------------------------------------------------------
def _iso(d):
    try:
        return d.isoformat() if hasattr(d, "isoformat") else str(d)
    except Exception:
        return ""


def _parse(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _today(app):
    d = getattr(app, "current_date", None)
    if d is None:
        return date.today()
    if isinstance(d, date):
        return d
    parsed = _parse(d)
    return parsed or date.today()


# ---------------------------------------------------------------------------
# Market accessors
# ---------------------------------------------------------------------------
def get_market(league):
    """Lazy-init the market dict on the league. Never raises."""
    try:
        m = getattr(league, "trade_market", None)
        if not isinstance(m, dict):
            m = {"listings": [], "seq": 0, "deal_cooldown": {},
                 "relist_cooldown": {}, "rumor_log": [],
                 "shortlist_nudges": {}}
            league.trade_market = m
        for k, v in (("listings", []), ("seq", 0), ("deal_cooldown", {}),
                     ("relist_cooldown", {}), ("rumor_log", []),
                     ("shortlist_nudges", {})):
            if k not in m:
                m[k] = v
        return m
    except Exception:
        return {"listings": [], "seq": 0, "deal_cooldown": {},
                "relist_cooldown": {}, "rumor_log": [],
                "shortlist_nudges": {}}


def get_trade_blocks(league):
    """{team_name: [player_id, ...]}. Never raises."""
    try:
        b = getattr(league, "trade_blocks", None)
        if not isinstance(b, dict):
            b = {}
            league.trade_blocks = b
        return b
    except Exception:
        return {}


def clear_for_new_season(league):
    """Wipe market + blocks on season rollover. Never raises."""
    try:
        league.trade_market = {"listings": [], "seq": 0, "deal_cooldown": {},
                               "relist_cooldown": {}, "rumor_log": [],
                               "shortlist_nudges": {}}
        league.trade_blocks = {}
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------
def _nhl_teams(league):
    try:
        return [t for t in (getattr(league, "teams", None) or [])
                if getattr(t, "league_name", NHL) == NHL]
    except Exception:
        return []


def _team_by_name(league, name):
    try:
        for t in (getattr(league, "teams", None) or []):
            if getattr(t, "team_name", "") == name:
                return t
    except Exception:
        pass
    return None


def _player_index(league):
    """{player.id: (player, team)} across NHL rosters. Rebuilt per call."""
    idx = {}
    try:
        for t in _nhl_teams(league):
            for p in (getattr(t, "roster", None) or []):
                try:
                    idx[p.id] = (p, t)
                except Exception:
                    continue
    except Exception:
        pass
    return idx


def resolve_player(league, player_id):
    """Return (player, team) or (None, None). Never raises."""
    try:
        return _player_index(league).get(player_id, (None, None))
    except Exception:
        return None, None


def _asset_ref(asset):
    """Serialize an asset to a ref tuple. Never raises."""
    try:
        from game_classes import DraftPick
        if isinstance(asset, DraftPick):
            return ("pick", getattr(asset, "id", None))
    except Exception:
        pass
    try:
        return ("player", asset.id)
    except Exception:
        return ("unknown", None)


def _resolve_asset(league, team, ref):
    """Resolve an asset ref to the live object (must be owned by team)."""
    try:
        kind, aid = ref
        if kind == "player":
            for p in (getattr(team, "roster", None) or []):
                try:
                    if p.id == aid:
                        return p
                except Exception:
                    continue
        elif kind == "pick":
            for _yr, picks in (getattr(team, "draft_picks", None) or {}).items():
                for pk in (picks or []):
                    try:
                        if getattr(pk, "id", None) == aid:
                            return pk
                    except Exception:
                        continue
    except Exception:
        pass
    return None


def _in_ramp(app, league, today):
    """True when today is inside the deadline ramp."""
    try:
        import trade_deadline_manager as tdm
        ddl = tdm.trade_deadline_date(league)
        if ddl is None:
            return False
        if not isinstance(ddl, date):
            ddl = _parse(ddl)
        if ddl is None:
            return False
        return (ddl - today).days <= RAMP_DAYS and (ddl - today).days >= 0
    except Exception:
        return False


def _deadline_passed(app, league, today):
    try:
        import trade_deadline_manager as tdm
        ddl = tdm.trade_deadline_date(league)
        if ddl is None:
            return False
        if not isinstance(ddl, date):
            ddl = _parse(ddl)
        return ddl is not None and today > ddl
    except Exception:
        return False


def _news(app, story, rumor=False):
    """Add a news story, honoring the rumor flood cap. Never raises."""
    try:
        if rumor:
            league = getattr(app, "league", None)
            market = get_market(league)
            today_s = _iso(_today(app))
            log = market.get("rumor_log", [])
            if sum(1 for d in log if d == today_s) >= RUMOR_CAP_PER_DAY:
                return False
            log.append(today_s)
            market["rumor_log"] = log[-30:]
        app.add_news(story)
        return True
    except Exception:
        return False


def _player_label(player):
    try:
        name = player.full_name
    except Exception:
        name = "?"
    try:
        ovr = player.overall_rating()
    except Exception:
        ovr = "?"
    try:
        pos = str(player.primary_position).split(".")[-1]
    except Exception:
        pos = "?"
    return f"{name} ({pos}, {ovr})"


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------
def _active_listings(market, team_name=None, player_id=None):
    out = []
    try:
        for li in market.get("listings", []):
            if li.get("status") != "open":
                continue
            if team_name is not None and li.get("seller") != team_name:
                continue
            if player_id is not None and li.get("player_id") != player_id:
                continue
            out.append(li)
    except Exception:
        pass
    return out


def _on_cooldown(market, team_name, today):
    try:
        until = _parse(market.get("deal_cooldown", {}).get(team_name, ""))
        return until is not None and today <= until
    except Exception:
        return False


def list_piece(app, league, seller, player, source="seller_list", today=None):
    """List a player's piece on the market. Returns the listing or None.

    Validates caps/cooldowns; never raises; never touches the trade engine
    beyond a read-only valuation for the ask.
    """
    try:
        import trade_engine as te
        market = get_market(league)
        today = today or _today(app)
        sname = getattr(seller, "team_name", "")
        pid = player.id
        ramp = _in_ramp(app, league, today)
        # One listing per player.
        if _active_listings(market, player_id=pid):
            return None
        # Relist cooldown.
        rc = _parse(market.get("relist_cooldown", {}).get(pid, ""))
        if rc is not None and today <= rc:
            return None
        # Per-team caps (trade requests always get a slot -- a player who
        # asked out must be shopped).
        if source != "trade_request":
            if _on_cooldown(market, sname, today):
                return None
            cap = MAX_ACTIVE_LISTINGS_RAMP if ramp else MAX_ACTIVE_LISTINGS_BASELINE
            if len(_active_listings(market, team_name=sname)) >= cap:
                return None
        league_cap = (MAX_OPEN_LISTINGS_LEAGUE_RAMP if ramp
                      else MAX_OPEN_LISTINGS_LEAGUE_BASELINE)
        if len(_active_listings(market)) >= league_cap:
            return None
        # Ask = read-only valuation at listing time.
        try:
            ask = int(te.player_trade_value(player))
        except Exception:
            return None
        window = BIDDING_WINDOW_RAMP_DAYS if ramp else BIDDING_WINDOW_BASELINE_DAYS
        market["seq"] = int(market.get("seq", 0) or 0) + 1
        listing = {
            "id": f"TM-{today.year}-{market['seq']:03d}",
            "seller": sname,
            "player_id": pid,
            "ask_points": ask,
            "listed_day": _iso(today),
            "bidding_close": _iso(today + timedelta(days=window)),
            "bids": [],
            "status": "open",
            "source": source,
            "rounds": 0,
            "last_round_day": "",
            "note": "",
        }
        market["listings"].append(listing)
        label = _player_label(player)
        if source == "trade_request":
            _news(app, f"RUMOR: {sname} is shopping {label} after his trade request.", rumor=True)
        elif source == "agitator":
            _news(app, f"RUMOR: {sname} listening on {label} -- star wants a contender.", rumor=True)
        else:
            _news(app, f"RUMOR: {sname} fielding calls on {label}.", rumor=True)
        return listing
    except Exception:
        return None


def _seller_eligible(app, team, stance, ramp):
    """Baseline: sellers + soft-sell bubble teams. Ramp: sellers lead."""
    try:
        import trade_storylines as tsl
        tname = getattr(team, "team_name", "")
        if stance == "seller":
            return True
        if stance == "bubble":
            try:
                streak = tsl._streak(app, tname)
            except Exception:
                streak = 0
            if streak <= -4:  # 4+ game losing streak: soft sell
                return True
        return False
    except Exception:
        return False


def _pick_pieces(team, count):
    """Expiring contracts first, then 29+ vets, by value desc. Never raises."""
    try:
        import trade_engine as te
        roster = list(getattr(team, "roster", None) or [])
        expiring, vets, rest = [], [], []
        for p in roster:
            try:
                yrs = getattr(getattr(p, "contract", None), "years_remaining", 99)
                age = getattr(p, "age", 0)
                if yrs == 1:
                    expiring.append(p)
                elif age >= 29:
                    vets.append(p)
                else:
                    rest.append(p)
            except Exception:
                rest.append(p)
        def _val(p):
            try:
                return te.player_trade_value(p)
            except Exception:
                return 0
        expiring.sort(key=_val, reverse=True)
        vets.sort(key=_val, reverse=True)
        return (expiring + vets)[:count]
    except Exception:
        return []


def _auto_list(app, league, market, today, ramp):
    """Sellers (and soft-sell bubble teams) list pieces. Trade requests
    always get shopped. Never raises."""
    try:
        import trade_storylines as tsl
        user_name = getattr(getattr(app, "user_team", None), "team_name", "")
        for team in _nhl_teams(league):
            tname = getattr(team, "team_name", "")
            if tname == user_name:
                continue  # user's block is manual; requests still auto-list
            # 1) Trade requests are always shopped, ramp or not.
            try:
                for p in (getattr(team, "roster", None) or []):
                    if getattr(p, "transfer_requested", False):
                        list_piece(app, league, team, p,
                                   source="trade_request", today=today)
            except Exception:
                pass
            # 2) Situation-driven seller listings.
            try:
                stance = tsl.stance(app, tname)
            except Exception:
                stance = "neutral"
            if not _seller_eligible(app, team, stance, ramp):
                continue
            have = len(_active_listings(market, team_name=tname))
            cap = MAX_ACTIVE_LISTINGS_RAMP if ramp else MAX_ACTIVE_LISTINGS_BASELINE
            want = cap - have
            if want <= 0:
                continue
            # Baseline: list at most 1 new piece per team per week (throttle).
            if not ramp:
                try:
                    listed_days = [_parse(li.get("listed_day", "")) or today
                                   for li in market.get("listings", [])
                                   if li.get("seller") == tname]
                    if listed_days and (today - max(listed_days)).days < 7:
                        continue
                except Exception:
                    pass
                want = min(want, 1)
            for piece in _pick_pieces(team, want):
                list_piece(app, league, team, piece,
                           source=("soft_sell" if stance == "bubble"
                                   else "seller_list"),
                           today=today)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Bidder matching + bid construction
# ---------------------------------------------------------------------------
def _gm_boldness(app, team):
    """GMIdentity.aggression (0..1); 0.5 default. Never raises."""
    try:
        from ai_gm_identity import gm_identity_from_staff
        mgr = getattr(getattr(app, "game_manager", None), "ai_manager", None)
        ident = None
        if mgr is not None:
            try:
                ident = (mgr.gm_identities or {}).get(getattr(team, "team_name", ""))
            except Exception:
                ident = None
        if ident is None:
            try:
                gm_staff = None
                _tgm = getattr(mgr, "_team_gm", None)
                if callable(_tgm):
                    gm_staff = _tgm(team)
                ident = gm_identity_from_staff(getattr(team, "team_name", ""), gm_staff)
            except Exception:
                ident = None
        if ident is not None:
            return max(0.0, min(1.0, float(getattr(ident, "aggression", 0.5))))
    except Exception:
        pass
    return 0.5


def _pos_code(player):
    """Short position code ('C','LW','RW','LD','RD','G') matching
    trade_engine.team_needs() groups. PlayerPosition enum values are
    already the short codes; plain strings fall back to the tail."""
    try:
        pp = player.primary_position
        code = getattr(pp, "value", None) or str(pp).split(".")[-1]
        return str(code).upper()
    except Exception:
        return ""


def _find_bidders(app, league, listing, today, ramp):
    """Eligible bidders for a listing. Never raises."""
    try:
        import trade_engine as te
        import trade_storylines as tsl
        idx = _player_index(league)
        player, seller = idx.get(listing.get("player_id"), (None, None))
        if player is None or seller is None:
            return []
        sname = listing.get("seller", "")
        user_name = getattr(getattr(app, "user_team", None), "team_name", "")
        try:
            needs_cache = {}
        except Exception:
            needs_cache = {}
        bidders = []
        for team in _nhl_teams(league):
            tname = getattr(team, "team_name", "")
            if tname in (sname, user_name):
                continue
            try:
                stance = tsl.stance(app, tname)
            except Exception:
                stance = "neutral"
            if stance not in ("buyer", "bubble"):
                continue
            # Baseline cooldown: hot GMs sit out initiating, but may bid.
            # (Cooldown gates *initiating*; bidding stays open.)
            # Need-fit: positional need or best-player-available override.
            # Need-fit: team_needs() returns all groups weakest-first; the
            # three weakest are genuine needs (plus a star BPA override).
            try:
                if tname not in needs_cache:
                    needs_cache[tname] = te.team_needs(team)[:3]
                needs = needs_cache[tname]
            except Exception:
                needs = []
            try:
                pos = _pos_code(player)
            except Exception:
                pos = ""
            try:
                ovr = player.overall_rating()
            except Exception:
                ovr = 0
            need_fit = (pos in needs) or \
                (pos == "D" and any(n in ("LD", "RD") for n in needs)) or \
                (ovr >= 84)
            if not need_fit:
                continue
            # Bitter rivals don't deal.
            try:
                if tsl._rivalry_intensity(app, tname, sname) >= 50:
                    continue
            except Exception:
                pass
            # Clause: piece must be movable to this bidder (or waivable).
            try:
                vetoes = te.trade_vetoes(seller, team, [player])
            except Exception:
                vetoes = []
            if vetoes:
                try:
                    ok, _why = te.will_waive_ntc(player, seller, team)
                except Exception:
                    ok = False
                if not ok:
                    continue
            bidders.append(team)
        return bidders
    except Exception:
        return []


def build_bid(app, league, bidder, player, seller, ask_points):
    """Build one opening offer sized to ask x eagerness. Returns a list of
    live asset objects (owned by bidder) or []. Never raises. Read-only
    until the caller executes."""
    try:
        import trade_engine as te
        import trade_storylines as tsl
        from game_classes import DraftPick
        try:
            sit = tsl.situational_context(app, bidder, seller)
            greed = float(sit.get("greed_mult", 1.0))
        except Exception:
            greed = 1.0
        eagerness = 1.0 / max(0.5, min(1.5, greed))
        target = ask_points * eagerness
        # Candidate assets: own tradeable picks (round 1-4), prospects,
        # then roster depth. Never the untouchable core (top-3 by value).
        cands = []
        try:
            bname = getattr(bidder, "team_name", "")
            for _yr, picks in (getattr(bidder, "draft_picks", None) or {}).items():
                for pk in (picks or []):
                    try:
                        if (isinstance(pk, DraftPick)
                                and getattr(pk, "current_team", "") == bname
                                and getattr(pk, "round", 99) in (1, 2, 3, 4)
                                and pk.can_be_traded()):
                            cands.append(("pick", pk))
                    except Exception:
                        continue
        except Exception:
            pass
        try:
            roster = list(getattr(bidder, "roster", None) or [])
            vals = []
            for p in roster:
                try:
                    vals.append((te.player_trade_value(p), p))
                except Exception:
                    continue
            vals.sort(key=lambda t: t[0], reverse=True)
            core_ids = {p.id for _v, p in vals[:3]}
            for _v, p in vals:
                try:
                    if getattr(p, "id", None) in core_ids:
                        continue
                    if te.trade_vetoes(bidder, seller, [p]):
                        continue
                    if getattr(p, "age", 99) <= 23:
                        cands.append(("prospect", p))
                    else:
                        cands.append(("depth", p))
                except Exception:
                    continue
        except Exception:
            pass
        # Cheapest-first fill until target reached (picks before prospects
        # before roster players -- GMs spend futures first).
        def _av(c):
            try:
                return te.asset_value(c[1])
            except Exception:
                return 0
        order = {"pick": 0, "prospect": 1, "depth": 2}
        cands.sort(key=lambda c: (order.get(c[0], 9), _av(c)))
        chosen, total = [], 0
        for _kind, asset in cands:
            if len(chosen) >= MAX_BID_ASSETS:
                break
            # Cap dry-check as we build: bidder must stay legal.
            try:
                if not te._cap_ok_after(bidder, chosen + [asset], [player]):
                    continue
            except Exception:
                pass
            chosen.append(asset)
            total += _av((_kind, asset))
            if total >= target:
                break
        return chosen
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Bidding rounds
# ---------------------------------------------------------------------------
def _evaluate_round(app, league, market, listing, today, ramp, tick=False):
    """Run one bidding round on a listing. Returns True if the listing
    closed (traded/expired/pulled). Never raises."""
    try:
        import trade_engine as te
        import trade_storylines as tsl
        idx = _player_index(league)
        player, seller = idx.get(listing.get("player_id"), (None, None))
        if player is None or seller is None:
            listing["status"] = "expired"
            listing["note"] = "piece unavailable"
            return True
        sname = listing.get("seller", "")
        # Ask decays in the final 5 days of the ramp (seller desperation).
        ask = float(listing.get("ask_points", 0) or 0)
        try:
            close_day = _parse(listing.get("bidding_close", ""))
            if ramp and close_day is not None:
                left = (close_day - today).days
                if 0 <= left <= 5:
                    listed = _parse(listing.get("listed_day", "")) or today
                    age_days = max(0, (today - listed).days)
                    ask = ask * max(0.85, 1.0 - ASK_DECAY_PER_DAY * age_days)
        except Exception:
            pass
        bidders = _find_bidders(app, league, listing, today, ramp)
        if not bidders:
            listing["note"] = "no bidders this round"
            return False
        # War rumor once the field is real.
        if len(bidders) >= MIN_BIDDERS_FOR_WAR_RUMOR and listing.get("rounds", 0) == 0:
            names = ", ".join(getattr(b, "team_name", "?") for b in bidders[:4])
            _news(app, f"BIDDING WAR: {names} are in on {_player_label(player)} "
                       f"({sname} listening).", rumor=True)
        try:
            seller_ctx = tsl.situational_context(app, seller)
        except Exception:
            seller_ctx = None
        patience = max(0.4, 1.0 - 0.15 * int(listing.get("rounds", 0) or 0))
        accepted = []  # (bidder, assets, resp)
        counters = []  # (bidder, assets, resp)
        for bidder in bidders:
            bname = getattr(bidder, "team_name", "")
            try:
                # Escalation: answer last round's counter by adding the
                # wanted asset (if still owned & cap-clean), else sweeten.
                assets = None
                if listing.get("rounds", 0) > 0:
                    assets = _escalate_bid(app, league, listing, bidder,
                                           player, seller, ask)
                if assets is None:
                    assets = build_bid(app, league, bidder, player, seller, ask)
                if not assets:
                    continue
                # Clause waiver stamp for the piece (mirrors deadline path).
                waived = False
                try:
                    if te.trade_vetoes(seller, bidder, [player]):
                        ok, _why = te.will_waive_ntc(player, seller, bidder)
                        if ok and getattr(player, "contract", None) is not None:
                            player.contract.ntc_waiver_for = bname
                            waived = True
                        else:
                            continue
                except Exception:
                    pass
                try:
                    resp = te.ai_consider_trade(
                        bidder, [player], list(assets),
                        user_team=seller, patience=patience,
                        situational=tsl.situational_context(app, bidder, seller))
                except TypeError:
                    resp = te.ai_consider_trade(
                        bidder, [player], list(assets),
                        user_team=seller, patience=patience)
                decision = getattr(resp, "decision", "reject")
                if decision == "accept":
                    accepted.append((bidder, list(assets), resp))
                elif decision == "counter":
                    counters.append((bidder, list(assets), resp))
                    # Stash the counter terms for next round's escalation.
                    _stash_counter(listing, bname, resp, today)
                else:
                    _clear_waiver(player)
                # Clear the waiver unless this bid is still alive.
                if decision != "accept":
                    _clear_waiver(player)
            except Exception:
                continue
        # Winner: highest asset value among accepted; ties -> earliest bid.
        if accepted:
            def _bidval(t):
                try:
                    return sum(te.asset_value(a) for a in t[1])
                except Exception:
                    return 0
            accepted.sort(key=_bidval, reverse=True)
            bidder, assets, _resp = accepted[0]
            if _execute_market_deal(app, league, listing, player, seller,
                                    bidder, assets, today):
                return True
            # Execution blocked (cap/clause at the gate): fall through to
            # counters rather than killing the listing.
        # No winner: keep counters alive for the next round; everyone else
        # may re-enter once with a sweetened offer (same escalation gate).
        if counters:
            listing["note"] = f"{len(counters)} counter(s) in play"
        # Loser consolation: bidders who neither accepted nor countered get
        # priority on the seller's next listing (one round).
        try:
            alive = {getattr(b, "team_name", "") for b, _a, _r in accepted + counters}
            for bidder in bidders:
                bname = getattr(bidder, "team_name", "")
                if bname not in alive:
                    _grant_consolation(market, sname, bname, today)
        except Exception:
            pass
        listing["rounds"] = int(listing.get("rounds", 0) or 0) + 1
        listing["last_round_day"] = _iso(today)
        return False
    except Exception:
        return False


def _clear_waiver(player):
    try:
        if getattr(player, "contract", None) is not None:
            player.contract.ntc_waiver_for = ""
    except Exception:
        pass


def _stash_counter(listing, bidder_name, resp, today=None):
    try:
        bids = listing.setdefault("bids", [])
        bids.append({"team": bidder_name,
                     "want_added": [_asset_ref(a) for a in
                                    (getattr(resp, "want_added", None) or [])],
                     "will_add": [_asset_ref(a) for a in
                                   (getattr(resp, "will_add", None) or [])],
                     "round": int(listing.get("rounds", 0) or 0),
                     "day": _iso(today) if today is not None else _iso(date.today()),
                     "status": "counter"})
        # Keep the log bounded.
        if len(bids) > 40:
            del bids[:len(bids) - 40]
    except Exception:
        pass


def _grant_consolation(market, seller_name, bidder_name, today):
    """Losing bidders get first look at the seller's next listing."""
    try:
        con = market.setdefault("consolation", {})
        con[f"{seller_name}|{bidder_name}"] = _iso(today + timedelta(days=14))
    except Exception:
        pass


def _has_consolation(market, seller_name, bidder_name, today):
    try:
        until = _parse(market.get("consolation", {}).get(
            f"{seller_name}|{bidder_name}", ""))
        return until is not None and today <= until
    except Exception:
        return False


def _escalate_bid(app, league, listing, bidder, player, seller, ask):
    """Answer the seller's last counter: add the wanted asset if owned and
    cap-clean, else sweeten with the next-best asset. Gated by
    ESCALATION_BASE x boldness x desperation. Returns assets or None."""
    try:
        import trade_engine as te
        import trade_storylines as tsl
        bname = getattr(bidder, "team_name", "")
        # Find this bidder's latest counter terms.
        want_refs = []
        try:
            for b in reversed(listing.get("bids", [])):
                if b.get("team") == bname and b.get("status") == "counter":
                    want_refs = b.get("want_added", []) or []
                    break
        except Exception:
            pass
        try:
            sit = tsl.situational_context(app, bidder, seller)
            greed = float(sit.get("greed_mult", 1.0))
        except Exception:
            greed = 1.0
        desperation = max(0.5, min(1.5, 1.0 / max(0.5, greed)))
        boldness = 0.5 + _gm_boldness(app, bidder)  # 0.5..1.5
        import random
        if random.random() > ESCALATION_BASE * boldness * desperation:
            return None  # GM walks from the counter
        base = build_bid(app, league, bidder, player, seller, ask)
        if not base:
            return None
        base_ids = set()
        for a in base:
            try:
                base_ids.add(a.id)
            except Exception:
                try:
                    base_ids.add(getattr(a, "id", None))
                except Exception:
                    pass
        # Add the wanted assets first.
        for ref in want_refs:
            live = _resolve_asset(league, bidder, ref)
            if live is None:
                continue
            try:
                lid = live.id if hasattr(live, "id") else getattr(live, "id", None)
            except Exception:
                lid = None
            if lid in base_ids:
                continue
            try:
                if te.trade_vetoes(bidder, seller, [live]):
                    continue
                if not te._cap_ok_after(bidder, base + [live], [player]):
                    continue
            except Exception:
                pass
            if len(base) >= MAX_BID_ASSETS:
                break
            base.append(live)
        return base
    except Exception:
        return None


def _execute_market_deal(app, league, listing, player, seller, bidder, assets, today):
    """Execute through Caleb's gate. Returns True on a completed deal."""
    try:
        import trade_engine as te
        sname = getattr(seller, "team_name", "")
        bname = getattr(bidder, "team_name", "")
        # Re-stamp the waiver for the winner (cleared after each round).
        try:
            if te.trade_vetoes(seller, bidder, [player]):
                ok, _why = te.will_waive_ntc(player, seller, bidder)
                if ok and getattr(player, "contract", None) is not None:
                    player.contract.ntc_waiver_for = bname
        except Exception:
            pass
        trade = te.execute_trade(
            seller, bidder, [player], list(assets),
            date_str=_iso(today), league=getattr(app, "league", None))
        _clear_waiver(player)
        summary = getattr(trade, "summary", "") or ""
        if summary.startswith("BLOCKED:"):
            print(f"market deal blocked: {summary}")
            return False
        # Deal done.
        listing["status"] = "traded"
        listing["note"] = f"{bname} won"
        try:
            if getattr(player, "transfer_requested", False):
                player.transfer_requested = False
                try:
                    player.happiness = min(100, int(getattr(player, "happiness", 70)) + 15)
                except Exception:
                    pass
        except Exception:
            pass
        # Cooldowns: both sides can't INITIATE for a while (can still bid).
        try:
            market = get_market(league)
            ramp = _in_ramp(app, league, today)
            cd = DEAL_COOLDOWN_RAMP_DAYS if ramp else DEAL_COOLDOWN_DAYS
            until = _iso(today + timedelta(days=cd))
            market["deal_cooldown"][sname] = until
            market["deal_cooldown"][bname] = until
        except Exception:
            pass
        # News: winner + price.
        try:
            pay_label = te.asset_label(assets[0]) if len(assets) == 1 else \
                f"{len(assets)} assets"
        except Exception:
            pay_label = "assets"
        story = (f"TRADE: {bname} acquires {_player_label(player)} from "
                 f"{sname} for {pay_label}.")
        _news(app, story)
        print(f"market: {story}")
        return True
    except Exception as e:
        print(f"market deal error (non-fatal): {e}")
        try:
            _clear_waiver(player)
        except Exception:
            pass
        return False


def _close_expired(app, league, market, listing, today):
    """Bidding window elapsed: seller takes the best counter-able bid at
    90% ask (capitulation) or the listing expires. Never raises."""
    try:
        import trade_engine as te
        idx = _player_index(league)
        player, seller = idx.get(listing.get("player_id"), (None, None))
        if player is None or seller is None:
            listing["status"] = "expired"
            return
        sname = listing.get("seller", "")
        # Best counter-able bid: re-run the last counter terms at 90% ask.
        best = None
        best_val = 0
        seen = set()
        for b in listing.get("bids", []):
            if b.get("status") != "counter":
                continue
            bname = b.get("team", "")
            if bname in seen:
                continue
            seen.add(bname)
            bidder = _team_by_name(league, bname)
            if bidder is None:
                continue
            try:
                assets = [_resolve_asset(league, bidder, ref)
                          for ref in (b.get("want_added", []) or [])]
                assets = [a for a in assets if a is not None]
                base = build_bid(app, league, bidder, player, seller,
                                 float(listing.get("ask_points", 0) or 0) * 0.9)
                for a in base:
                    if a not in assets and len(assets) < MAX_BID_ASSETS:
                        assets.append(a)
                if not assets:
                    continue
                val = sum(te.asset_value(a) for a in assets)
                if val > best_val:
                    best_val = val
                    best = (bidder, assets)
            except Exception:
                continue
        if best is not None:
            bidder, assets = best
            if _execute_market_deal(app, league, listing, player, seller,
                                    bidder, assets, today):
                return
        # Expire: no relist for a while; rumor notes the hold.
        listing["status"] = "expired"
        listing["note"] = "no deal"
        try:
            market["relist_cooldown"][listing.get("player_id")] = \
                _iso(today + timedelta(days=RELIST_COOLDOWN_DAYS))
        except Exception:
            pass
        _news(app, f"{sname} holds onto {_player_label(player)} -- no deal.", rumor=True)
    except Exception:
        try:
            listing["status"] = "expired"
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Trade-request resolution (four paths)
# ---------------------------------------------------------------------------
def _resolve_trade_requests(app, league, market, today, ramp):
    """Daily check on open trade_request listings. Never raises."""
    try:
        import trade_storylines as tsl
        import random
        deadline_gone = _deadline_passed(app, league, today)
        for listing in _active_listings(market):
            try:
                if listing.get("source") != "trade_request":
                    continue
                player, team = resolve_player(league, listing.get("player_id"))
                if player is None or team is None:
                    listing["status"] = "expired"
                    continue
                tname = getattr(team, "team_name", "")
                # Path 2 -- RESCINDED: club turned it around (now buying).
                try:
                    stance = tsl.stance(app, tname)
                except Exception:
                    stance = "neutral"
                if stance == "buyer":
                    # 40%/week rescind roll, evaluated daily.
                    if random.random() < 1.0 - (1.0 - 0.40) ** (1.0 / 7.0):
                        player.transfer_requested = False
                        listing["status"] = "pulled"
                        listing["note"] = "request rescinded"
                        try:
                            player.happiness = min(
                                100, int(getattr(player, "happiness", 70)) + 10)
                        except Exception:
                            pass
                        _news(app, f"{_player_label(player)} rescinds his trade "
                                   f"request -- {tname} are winning again.", rumor=True)
                        continue
                # Path 3 -- DEADLINE PASSES UNTRADED: fallout.
                if deadline_gone and not listing.get("fallout_done"):
                    listing["fallout_done"] = True
                    try:
                        player.happiness = max(
                            1, int(getattr(player, "happiness", 70)) - 15)
                        if hasattr(player, "morale"):
                            player.morale = max(
                                1, int(getattr(player, "morale", 70)) - 10)
                    except Exception:
                        pass
                    _news(app, f"{_player_label(player)} still wants out of "
                               f"{tname} after a quiet deadline.", rumor=True)
                    continue
                # Path 4 -- PULLED: seller pulls a core piece pre-deadline.
                if not deadline_gone and not ramp:
                    try:
                        ovr = player.overall_rating()
                    except Exception:
                        ovr = 0
                    if ovr >= 85 and random.random() < 0.02:
                        listing["status"] = "pulled"
                        listing["note"] = "seller pulled"
                        try:
                            player.happiness = min(
                                100, int(getattr(player, "happiness", 70)) + 5)
                        except Exception:
                            pass
                        # The request does NOT clear -- next window reopens it.
                        _news(app, f"{tname} no longer shopping "
                                   f"{_player_label(player)}.", rumor=True)
            except Exception:
                continue
    except Exception:
        pass


def ambition_agitation_tick(app):
    """Monthly: cup-ambition stars on sellers agitate for a trade.

    Called next to headlines.monthly_trade_request_check (additive -- that
    function is untouched). Never raises.
    """
    try:
        import trade_storylines as tsl
        import random
        league = getattr(app, "league", None)
        if league is None:
            return 0
        fired = 0
        for team in _nhl_teams(league):
            if fired >= TRADE_REQUEST_MONTHLY_CAP:
                break
            tname = getattr(team, "team_name", "")
            try:
                if tsl.stance(app, tname) != "seller":
                    continue
            except Exception:
                continue
            for p in (getattr(team, "roster", None) or []):
                if fired >= TRADE_REQUEST_MONTHLY_CAP:
                    break
                try:
                    if getattr(p, "transfer_requested", False):
                        continue
                    amb = getattr(p, "ambition", "")
                    if amb not in ("cup", "stanley_cup"):
                        continue
                    ovr = p.overall_rating()
                    if ovr < 82:
                        continue
                    # Cup-chasing star, losing team: monthly agitation roll.
                    if random.random() < 0.25:
                        p.transfer_requested = True
                        fired += 1
                        _news(app, f"TRADE REQUEST: {_player_label(p)} wants "
                                   f"out of {tname} -- chasing a Cup.", rumor=False)
                except Exception:
                    continue
        return fired
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Trade blocks (league-wide board data)
# ---------------------------------------------------------------------------
def refresh_trade_blocks(app, league):
    """Regenerate AI trade blocks from listings + stance. Mirrors the user's
    manual block. Never raises."""
    try:
        import trade_engine as te
        import trade_storylines as tsl
        market = get_market(league)
        blocks = get_trade_blocks(league)
        idx = _player_index(league)
        user_name = getattr(getattr(app, "user_team", None), "team_name", "")
        # User's block: mirror the manual list. Entries are usually
        # player objects; accept id-dicts too (post-load shapes vary).
        try:
            ublock = []
            for entry in (getattr(getattr(app, "user_team", None),
                                  "trade_block", None) or []):
                try:
                    if hasattr(entry, "id"):
                        ublock.append(entry.id)
                    elif isinstance(entry, dict) and \
                            entry.get("player_id") is not None:
                        ublock.append(entry["player_id"])
                except Exception:
                    continue
            if user_name:
                blocks[user_name] = ublock
        except Exception:
            pass
        for team in _nhl_teams(league):
            tname = getattr(team, "team_name", "")
            if tname == user_name:
                continue
            try:
                stance = tsl.stance(app, tname)
            except Exception:
                stance = "neutral"
            ids = []
            # Active listings' pieces first.
            for li in _active_listings(market, team_name=tname):
                pid = li.get("player_id")
                if pid is not None and pid not in ids:
                    ids.append(pid)
            # Stance-driven depth: sellers add vets, bubble adds one.
            if stance == "seller" and len(ids) < MAX_AI_BLOCK_SIZE:
                for p in _pick_pieces(team, MAX_AI_BLOCK_SIZE - len(ids)):
                    try:
                        if p.id not in ids:
                            ids.append(p.id)
                    except Exception:
                        continue
            elif stance == "bubble" and len(ids) < MAX_AI_BLOCK_SIZE:
                extra = _pick_pieces(team, 1)
                for p in extra:
                    try:
                        if p.id not in ids:
                            ids.append(p.id)
                    except Exception:
                        continue
            blocks[tname] = ids[:MAX_AI_BLOCK_SIZE]
    except Exception:
        pass


def block_availability_note(app, league, player_id):
    """Truthful availability note for a block player. Never raises."""
    try:
        market = get_market(league)
        for li in _active_listings(market, player_id=player_id):
            src = li.get("source", "")
            if src == "trade_request":
                return "Trade request -- motivated seller"
            if src == "agitator":
                return "Star wants a contender -- listening"
            return "On the block: seller is listening"
        return "Soft sell: asking high"
    except Exception:
        return "Available"


# ---------------------------------------------------------------------------
# Scouting shortlist
# ---------------------------------------------------------------------------
def get_shortlist(user_team):
    """[{player_id, added_by, date, note}]. Never raises."""
    try:
        sl = getattr(user_team, "scout_shortlist", None)
        if not isinstance(sl, list):
            sl = []
            user_team.scout_shortlist = sl
        return sl
    except Exception:
        return []


def add_to_shortlist(user_team, player, added_by="user", note="", today=None):
    """Add a player to the shortlist. Returns True if added. Never raises."""
    try:
        sl = get_shortlist(user_team)
        pid = player.id
        for e in sl:
            if e.get("player_id") == pid:
                return False
        if len(sl) >= SHORTLIST_MAX:
            # Oldest user-added drops with the cap; scout suggestions rotate.
            for i, e in enumerate(sl):
                if e.get("added_by") == "user":
                    del sl[i]
                    break
            else:
                sl.pop(0)
        sl.append({"player_id": pid, "added_by": added_by,
                   "date": _iso(today) if today is not None
                   else date.today().isoformat(),
                   "note": note or ""})
        return True
    except Exception:
        return False


def remove_from_shortlist(user_team, player_id):
    """Never raises."""
    try:
        sl = get_shortlist(user_team)
        for i, e in enumerate(sl):
            if e.get("player_id") == player_id:
                del sl[i]
                return True
    except Exception:
        pass
    return False


def refresh_scout_suggestions(app, league):
    """Ask each user scout for value tips (JPA-scaled correctness) and
    stage them as suggestions on the shortlist. Never raises.

    Suggestions are entries with added_by=<scout name> and note starting
    with 'SUGGESTED:'. The user promotes or dismisses them in the UI.
    """
    try:
        import analytics_scouting as asc
        user_team = getattr(app, "user_team", None)
        if user_team is None:
            return 0
        # Gather scouts from staff.
        scouts = []
        try:
            for s in (getattr(user_team, "staff", None) or []):
                try:
                    from scouting import is_scout
                    if is_scout(s):
                        scouts.append(s)
                except Exception:
                    # Fallback: role-name heuristic.
                    role = str(getattr(s, "role", "")).lower()
                    if "scout" in role:
                        scouts.append(s)
        except Exception:
            pass
        if not scouts:
            return 0
        players, teams = [], list(_nhl_teams(league))
        try:
            for t in teams:
                players.extend(list(getattr(t, "roster", None) or []))
        except Exception:
            pass
        sl = get_shortlist(user_team)
        have = {e.get("player_id") for e in sl}
        added = 0
        import random
        rng = random.Random()
        for scout in scouts[:4]:  # cap: 4 scouts contribute
            try:
                tips = asc.scout_value_tips(scout, players, teams,
                                            user_team=user_team, limit=3,
                                            rng=rng)
            except Exception:
                continue
            try:
                sname = getattr(scout, "full_name", getattr(scout, "name", "Scout"))
            except Exception:
                sname = "Scout"
            for tip in (tips or []):
                try:
                    p = tip.get("player") if isinstance(tip, dict) else None
                    if p is None:
                        continue
                    if p.id in have or len(sl) >= SHORTLIST_MAX:
                        continue
                    reason = ""
                    try:
                        reason = tip.get("reason", "") or ""
                    except Exception:
                        pass
                    sl.append({"player_id": p.id, "added_by": sname,
                               "date": _iso(_today(app)),
                               "note": f"SUGGESTED: {reason}"[:120]})
                    have.add(p.id)
                    added += 1
                except Exception:
                    continue
        return added
    except Exception:
        return 0


def check_shortlist_nudges(app, league, market=None, today=None):
    """Nudge the user when a shortlisted player hits the market or a trade
    block. Bounded: one nudge per player per 14 days. Never raises."""
    try:
        market = market or get_market(league)
        today = today or _today(app)
        user_team = getattr(app, "user_team", None)
        if user_team is None:
            return
        sl = get_shortlist(user_team)
        if not sl:
            return
        nudged = market.get("shortlist_nudges", {})
        # Collect market + block player ids.
        on_market = {li.get("player_id") for li in _active_listings(market)}
        blocks = get_trade_blocks(league)
        on_blocks = {}
        for tname, ids in blocks.items():
            for pid in (ids or []):
                on_blocks.setdefault(pid, tname)
        for e in sl:
            try:
                pid = e.get("player_id")
                if pid is None:
                    continue
                last = _parse(nudged.get(pid, ""))
                if last is not None and (today - last).days < SHORTLIST_NUDGE_COOLDOWN_DAYS:
                    continue
                player, pteam = resolve_player(league, pid)
                if player is None:
                    continue
                who = e.get("added_by", "user")
                whotxt = f"your target" if who == "user" else f"{who}'s target"
                if pid in on_market:
                    tname = pteam.team_name if pteam else "?"
                    _news(app, f"SHORTLIST: {whotxt} {_player_label(player)} "
                               f"just hit the market ({tname} listening).")
                    nudged[pid] = _iso(today)
                elif pid in on_blocks:
                    _news(app, f"SHORTLIST: {whotxt} {_player_label(player)} "
                               f"is on {on_blocks[pid]}'s trade block.")
                    nudged[pid] = _iso(today)
            except Exception:
                continue
        market["shortlist_nudges"] = nudged
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Daily driver + deadline tick
# ---------------------------------------------------------------------------
def process_market(app, league, today=None):
    """Daily market driver. Year-round: baseline listing/bidding most of the
    season, ramp cadence in the final 21 days, trade-request shopping always
    on. Cheap no-op when nothing is listed. Never raises."""
    try:
        today = today or _today(app)
        market = get_market(league)
        ramp = _in_ramp(app, league, today)
        _auto_list(app, league, market, today, ramp)
        # One bidding round per listing per day (deadline day uses ticks).
        if not _is_deadline_day(app, league, today):
            for listing in list(_active_listings(market)):
                try:
                    last = _parse(listing.get("last_round_day", ""))
                    if last is not None and last >= today:
                        continue
                    close = _parse(listing.get("bidding_close", ""))
                    if close is not None and today > close:
                        _close_expired(app, league, market, listing, today)
                        continue
                    _evaluate_round(app, league, market, listing, today, ramp)
                except Exception:
                    continue
        _resolve_trade_requests(app, league, market, today, ramp)
        refresh_trade_blocks(app, league)
        check_shortlist_nudges(app, league, market, today)
        # Sweep stale rumor log.
        try:
            market["rumor_log"] = [d for d in market.get("rumor_log", [])
                                   if (_parse(d) or today) >= today - timedelta(days=2)]
        except Exception:
            pass
    except Exception as e:
        print(f"trade_market.process_market error (non-fatal): {e}")


def _is_deadline_day(app, league, today):
    try:
        import trade_deadline_manager as tdm
        ddl = tdm.trade_deadline_date(league)
        if ddl is None:
            return False
        if not isinstance(ddl, date):
            ddl = _parse(ddl)
        return ddl == today
    except Exception:
        return False


def process_deadline_tick(app, league, mgr=None):
    """Advance one bidding round per open listing per deadline tick.
    Called from the deadline clock; the organic tick cap is untouched."""
    try:
        today = _today(app)
        market = get_market(league)
        for listing in list(_active_listings(market)):
            try:
                close = _parse(listing.get("bidding_close", ""))
                if close is not None and today > close:
                    _close_expired(app, league, market, listing, today)
                    continue
                _evaluate_round(app, league, market, listing, today,
                                ramp=True, tick=True)
            except Exception:
                continue
        _resolve_trade_requests(app, league, market, today, ramp=True)
        refresh_trade_blocks(app, league)
    except Exception as e:
        print(f"trade_market.process_deadline_tick error (non-fatal): {e}")
