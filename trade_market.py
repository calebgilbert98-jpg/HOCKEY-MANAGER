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

# Deadline heat (refinement 2026-09-29): trading runs all season, and a
# continuous heat curve -- not a flat 21-day mode -- accelerates listing
# volume, escalation, ask decay, and rumor intensity as the deadline nears.
# Heat scales guardrails only; volume stays situation-driven, never quota'd.
HEAT_WINDOW_DAYS = 90
HEAT_BEATS = (0.5, 0.75, 0.9)

# Headliner overlay (refinement 2026-09-29): superstar pieces cost packages.
# Modeled on real deals (see the design doc): Eichel'21
# (Tuch + Krebs + 1st + 2nd), Karlsson'18 (Norris + Tierney + DeMelo + 1st +
# 2nd + more), Tkachuk'22 (Huberdeau + Weegar + prospect + 1st), Stone'19
# (rental: Brannstrom + Lindberg + 2nd). The 1-for-1 exception
# (Hall<->Larsson, Jones<->Johansen): young-controllable for
# young-controllable at a clear positional need. trade_engine.py is NEVER
# touched -- this is a market-layer overlay only.
HEADLINER_OVR = 85
HEADLINER_YOUNG_OVR = 83
HEADLINER_YOUNG_AGE = 26
HEADLINER_MIN_ASSETS = 3
HEADLINER_EXCEPTION_AGE = 27
HEADLINER_EXCEPTION_YEARS = 3
HEADLINER_EXCEPTION_OVR_GAP = 6

# Block engagement (refinement 2026-09-29): blocks refresh on stance flips,
# new trade requests, and long-term injuries to key players -- never stale.
INJURY_LONG_TERM_GAMES = 20
# Offers to the user on their block players: one per listing per week.
USER_OFFER_THROTTLE_DAYS = 7

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
    """Legacy boolean: now heat >= 0.5 (~the last month), kept for callers."""
    return deadline_heat(app, league, today) >= 0.5


def _days_to_deadline(app, league, today):
    """Days until the trade deadline, or None if unknown."""
    try:
        import trade_deadline_manager as tdm
        ddl = tdm.trade_deadline_date(league)
        if ddl is None:
            return None
        if not isinstance(ddl, date):
            ddl = _parse(ddl)
        if ddl is None:
            return None
        return (ddl - today).days
    except Exception:
        return None


def deadline_heat(app, league, today):
    """Continuous deadline heat: 0.0 far out .. 1.0 on deadline day.

    Curved (x^1.5) so the market simmers early and spikes late -- a real
    deadline arc, not a flat ramp mode. Trading runs all season until the
    deadline; the deadline is the conscious decision point for roster
    direction, and heat rising toward it is how the game says so."""
    d = _days_to_deadline(app, league, today)
    if d is None:
        return 0.0
    if d <= 0:
        return 1.0
    base = 1.0 - min(1.0, d / HEAT_WINDOW_DAYS)
    return round(base ** 1.5, 3)


def _heat_params(heat):
    """Guardrail scaling from heat. No quotas -- volume stays
    situation-driven; heat only moves the ceilings and the tempo."""
    return {
        "max_team": 2 + int(heat * 2.99),       # 2 -> 4 listings per team
        "league_cap": 12 + int(heat * 16.99),   # 12 -> 28 open listings
        "window": max(2, 7 - int(heat * 5.99)), # 7 -> 2 day bidding window
        "rumor_cap": 3 + int(heat * 3.99),      # 3 -> 6 rumors/day
        "esc_mult": 0.7 + 0.8 * heat,           # escalation gate: 0.7x -> 1.5x
        "decay_mult": 1.0 + 2.0 * heat,         # ask decay: 1x -> 3x
        "throttle": max(2, int(7 * (1.0 - heat) + 1)),  # auto-list days: 7 -> 2
    }


def _heat_beat_stories(app, league, market, heat, today):
    """League-wide 'decision time' beats as heat crosses thresholds upward.
    One story per threshold per season; reset with the market each season."""
    try:
        fired = set(market.setdefault("heat_beats", []))
        import trade_storylines as tsl
        user_name = getattr(getattr(app, "user_team", None), "team_name", "")
        for beat in HEAT_BEATS:
            if heat < beat or beat in fired:
                continue
            fired.add(beat)
            sellers, buyers = [], []
            for team in _nhl_teams(league):
                tname = getattr(team, "team_name", "")
                if tname == user_name:
                    continue
                try:
                    st = tsl.stance(app, tname)
                except Exception:
                    continue
                city = getattr(team, "city", None) or tname
                if st == "seller":
                    sellers.append(city)
                elif st == "buyer":
                    buyers.append(city)
            sc = ", ".join(sellers[:4]) or "no one yet"
            if beat == HEAT_BEATS[0]:
                story = (f"Decision time in {sc}: the deadline is a month out "
                         f"and the sellers are making their calls.")
            elif beat == HEAT_BEATS[1]:
                bc = ", ".join(buyers[:4]) or "the contenders"
                story = (f"Two weeks to the deadline -- {len(sellers)} teams "
                         f"listening, phones heating up. {bc} are loading up.")
            else:
                story = (f"Deadline week: bold moves expected as decision time "
                         f"arrives in {sc}.")
            _news(app, story)
        market["heat_beats"] = sorted(fired)
    except Exception:
        pass


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


def _news(app, story, rumor=False, rumor_cap=None):
    """Add a news story, honoring the rumor flood cap. Never raises."""
    try:
        if rumor:
            league = getattr(app, "league", None)
            market = get_market(league)
            today_s = _iso(_today(app))
            cap = rumor_cap if rumor_cap is not None else RUMOR_CAP_PER_DAY
            log = market.get("rumor_log", [])
            if sum(1 for d in log if d == today_s) >= cap:
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


def list_piece(app, league, seller, player, source="seller_list", today=None,
               params=None):
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
        heat = deadline_heat(app, league, today)
        ramp = heat >= 0.5
        params = params or _heat_params(heat)
        # One listing per player.
        if _active_listings(market, player_id=pid):
            return None
        # Relist cooldown.
        rc = _parse(market.get("relist_cooldown", {}).get(pid, ""))
        if rc is not None and today <= rc:
            return None
        # Per-team caps (trade requests always get a slot -- a player who
        # asked out must be shopped; user block listings always get a slot
        # too, so AI GMs can bid on them).
        if source not in ("trade_request", "user_block"):
            if _on_cooldown(market, sname, today):
                return None
            cap = params.get("max_team", MAX_ACTIVE_LISTINGS_RAMP)
            if len(_active_listings(market, team_name=sname)) >= cap:
                return None
        league_cap = params.get("league_cap", MAX_OPEN_LISTINGS_LEAGUE_RAMP)
        if len(_active_listings(market)) >= league_cap:
            return None
        # Ask = read-only valuation at listing time.
        try:
            ask = int(te.player_trade_value(player))
        except Exception:
            return None
        window = params.get("window", BIDDING_WINDOW_BASELINE_DAYS)
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
            _news(app, f"RUMOR: {sname} is shopping {label} after his trade request.", rumor=True,
                  rumor_cap=params.get("rumor_cap"))
        elif source == "agitator":
            _news(app, f"RUMOR: {sname} listening on {label} -- star wants a contender.", rumor=True,
                  rumor_cap=params.get("rumor_cap"))
        elif source == "user_block":
            _news(app, f"RUMOR: {sname} has put {label} on the block -- GMs are calling.", rumor=True,
                  rumor_cap=params.get("rumor_cap"))
        else:
            _news(app, f"RUMOR: {sname} fielding calls on {label}.", rumor=True,
                  rumor_cap=params.get("rumor_cap"))
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


def _auto_list(app, league, market, today, ramp, params=None, heat=0.0):
    """Sellers (and soft-sell bubble teams) list pieces. Trade requests
    always get shopped. Heat drives the cadence: weekly baseline throttle
    tightens toward daily as the deadline nears. Never raises."""
    try:
        import trade_storylines as tsl
        params = params or _heat_params(heat)
        throttle = params.get("throttle", 7)
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
                                   source="trade_request", today=today,
                                   params=params)
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
            cap = params.get("max_team", MAX_ACTIVE_LISTINGS_RAMP)
            want = cap - have
            if want <= 0:
                continue
            # Heat-driven throttle: at heat 0 list at most 1 new piece per
            # team per week; near the deadline, up to 2 every 2 days.
            try:
                listed_days = [_parse(li.get("listed_day", "")) or today
                               for li in market.get("listings", [])
                               if li.get("seller") == tname]
                if listed_days and (today - max(listed_days)).days < throttle:
                    continue
            except Exception:
                pass
            want = min(want, 2 if ramp else 1)
            for piece in _pick_pieces(team, want):
                list_piece(app, league, team, piece,
                           source=("soft_sell" if stance == "bubble"
                                   else "seller_list"),
                           today=today, params=params)
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


# ---------------------------------------------------------------------------
# Headliner overlay (refinement 2026-09-29): superstar pieces cost packages.
# trade_engine.py / player_trade_value() are NEVER touched -- this is a
# market-layer overlay only.
# ---------------------------------------------------------------------------
def _is_headliner(player):
    """A Quinn Hughes-caliber piece: 85+ overall, or 83+ at age <= 26."""
    try:
        ovr = player.overall_rating()
        age = getattr(player, "age", 99)
        return ovr >= HEADLINER_OVR or (age <= HEADLINER_YOUNG_AGE
                                       and ovr >= HEADLINER_YOUNG_OVR)
    except Exception:
        return False


def _need_hit(need0, asset):
    """Does the asset fill the seller's #1 positional need? A generic
    defenseman (code 'D') fills an LD/RD need -- handedness isn't modeled
    for plain DEFENSE players. Never raises."""
    try:
        if need0 is None:
            return False
        code = _pos_code(asset)
        if code == need0:
            return True
        return code == "D" and need0 in ("LD", "RD")
    except Exception:
        return False


def _headliner_package_ok(app, league, player, seller, bidder, assets):
    """(ok, reason). A headliner normally costs a package: 3+ assets with
    a young roster player and a 1st (or blue-chip prospect). The rare
    1-for-1 'hockey trade' exception (Hall<->Larsson, Jones<->Johansen):
    young-controllable for young-controllable at the seller's clear #1
    positional need. Rentals get the Stone'19 shape: 2+ assets with a top
    prospect/young roster piece and an early pick. Never raises."""
    try:
        import trade_engine as te
        from game_classes import DraftPick
        if not _is_headliner(player):
            return True, "not a headliner"
        live = [a for a in assets if a is not None]
        try:
            piece_ovr = player.overall_rating()
        except Exception:
            piece_ovr = 0
        try:
            piece_yrs = getattr(getattr(player, "contract", None),
                                "years_remaining", 99) or 99
        except Exception:
            piece_yrs = 99

        def _is_pick(a):
            return isinstance(a, DraftPick)

        def _grade(a):
            return str(getattr(a, "potential_grade", "") or "").upper()

        # --- 1-for-1 exception: young + controllable + at the seller's #1
        # --- positional need (Hall 24 for Larsson 23, Edmonton's RHD hole).
        if len(live) == 1 and not _is_pick(live[0]):
            a = live[0]
            try:
                ovr = a.overall_rating()
            except Exception:
                ovr = 0
            try:
                yrs = getattr(getattr(a, "contract", None),
                              "years_remaining", 0) or 0
            except Exception:
                yrs = 0
            try:
                need0 = (te.team_needs(seller) or [None])[0]
            except Exception:
                need0 = None
            if (getattr(a, "age", 99) <= HEADLINER_EXCEPTION_AGE
                    and yrs >= HEADLINER_EXCEPTION_YEARS
                    and abs(ovr - piece_ovr) <= HEADLINER_EXCEPTION_OVR_GAP
                    and _need_hit(need0, a)):
                return True, "one-for-one exception"
        prospects = [a for a in live if not _is_pick(a)
                     and getattr(a, "age", 99) <= 23
                     and _grade(a) in ("A+", "A", "A-", "B+", "B")]
        young_roster = [a for a in live if not _is_pick(a)
                        and getattr(a, "age", 99) <= HEADLINER_YOUNG_AGE]
        firsts = [a for a in live if _is_pick(a)
                  and getattr(a, "round", 99) == 1]
        picks12 = [a for a in live if _is_pick(a)
                   and getattr(a, "round", 99) <= 2]
        # --- rental discount: pending UFA headliner (Stone'19). ---
        if piece_yrs == 1:
            if len(live) >= 2 and (prospects or young_roster) and picks12:
                return True, "rental package"
            return False, "rental headliner needs prospect/young roster + early pick"
        # --- the standard package (Eichel'21, Karlsson'18, Tkachuk'22). ---
        bluechip = any(getattr(a, "age", 99) <= 22 for a in prospects)
        if (len(live) >= HEADLINER_MIN_ASSETS and young_roster
                and (firsts or bluechip)):
            return True, "headliner package"
        return False, "headliner price: package with young roster player + 1st/top prospect"
    except Exception:
        return True, "check failed open"


def _shape_headliner_bid(app, league, bidder, player, seller, chosen, cands,
                         target):
    """Shape a headliner bid into a real package: a young roster player and
    a 1st (or blue-chip prospect) lead the offer. Swaps in from the
    candidate pool when needed; respects MAX_BID_ASSETS and the cap; never
    raises; returns the (possibly unchanged) chosen list."""
    try:
        import trade_engine as te
        from game_classes import DraftPick
        have_ids = {getattr(a, "id", None) for a in chosen}

        def _add(asset):
            try:
                if asset is None or getattr(asset, "id", None) in have_ids:
                    return
                if len(chosen) < MAX_BID_ASSETS:
                    try:
                        if not te._cap_ok_after(bidder, chosen + [asset],
                                                [player]):
                            return
                    except Exception:
                        pass
                    chosen.append(asset)
                    have_ids.add(getattr(asset, "id", None))
                    return
                # Swap out the lowest-value asset that isn't a 1st.
                drop_i, drop_v = -1, None
                for i, a in enumerate(chosen):
                    if (isinstance(a, DraftPick)
                            and getattr(a, "round", 99) == 1):
                        continue
                    try:
                        v = te.asset_value(a)
                    except Exception:
                        v = 0
                    if drop_v is None or v < drop_v:
                        drop_v, drop_i = v, i
                if drop_i < 0:
                    return
                trial = [a for i, a in enumerate(chosen) if i != drop_i]
                trial.append(asset)
                try:
                    if not te._cap_ok_after(bidder, trial, [player]):
                        return
                except Exception:
                    pass
                have_ids.discard(getattr(chosen[drop_i], "id", None))
                chosen[drop_i] = asset
                have_ids.add(getattr(asset, "id", None))
            except Exception:
                pass

        def _best(pred):
            best, bestv = None, -1
            for _kind, a in cands:
                if getattr(a, "id", None) in have_ids:
                    continue
                if not pred(a):
                    continue
                try:
                    if te.trade_vetoes(bidder, seller, [a]):
                        continue
                except Exception:
                    pass
                try:
                    v = te.player_trade_value(a)
                except Exception:
                    v = 0
                if v > bestv:
                    best, bestv = a, v
            return best

        if not any((not isinstance(a, DraftPick))
                   and getattr(a, "age", 99) <= HEADLINER_YOUNG_AGE
                   for a in chosen):
            _add(_best(lambda a: (not isinstance(a, DraftPick))
                       and getattr(a, "age", 99) <= HEADLINER_YOUNG_AGE))
        if not any(isinstance(a, DraftPick)
                   and getattr(a, "round", 99) == 1 for a in chosen):
            first = _best(lambda a: isinstance(a, DraftPick)
                          and getattr(a, "round", 99) == 1)
            if first is None:
                first = _best(lambda a: (not isinstance(a, DraftPick))
                              and getattr(a, "age", 99) <= 22
                              and str(getattr(a, "potential_grade", "")
                                      ).upper() in ("A+", "A", "A-", "B+", "B"))
            _add(first)
        return chosen
    except Exception:
        return chosen


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
        # Headliner pieces get package-shaped offers (see overlay above).
        if _is_headliner(player):
            chosen = _shape_headliner_bid(app, league, bidder, player, seller,
                                          chosen, cands, target)
        return chosen
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Bidding rounds
# ---------------------------------------------------------------------------
def _evaluate_round(app, league, market, listing, today, ramp, tick=False,
                    params=None, heat=0.0):
    """Run one bidding round on a listing. Returns True if the listing
    closed (traded/expired/pulled). Never raises.

    User-sale listings (source user_block): AI bids are routed to the user
    through the existing negotiation path -- never auto-executed. The
    headliner overlay holds AI sellers out for a real package.
    """
    try:
        import trade_engine as te
        import trade_storylines as tsl
        params = params or _heat_params(heat)
        idx = _player_index(league)
        player, seller = idx.get(listing.get("player_id"), (None, None))
        if player is None or seller is None:
            listing["status"] = "expired"
            listing["note"] = "piece unavailable"
            return True
        sname = listing.get("seller", "")
        user_name = getattr(getattr(app, "user_team", None), "team_name", "")
        user_sale = (sname == user_name)
        # Ask decays near the listing's close: the window and the rate both
        # scale with heat (seller desperation rises toward the deadline).
        ask = float(listing.get("ask_points", 0) or 0)
        try:
            close_day = _parse(listing.get("bidding_close", ""))
            if close_day is not None:
                left = (close_day - today).days
                decay_window = 2 + int(heat * 8)
                if 0 <= left <= decay_window:
                    listed = _parse(listing.get("listed_day", "")) or today
                    age_days = max(0, (today - listed).days)
                    rate = ASK_DECAY_PER_DAY * params.get("decay_mult", 1.0)
                    ask = ask * max(0.85, 1.0 - rate * age_days)
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
                       f"({sname} listening).", rumor=True,
                  rumor_cap=params.get("rumor_cap"))
        try:
            seller_ctx = tsl.situational_context(app, seller)
        except Exception:
            seller_ctx = None
        patience = max(0.4, 1.0 - 0.15 * int(listing.get("rounds", 0) or 0))
        accepted = []  # (bidder, assets, resp)
        counters = []  # (bidder, assets, resp)
        user_bids = []  # (bidder, assets) for user-sale listings
        for bidder in bidders:
            bname = getattr(bidder, "team_name", "")
            try:
                # Escalation: answer last round's counter by adding the
                # wanted asset (if still owned & cap-clean), else sweeten.
                assets = None
                if listing.get("rounds", 0) > 0:
                    assets = _escalate_bid(app, league, listing, bidder,
                                           player, seller, ask,
                                           esc_mult=params.get("esc_mult", 1.0))
                if assets is None:
                    assets = build_bid(app, league, bidder, player, seller, ask)
                if not assets:
                    continue
                # User sale: no engine evaluation here -- the best bid goes
                # to the user as a real negotiation offer.
                if user_sale:
                    user_bids.append((bidder, list(assets)))
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
                    # Headliner overlay: the seller holds out for a package
                    # instead of accepting a light offer.
                    ok, why = _headliner_package_ok(app, league, player,
                                                    seller, bidder,
                                                    list(assets))
                    if ok:
                        accepted.append((bidder, list(assets), resp))
                    else:
                        counters.append((bidder, list(assets), resp))
                        _stash_counter(listing, bname, resp, today)
                        listing["note"] = f"holding out for a package ({why})"
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
        if user_sale:
            # Best AI bid becomes a real offer in the user's negotiation box.
            if user_bids:
                def _uv(t):
                    try:
                        return sum(te.asset_value(a) for a in t[1])
                    except Exception:
                        return 0
                user_bids.sort(key=_uv, reverse=True)
                top_bidder, top_assets = user_bids[0]
                _deliver_user_offer(app, league, market, listing, top_bidder,
                                    top_assets, today)
                listing["note"] = "offer(s) sent to you"
            listing["rounds"] = int(listing.get("rounds", 0) or 0) + 1
            listing["last_round_day"] = _iso(today)
            return False
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
        # A headliner holdout keeps its note (don't overwrite with a count).
        if counters and "holding out" not in listing.get("note", ""):
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


def _escalate_bid(app, league, listing, bidder, player, seller, ask,
                  esc_mult=1.0):
    """Answer the seller's last counter: add the wanted asset if owned and
    cap-clean, else sweeten with the next-best asset. Gated by
    ESCALATION_BASE x esc_mult (heat) x boldness x desperation.
    Returns assets or None."""
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
        if random.random() > ESCALATION_BASE * esc_mult * boldness * desperation:
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
            # Headliner overlay: no capitulation for scraps -- the seller
            # would rather hold the superstar than take a light package.
            ok, why = _headliner_package_ok(app, league, player, seller,
                                            bidder, assets)
            if ok and _execute_market_deal(app, league, listing, player, seller,
                                           bidder, assets, today):
                return
            if not ok:
                listing["note"] = f"held the headliner ({why})"
        # Expire: no relist for a while; rumor notes the hold.
        listing["status"] = "expired"
        listing["note"] = listing.get("note") or "no deal"
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
# ---------------------------------------------------------------------------
# Block engagement (refinement 2026-09-29)
# ---------------------------------------------------------------------------
def _deliver_user_offer(app, league, market, listing, bidder, assets, today):
    """Route the best AI bid on the user's block player to the user through
    the existing negotiation path (trade_negotiation.incoming_offer --
    inbox, never a popup). Throttled: one offer per listing per
    USER_OFFER_THROTTLE_DAYS. The offer is also recorded on the listing so
    headless tests can assert engagement. Never raises."""
    try:
        lid = listing.get("id", "")
        last = _parse((market.get("user_offer_log", {}) or {}).get(lid, ""))
        if last is not None and (today - last).days < USER_OFFER_THROTTLE_DAYS:
            return False
        idx = _player_index(league)
        player, _seller = idx.get(listing.get("player_id"), (None, None))
        if player is None:
            return False
        bname = getattr(bidder, "team_name", "?")
        try:
            import trade_negotiation as tneg
            tneg.incoming_offer(app, bidder, list(assets), player_wanted=player)
        except Exception as e:
            print(f"user offer deliver failed (non-fatal): {e}")
        try:
            market.setdefault("user_offer_log", {})[lid] = _iso(today)
            listing["user_offer"] = {"team": bname, "day": _iso(today),
                                     "assets": [_asset_ref(a) for a in assets]}
            listing["note"] = f"offer sent to you by {bname}"
        except Exception:
            pass
        _news(app, f"RUMOR: {bname} has made an offer for "
                    f"{_player_label(player)} (your block).", rumor=True)
        return True
    except Exception:
        return False


def _sync_user_block(app, league, market, today, params):
    """Mirror the user's manual trade block into market listings so AI GMs
    can bid on them (source user_block -- always a slot, never auto-sold).
    Pull listings for players removed from the block. Never raises."""
    try:
        user_team = getattr(app, "user_team", None)
        if user_team is None:
            return
        uname = getattr(user_team, "team_name", "")
        block_ids = set()
        for src in (getattr(user_team, "trade_block", None) or [],
                    getattr(app, "trade_block", None) or []):
            for entry in src:
                try:
                    pid = entry.id if hasattr(entry, "id") else None
                    if pid is None and isinstance(entry, dict):
                        pid = entry.get("player_id")
                    if pid is not None:
                        block_ids.add(pid)
                except Exception:
                    continue
        for pid in block_ids:
            if _active_listings(market, player_id=pid):
                continue
            player, pteam = resolve_player(league, pid)
            if (player is None or pteam is None
                    or getattr(pteam, "team_name", "") != uname):
                continue
            list_piece(app, league, user_team, player, source="user_block",
                       today=today, params=params)
        # Pull listings whose player left the block.
        for li in _active_listings(market, team_name=uname):
            if (li.get("source") == "user_block"
                    and li.get("player_id") not in block_ids):
                li["status"] = "pulled"
                li["note"] = "removed from your block"
    except Exception:
        pass


def _key_players(team):
    """The players whose long-term injury moves a GM's block: top-6 skaters
    by trade value plus the top goalie. Never raises."""
    try:
        import trade_engine as te
        roster = list(getattr(team, "roster", None) or [])
        skaters, goalies = [], []
        for p in roster:
            try:
                (goalies if _pos_code(p) == "G" else skaters).append(p)
            except Exception:
                skaters.append(p)
        def _val(p):
            try:
                return te.player_trade_value(p)
            except Exception:
                return 0
        skaters.sort(key=_val, reverse=True)
        goalies.sort(key=_val, reverse=True)
        return skaters[:6] + goalies[:1]
    except Exception:
        return []


def note_situation_change(app, league, market, today):
    """Event-driven trade-block refresh: stance flips (incl. buyer->seller),
    new trade requests, and long-term injuries to key players. Blocks never
    go stale. Called daily from process_market. Never raises."""
    try:
        import trade_engine as te
        import trade_storylines as tsl
        user_name = getattr(getattr(app, "user_team", None), "team_name", "")
        # 1) Stance flips.
        prev = market.setdefault("prev_stance", {})
        for team in _nhl_teams(league):
            tname = getattr(team, "team_name", "")
            if tname == user_name:
                continue
            try:
                stance = tsl.stance(app, tname)
            except Exception:
                continue
            old = prev.get(tname)
            prev[tname] = stance
            if old is not None and old != stance:
                refresh_trade_blocks(app, league)
                city = getattr(team, "city", None) or tname
                if stance == "seller":
                    _news(app, f"Decision time in {city}: the "
                               f"{tname} are selling -- block updated.")
                elif stance == "buyer" and old == "seller":
                    _news(app, f"{tname} flip from sellers to buyers -- off "
                               f"the block, hunting.")
        # 2) New trade requests (they're auto-listed; the block follows).
        known = set(market.setdefault("known_requests", []))
        fresh = False
        for team in _nhl_teams(league):
            for p in (getattr(team, "roster", None) or []):
                try:
                    if (getattr(p, "transfer_requested", False)
                            and p.id not in known):
                        known.add(p.id)
                        fresh = True
                except Exception:
                    continue
        if fresh:
            market["known_requests"] = sorted(known)[-200:]
            refresh_trade_blocks(app, league)
        # 3) Long-term injuries to key players.
        flags = set(market.setdefault("injury_flags", []))
        hit = False
        for team in _nhl_teams(league):
            tname = getattr(team, "team_name", "")
            for p in _key_players(team):
                try:
                    if (getattr(p, "is_injured", False)
                            and getattr(p, "games_remaining_injured", 0)
                            >= INJURY_LONG_TERM_GAMES
                            and p.id not in flags):
                        flags.add(p.id)
                        hit = True
                        if tname != user_name:
                            _news(app, f"RUMOR: {tname} shopping for help "
                                       f"after the {_player_label(p)} injury.",
                                  rumor=True)
                except Exception:
                    continue
        if hit:
            market["injury_flags"] = sorted(flags)[-200:]
            refresh_trade_blocks(app, league)
    except Exception:
        pass


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
# ---------------------------------------------------------------------------
# Unified shortlist (refinement 2026-09-29): ONE surface.
#
# ShortlistManager's "Trade Targets" category is the canonical store.
# The legacy team.scout_shortlist store is migrated once (never duplicated)
# and retired. Scout suggestions, user targets, and market/block nudges all
# read and write the same list -- there is no import step and no second tab.
# ---------------------------------------------------------------------------
_SHORTLIST_CATEGORY = "Trade Targets"
_SUGGEST_PREFIX = "SUGGESTED by "


def _shortlist_mgr():
    """The canonical shortlist store. None if unavailable. Never raises."""
    try:
        from shortlist_system import ShortlistManager
        return ShortlistManager()
    except Exception:
        return None


def get_unified_targets():
    """Every entry on the ONE unified surface, as dicts
    {player_id, player_name, notes, priority, date_added}. Never raises."""
    out = []
    try:
        mgr = _shortlist_mgr()
        if mgr is None:
            return []
        for e in (mgr.get_entries_by_category(_SHORTLIST_CATEGORY) or []):
            try:
                out.append({
                    "player_id": getattr(e, "player_id", ""),
                    "player_name": getattr(e, "player_name", ""),
                    "notes": getattr(e, "notes", "") or "",
                    "priority": getattr(e, "priority", 2),
                    "date_added": str(getattr(e, "date_added", "") or ""),
                })
            except Exception:
                continue
    except Exception:
        pass
    return out


def _add_raw_target(pid_str, name, notes, priority=2):
    """Low-level add with exact notes. Returns True on a new add. Never raises."""
    try:
        mgr = _shortlist_mgr()
        if mgr is None or pid_str in (None, ""):
            return False
        _enforce_target_cap()
        return bool(mgr.add_player(str(pid_str), str(name or "?"),
                                   _SHORTLIST_CATEGORY,
                                   notes=(notes or "")[:200],
                                   priority=priority))
    except Exception:
        return False


def _enforce_target_cap():
    """Keep the unified surface at SHORTLIST_MAX: oldest user-added entries
    rotate out first, then oldest suggestions. Never raises."""
    try:
        mgr = _shortlist_mgr()
        if mgr is None:
            return
        entries = mgr.get_entries_by_category(_SHORTLIST_CATEGORY) or []
        while len(entries) >= SHORTLIST_MAX:
            def _is_suggest(e):
                return str(getattr(e, "notes", "") or "").startswith(_SUGGEST_PREFIX)
            cands = [e for e in entries if not _is_suggest(e)] or entries
            cands.sort(key=lambda e: str(getattr(e, "date_added", "") or ""))
            victim = cands[0]
            try:
                mgr.remove_player(getattr(victim, "player_id", ""),
                                  _SHORTLIST_CATEGORY)
            except Exception:
                break
            entries = mgr.get_entries_by_category(_SHORTLIST_CATEGORY) or []
    except Exception:
        pass


def add_target(player, source="user", note="", priority=2):
    """Add a target to the unified surface. source: "user" or a scout's
    name (stored as a SUGGESTED-by note with the scout's confidence band).
    Returns True on a new add. Never raises."""
    try:
        if player is None:
            return False
        pid = getattr(player, "id", None)
        name = getattr(player, "full_name", None) or getattr(player, "name", "?")
        if pid is None:
            return False
        if source == "user":
            notes = (note or "").strip()
        else:
            notes = f"{_SUGGEST_PREFIX}{source}: {(note or '').strip()}".strip()
        return _add_raw_target(pid, name, notes, priority)
    except Exception:
        return False


def remove_target(player_id):
    """Remove from the unified surface. Never raises."""
    try:
        mgr = _shortlist_mgr()
        if mgr is None:
            return False
        return bool(mgr.remove_player(str(player_id), _SHORTLIST_CATEGORY))
    except Exception:
        return False


def _target_source(notes):
    """(kind, display) for a unified entry's notes: ('scout', name),
    ('user', tag), or ('user', 'You'). Never raises."""
    try:
        n = (notes or "").strip()
        if n.startswith(_SUGGEST_PREFIX):
            rest = n[len(_SUGGEST_PREFIX):]
            scout, _, _rest = rest.partition(":")
            return "scout", (scout.strip() or "Scout")
        if n.startswith("[") and "]" in n:
            tag = n[1:].partition("]")[0].strip()
            return "user", (tag or "You")
    except Exception:
        pass
    return "user", "You"


def migrate_shortlist_once(app, league, user_team, market):
    """One-time migration: legacy team.scout_shortlist entries move into the
    unified ShortlistManager surface. Never duplicates; the legacy list is
    retired afterwards. Returns the number moved. Never raises."""
    try:
        if market.get("shortlist_migrated"):
            return 0
        moved = 0
        legacy = getattr(user_team, "scout_shortlist", None) or []
        for e in legacy:
            try:
                if not isinstance(e, dict):
                    continue
                pid = e.get("player_id")
                if pid is None:
                    continue
                player, _team = resolve_player(league, pid)
                name = (player.full_name if player is not None else str(pid))
                added_by = e.get("added_by", "user") or "user"
                note = (e.get("note", "") or "").strip()
                if added_by == "user":
                    notes = note
                else:
                    # Old scout format: added_by=<scout>, note="SUGGESTED: ...".
                    if note.upper().startswith("SUGGESTED:"):
                        note = note[len("SUGGESTED:"):].strip()
                    notes = f"{_SUGGEST_PREFIX}{added_by}: {note}".strip()
                if _add_raw_target(pid, name, notes):
                    moved += 1
            except Exception:
                continue
        try:
            user_team.scout_shortlist = []  # legacy store retired
        except Exception:
            pass
        market["shortlist_migrated"] = True
        return moved
    except Exception:
        return 0


# --- Legacy shims: same names/shapes as before, now backed by the unified
# --- surface so older callers keep working.
def get_shortlist(user_team):
    """[{player_id, added_by, date, note}]. Backed by the unified surface.
    Never raises."""
    out = []
    for t in get_unified_targets():
        try:
            pid = t.get("player_id")
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                pass
            notes = t.get("notes", "") or ""
            kind, who = _target_source(notes)
            if kind == "scout":
                note = notes.split(":", 1)[1].strip() if ":" in notes else ""
                added_by = who
            elif notes.startswith("[") and "]" in notes:
                note = notes.partition("]")[2].strip()
                added_by = who if who != "You" else "user"
            else:
                note, added_by = notes, "user"
            out.append({"player_id": pid, "added_by": added_by,
                        "date": str(t.get("date_added", ""))[:10],
                        "note": note})
        except Exception:
            continue
    return out


def add_to_shortlist(user_team, player, added_by="user", note="", today=None):
    """Add a player to the shortlist. Returns True if added. Never raises."""
    try:
        if added_by == "user":
            return add_target(player, source="user", note=note or "")
        return _add_raw_target(getattr(player, "id", ""),
                               getattr(player, "full_name", "?"),
                               f"[{added_by}] {(note or '').strip()}".strip())
    except Exception:
        return False


def remove_from_shortlist(user_team, player_id):
    """Never raises."""
    return remove_target(player_id)


def refresh_scout_suggestions(app, league):
    """Ask each user scout for value tips (JPA-scaled correctness) and stage
    them on the unified surface as SUGGESTED-by entries carrying the scout's
    name and confidence band (High/Medium/Low -- the truth is never shown).
    Dedupes by player id. Never raises. Returns the number of new tips."""
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
        import random
        rng = random.Random()
        added = 0
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
                    reason = ""
                    conf = ""
                    try:
                        reason = tip.get("reason", "") or ""
                        conf = tip.get("confidence", "") or ""
                    except Exception:
                        pass
                    note = f"({conf} confidence): {reason}".strip() if conf \
                        else reason
                    if add_target(p, source=sname, note=note[:140]):
                        added += 1
                except Exception:
                    continue
        return added
    except Exception:
        return 0


def check_shortlist_nudges(app, league, market=None, today=None):
    """Nudge the user when a unified-surface target hits the market or a
    trade block. Bounded: one nudge per player per 14 days. Never raises."""
    try:
        market = market or get_market(league)
        today = today or _today(app)
        targets = get_unified_targets()
        if not targets:
            return
        nudged = market.get("shortlist_nudges", {})
        # Collect market + block player ids.
        on_market = {li.get("player_id") for li in _active_listings(market)}
        blocks = get_trade_blocks(league)
        on_blocks = {}
        for tname, ids in blocks.items():
            for pid in (ids or []):
                on_blocks.setdefault(pid, tname)
        for t in targets:
            try:
                pid_raw = t.get("player_id")
                pid = pid_raw
                try:
                    pid = int(pid_raw)
                except (TypeError, ValueError):
                    pass
                nkey = str(pid_raw)
                last = _parse(nudged.get(nkey, ""))
                if (last is not None
                        and (today - last).days < SHORTLIST_NUDGE_COOLDOWN_DAYS):
                    continue
                player, pteam = resolve_player(league, pid)
                if player is None:
                    player, _t2 = resolve_player(league, pid_raw)
                if player is None:
                    continue
                kind, who = _target_source(t.get("notes", ""))
                whotxt = (f"{who}'s suggestion" if kind == "scout"
                          else "your target")
                if pid in on_market or pid_raw in on_market:
                    tname = pteam.team_name if pteam else "?"
                    _news(app, f"SHORTLIST: {whotxt} {_player_label(player)} "
                               f"just hit the market ({tname} listening).")
                    nudged[nkey] = _iso(today)
                elif pid in on_blocks or pid_raw in on_blocks:
                    _news(app, f"SHORTLIST: {whotxt} {_player_label(player)} "
                               f"is on {on_blocks.get(pid, on_blocks.get(pid_raw))}'s trade block.")
                    nudged[nkey] = _iso(today)
            except Exception:
                continue
        market["shortlist_nudges"] = nudged
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Daily driver + deadline tick
# ---------------------------------------------------------------------------
def process_market(app, league, today=None):
    """Daily market driver. Year-round: trading runs the whole regular
    season until the deadline; a continuous heat curve (not a flat ramp)
    accelerates listing volume, escalation, ask decay, and rumor intensity
    as the deadline nears. Trade-request shopping always on. Cheap no-op
    when nothing is listed. Never raises."""
    try:
        today = today or _today(app)
        market = get_market(league)
        heat = deadline_heat(app, league, today)
        ramp = heat >= 0.5
        params = _heat_params(heat)
        _heat_beat_stories(app, league, market, heat, today)
        # Event-driven engagement: stance flips, new requests, key injuries.
        note_situation_change(app, league, market, today)
        # One-time shortlist migration (legacy store -> unified surface).
        try:
            user_team = getattr(app, "user_team", None)
            if user_team is not None:
                migrate_shortlist_once(app, league, user_team, market)
        except Exception:
            pass
        # The user's manual block becomes listings AI GMs bid on.
        _sync_user_block(app, league, market, today, params)
        _auto_list(app, league, market, today, ramp, params=params, heat=heat)
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
                    _evaluate_round(app, league, market, listing, today, ramp,
                                    params=params, heat=heat)
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
        heat = deadline_heat(app, league, today)
        params = _heat_params(heat)
        for listing in list(_active_listings(market)):
            try:
                close = _parse(listing.get("bidding_close", ""))
                if close is not None and today > close:
                    _close_expired(app, league, market, listing, today)
                    continue
                _evaluate_round(app, league, market, listing, today,
                                ramp=True, tick=True, params=params, heat=1.0)
            except Exception:
                continue
        _resolve_trade_requests(app, league, market, today, ramp=True)
        refresh_trade_blocks(app, league)
    except Exception as e:
        print(f"trade_market.process_deadline_tick error (non-fatal): {e}")
