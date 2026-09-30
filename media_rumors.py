"""media_rumors.py -- Read-only media rumor engine for the Trade Deadline Center.

Replaces the old hardcoded fictional rumor lines with rumors generated from
REAL league state: trade-block players, expiring contracts, low-morale stars,
seller fire-sales, contender needs, hot/cold streaks, coaching pressure,
rivalry heat, award races, prospect standouts, injury returns, market
temperature, and completed deadline deals.

Design rules (per Chris):
  * The media is wrong sometimes. Every rumor carries a veracity roll made
    INSIDE this engine: most rumors are grounded in real state, ~1 in 4 is
    systematically distorted (wrong team, wrong player, or wrong number).
    Veracity is NEVER labelled in the UI -- you can't tell which is which.
  * Strictly read-only: nothing here mutates league state, calls a tick, or
    drives gameplay effects (no morale hits, no trade effects).
  * Seeded determinism: the batch is stable per in-game day, so re-opening
    the window doesn't reshuffle everything. Pass fresh=True (or a new seed)
    to file a new batch of stories.

Public API:
  generate_rumors(deadline_manager=None, game_manager=None, league=None,
                  count=8, seed=None, fresh=False) -> list[str]
      The rumor lines for the UI. Honest fallback line when no league data
      is available (never fabricated).

  get_impact_players(game_manager=None, league=None, deadline_manager=None,
                     count=8) -> list[dict]
      Real availability data for the "Impact Players Available" panel.
      Each dict: {name, pos, team, status, value}. Empty list when nothing
      is actually available (the panel renders an honest placeholder row).

  invalidate_cache() -- drop the per-day cache.
"""

import random
import hashlib

# ---------------------------------------------------------------------------
# Tuning knobs (Chris approves changes)
# ---------------------------------------------------------------------------
# Fraction of rumors that carry a systematic distortion ("the media is
# wrong and makes things up"). Rolled per rumor inside the engine.
DISTORTION_RATE = 0.25
# Cap so a bad roll can't distort an outsized share of one batch.
MAX_DISTORTION_SHARE = 0.35
# Max rumors from one subject family per batch -- forces a varied mix of
# subjects instead of five goaltending-need lines in a row.
MAX_PER_FAMILY = 2

DEFAULT_RUMOR_COUNT = 8

_cache = {}          # (date_iso, count) -> list[str]
_fresh_nonce = [0]   # bumped by fresh=True so Refresh files new stories


# ---------------------------------------------------------------------------
# Small guarded helpers over real league state
# ---------------------------------------------------------------------------
def _pname(p):
    try:
        return f"{getattr(p, 'first_name', '')} {getattr(p, 'last_name', '')}".strip() or "Unknown player"
    except Exception:
        return "Unknown player"


def _pos_str(p):
    try:
        pos = getattr(p, "primary_position", None)
        v = getattr(pos, "value", None)
        return str(v or pos or "?")
    except Exception:
        return "?"


def _pos_group(pos):
    s = str(pos or "").upper()
    if s == "G":
        return "G"
    if s in ("LD", "RD", "D"):
        return "D"
    return "F"


def _ovr(p):
    try:
        return int(p.overall_rating())
    except Exception:
        return 0


def _gp(p):
    try:
        return int(getattr(p, "games_played", 0) or getattr(getattr(p, "stats", None), "games_played", 0) or 0)
    except Exception:
        return 0


def _pts(p):
    try:
        return int(getattr(p, "points", 0) or getattr(getattr(p, "stats", None), "points", 0) or 0)
    except Exception:
        return 0


def _goals(p):
    try:
        return int(getattr(p, "goals", 0) or getattr(getattr(p, "stats", None), "goals", 0) or 0)
    except Exception:
        return 0


def _city(team):
    try:
        return str(getattr(team, "city", None) or getattr(team, "team_name", "Unknown"))
    except Exception:
        return "Unknown"


def _nhl_teams(league):
    try:
        return [t for t in (getattr(league, "teams", []) or [])
                if getattr(t, "league_name", "") == "National Hockey League"]
    except Exception:
        return []


def _date_iso(game_manager):
    try:
        d = getattr(game_manager, "current_date", None)
        if d is not None and hasattr(d, "isoformat"):
            return d.isoformat()
    except Exception:
        pass
    return "nodate"


def _seed_for(date_iso, seed, fresh):
    if seed is not None:
        return int(seed)
    h = hashlib.sha256(f"{date_iso}|rumors".encode("utf-8")).hexdigest()
    base = int(h[:8], 16)
    if fresh:
        _fresh_nonce[0] += 1
        base ^= (_fresh_nonce[0] * 0x9E3779B1) & 0xFFFFFFFF
    return base


def _standings_rows(league, teams):
    """[(team, W, L, OTL, Points, pct)] sorted by Points desc. Pure read."""
    rows = []
    try:
        table = getattr(league, "standings", {}) or {}
        by_name = {getattr(t, "team_name", ""): t for t in teams}
        for name, row in table.items():
            t = by_name.get(name)
            if t is None:
                continue
            try:
                w = int(row.get("W", 0)); l = int(row.get("L", 0))
                otl = int(row.get("OTL", 0)); pts = int(row.get("Points", 0))
            except Exception:
                continue
            gp = w + l + otl
            pct = (pts / (2 * gp)) if gp else 0.0
            rows.append((t, w, l, otl, pts, pct))
    except Exception:
        pass
    rows.sort(key=lambda r: r[4], reverse=True)
    return rows


class _Ctx:
    """Snapshot of the real state the rumor builders may read. Read-only."""

    def __init__(self, game_manager=None, league=None, deadline_manager=None):
        self.game_manager = game_manager
        self.league = league
        self.deadline_manager = deadline_manager
        self.teams = _nhl_teams(league) if league is not None else []
        self.team_by_name = {}
        self.roster = []          # [(team, player)]
        self.cities = []
        for t in self.teams:
            try:
                self.team_by_name[getattr(t, "team_name", "")] = t
                self.cities.append(_city(t))
                for p in (getattr(t, "roster", []) or []):
                    self.roster.append((t, p))
            except Exception:
                continue
        self.standings = _standings_rows(league, self.teams)
        # player name pools by position group, for wrong-player distortions
        self.player_pool = {"F": [], "D": [], "G": []}
        for _t, p in self.roster:
            try:
                g = _pos_group(_pos_str(p))
                self.player_pool[g].append((_pname(p), _pos_str(p)))
            except Exception:
                continue


def _resolve_league(game_manager, league, deadline_manager):
    if league is not None:
        return league
    gm = game_manager
    if gm is None and deadline_manager is not None:
        gm = getattr(deadline_manager, "game_manager", None)
    if gm is not None:
        return getattr(gm, "league", None)
    return None


# ---------------------------------------------------------------------------
# Subject builders -- each returns rumor specs grounded in real state.
#
# spec = {
#   "family": str,
#   "templates": [str],          # rendered with bind via str.format
#   "bind": dict,                # real entity values
#   "team_keys": [...],          # bind keys holding team cities
#   "player_keys": [...],         # bind keys holding player names
#   "pos_of": {player_key: pos_key},  # companion position keys
#   "num_keys": [...],           # bind keys holding ints
# }
# ---------------------------------------------------------------------------
def _spec(family, templates, bind, team_keys=(), player_keys=(),
          pos_of=None, num_keys=()):
    return {"family": family, "templates": list(templates),
            "bind": dict(bind), "team_keys": list(team_keys),
            "player_keys": list(player_keys), "pos_of": dict(pos_of or {}),
            "num_keys": list(num_keys)}


def _b_user_block(ctx):
    out = []
    try:
        gm = ctx.game_manager
        block = list(getattr(gm, "trade_block", []) or [])
        user_team = getattr(gm, "user_team", None)
        city = _city(user_team) if user_team is not None else "Your club"
        for p in block[:4]:
            name, pos = _pname(p), _pos_str(p)
            out.append(_spec(
                "user_block",
                ["{team} has officially placed {player} ({pos}) on the trade block, per the club.",
                 "{team} is taking calls on {player} ({pos}).",
                 "{player} ({pos}) is available out of {team} -- asking price unknown."],
                {"team": city, "player": name, "pos": pos},
                team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
    except Exception:
        pass
    return out


def _b_ai_block(ctx):
    out = []
    try:
        import trade_market as tm
        blocks = tm.get_trade_blocks(ctx.league) or {}
        seen = 0
        for team_name, pids in blocks.items():
            if seen >= 6:
                break
            team = ctx.team_by_name.get(team_name)
            city = _city(team) if team is not None else str(team_name)
            for pid in list(pids or [])[:2]:
                try:
                    p, _listed_team = tm.resolve_player(ctx.league, pid)
                except Exception:
                    p = None
                if p is None:
                    continue
                name, pos = _pname(p), _pos_str(p)
                out.append(_spec(
                    "ai_block",
                    ["{team} has quietly made {player} ({pos}) available.",
                     "{player} ({pos}) can be had from {team} for the right package.",
                     "{player} ({pos}) is drawing interest on {team}'s trade block -- multiple teams asking."],
                    {"team": city, "player": name, "pos": pos},
                    team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
                seen += 1
                if seen >= 6:
                    break
    except Exception:
        pass
    return out


def _b_rental_expiring(ctx):
    out = []
    try:
        bottom = {getattr(t, "team_name", "") for t, _w, _l, _o, _p, _pc in ctx.standings[len(ctx.standings) // 2:]}
        cands = []
        for t, p in ctx.roster:
            try:
                c = getattr(p, "contract", None)
                yrs = getattr(c, "years_remaining", None)
                if yrs is None or yrs > 1:
                    continue
                ovr = _ovr(p)
                if ovr < 76 or _pos_group(_pos_str(p)) == "G":
                    continue
                cands.append((ovr, t, p))
            except Exception:
                continue
        cands.sort(key=lambda c: c[0], reverse=True)
        for ovr, t, p in cands[:6]:
            out.append(_spec(
                "rental",
                ["With {player} ({pos}) unsigned past this season, {team} is listening.",
                 "{player} ({pos}) heads a deep rental class in {team} -- contenders are circling.",
                 "{team} will move {player} ({pos}) rather than lose him for nothing."],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p)},
                team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
    except Exception:
        pass
    return out


def _b_unhappy_star(ctx):
    out = []
    try:
        cands = []
        for t, p in ctx.roster:
            try:
                ovr = _ovr(p)
                if ovr < 80:
                    continue
                morale = int(getattr(p, "morale", 70) or 70)
                happy = int(getattr(p, "happiness", 70) or 70)
                if morale >= 45 and happy >= 45:
                    continue
                cands.append((ovr, t, p))
            except Exception:
                continue
        cands.sort(key=lambda c: c[0], reverse=True)
        for ovr, t, p in cands[:4]:
            out.append(_spec(
                "unhappy",
                ["Those around {player} describe a frustrated star in {team} -- \"he wants a bigger role.\"",
                 "Whispers out of {team}: {player}'s camp is unhappy with how things are going.",
                 "Rival execs are watching {player} closely -- the mood in {team} sounds tense."],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p)},
                team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
    except Exception:
        pass
    return out


def _b_seller_firesale(ctx):
    out = []
    try:
        import trade_market as tm
        blocks = tm.get_trade_blocks(ctx.league) or {}
        n = len(ctx.standings)
        for t, w, l, otl, pts, pct in ctx.standings[max(0, n - 6):]:
            try:
                tname = getattr(t, "team_name", "")
                n_block = len(blocks.get(tname, []) or [])
                rentals = sum(1 for _t2, p in ctx.roster if _t2 is t
                              and (getattr(getattr(p, "contract", None), "years_remaining", 9) or 9) <= 1
                              and _ovr(p) >= 76)
                if n_block == 0 and rentals < 2:
                    continue
                out.append(_spec(
                    "firesale",
                    ["{team} is open for business -- rival execs expect a full fire sale.",
                     "Everything is on the table in {team} as the losses pile up."],
                    {"team": _city(t)},
                    team_keys=["team"]))
            except Exception:
                continue
    except Exception:
        pass
    return out


def _need_word(group):
    return {"F": "a top-six forward", "D": "blue-line", "G": "goaltending"}.get(group, "depth")


def _b_contender_need(ctx):
    out = []
    try:
        for t, w, l, otl, pts, pct in ctx.standings[:6]:
            try:
                counts = {"F": 0, "D": 0, "G": 0}
                for _t2, p in ctx.roster:
                    if _t2 is not t:
                        continue
                    if _ovr(p) >= 80:
                        counts[_pos_group(_pos_str(p))] += 1
                weak = min(counts, key=lambda g: counts[g])
                if counts[weak] >= 4:
                    continue
                out.append(_spec(
                    "contender_need",
                    ["{team} is in the market for {need} help.",
                     "Contenders are loading up -- {team}'s shopping list starts with {need}.",
                     "{team} has made {need} its top deadline priority."],
                    {"team": _city(t), "need": _need_word(weak)},
                    team_keys=["team"]))
            except Exception:
                continue
    except Exception:
        pass
    return out


def _b_hot_streak(ctx):
    out = []
    try:
        cands = []
        for t, p in ctx.roster:
            try:
                if _pos_group(_pos_str(p)) == "G":
                    continue
                st = int(getattr(p, "current_point_streak", 0) or 0)
                if st >= 6 and _ovr(p) >= 74:
                    cands.append((st, t, p))
            except Exception:
                continue
        cands.sort(key=lambda c: c[0], reverse=True)
        for st, t, p in cands[:4]:
            out.append(_spec(
                "hot_streak",
                ["{player} has points in {streak} straight -- and the price keeps climbing, say scouts.",
                 "{player}'s {streak}-game point streak has GMs around the league taking notice."],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p), "streak": st},
                team_keys=["team"], player_keys=["player"],
                pos_of={"player": "pos"}, num_keys=["streak"]))
    except Exception:
        pass
    return out


def _b_cold_drought(ctx):
    out = []
    try:
        cands = []
        for t, p in ctx.roster:
            try:
                if _pos_group(_pos_str(p)) == "G":
                    continue
                ovr = _ovr(p)
                gp = _gp(p)
                if ovr < 82 or gp < 15:
                    continue
                ppg = _pts(p) / gp if gp else 0
                if ppg >= 0.45:
                    continue
                cands.append((ovr, t, p, ppg))
            except Exception:
                continue
        cands.sort(key=lambda c: c[0], reverse=True)
        for ovr, t, p, ppg in cands[:4]:
            out.append(_spec(
                "cold",
                ["{player}'s quiet season has rival GMs circling for a buy-low move.",
                 "The slump in {team} continues for {player} -- \"someone will bet on the bounce-back.\""],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p)},
                team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
    except Exception:
        pass
    return out


def _b_hot_goalie(ctx):
    out = []
    try:
        cands = []
        for t, p in ctx.roster:
            try:
                if _pos_group(_pos_str(p)) != "G":
                    continue
                st = getattr(p, "stats", None)
                sv = float(getattr(st, "save_percentage", 0.0) or 0.0)
                gp = _gp(p)
                if sv >= 0.925 and gp >= 12:
                    cands.append((sv, t, p))
            except Exception:
                continue
        cands.sort(key=lambda c: c[0], reverse=True)
        for sv, t, p in cands[:3]:
            out.append(_spec(
                "hot_goalie",
                ["{player} is stealing games in {team} -- .{svp} hockey has the league buzzing.",
                 "Scouts rave about {player}: \"he's the reason {team} is still in this.\""],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p),
                 "svp": str(int(round(sv * 1000))).zfill(3)},
                team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
    except Exception:
        pass
    return out


def _b_coach_pressure(ctx):
    out = []
    try:
        n = len(ctx.standings)
        for t, w, l, otl, pts, pct in ctx.standings[max(0, n - 5):]:
            try:
                gp = w + l + otl
                if gp < 10:
                    continue
                out.append(_spec(
                    "coach_pressure",
                    ["The seat is getting warm behind {team}'s bench -- {w}-{l}-{otl} has the vultures circling.",
                     "Patience is wearing thin with {team}'s coaching staff."],
                    {"team": _city(t), "w": w, "l": l, "otl": otl},
                    team_keys=["team"], num_keys=["w", "l", "otl"]))
            except Exception:
                continue
    except Exception:
        pass
    return out


def _b_rivalry(ctx):
    out = []
    try:
        rivs = getattr(ctx.league, "rivalries", None) or []
        pairs = []
        for r in rivs:
            try:
                if not isinstance(r, dict):
                    continue
                if r.get("kind") != "team_team":
                    continue
                heat = int(r.get("intensity", 0) or 0)
                if heat < 55:
                    continue
                a = ctx.team_by_name.get(r.get("a_name"))
                b = ctx.team_by_name.get(r.get("b_name"))
                an = _city(a) if a is not None else str(r.get("a_name", "?"))
                bn = _city(b) if b is not None else str(r.get("b_name", "?"))
                pairs.append((heat, an, bn))
            except Exception:
                continue
        pairs.sort(reverse=True)
        for heat, an, bn in pairs[:3]:
            out.append(_spec(
                "rivalry",
                ["{a} and {b} genuinely don't like each other -- and it shows every shift.",
                 "Bad blood is real between {a} and {b}: \"circle those dates,\" one scout says."],
                {"a": an, "b": bn},
                team_keys=["a", "b"]))
    except Exception:
        pass
    return out


def _b_award_races(ctx):
    out = []
    try:
        import awards_race as ar
        players = [p for _t, p in ctx.roster]
        try:
            ross = ar.art_ross_race(players, min_gp=20)[:3]
            if len(ross) >= 2:
                gap = int(ross[0].get("points", 0)) - int(ross[1].get("points", 0))
                if gap <= 6:
                    out.append(_spec(
                        "award_race",
                        ["The scoring race is tightening: {a} leads {b} by just {gap} points.",
                         "Art Ross watch: {a} and {b} are separated by only {gap} -- \"it's going down to the wire.\""],
                        {"a": _pname(ross[0]["player"]), "b": _pname(ross[1]["player"]), "gap": gap},
                        player_keys=["a", "b"], num_keys=["gap"]))
        except Exception:
            pass
        try:
            rocket = ar.rocket_race(players, min_gp=20)[:3]
            if len(rocket) >= 2:
                gap = int(rocket[0].get("goals", 0)) - int(rocket[1].get("goals", 0))
                if gap <= 3:
                    out.append(_spec(
                        "award_race",
                        ["Goal-scoring crown in play: {a} leads {b} by {gap} -- every snipe matters now."],
                        {"a": _pname(rocket[0]["player"]), "b": _pname(rocket[1]["player"]), "gap": gap},
                        player_keys=["a", "b"], num_keys=["gap"]))
        except Exception:
            pass
        try:
            hart = ar.hart_race(players, min_gp=20)[:1]
            if hart:
                p = hart[0]["player"]
                tname = getattr(p, "team_name", "")
                team = ctx.team_by_name.get(tname)
                out.append(_spec(
                    "award_race",
                    ["MVP chatter is building around {a} -- \"he's carrying {team} on his back.\""],
                    {"a": _pname(p), "team": _city(team) if team is not None else str(tname or "his club")},
                    team_keys=["team"], player_keys=["a"]))
        except Exception:
            pass
    except Exception:
        pass
    return out


def _b_prospect(ctx):
    out = []
    try:
        cands = []
        for t in ctx.teams:
            try:
                for p in (getattr(t, "prospects", []) or [])[:40]:
                    try:
                        age = int(getattr(p, "age", 99) or 99)
                        pot = int(getattr(p, "potential", 0) or 0)
                        ovr = _ovr(p)
                        if age <= 22 and (pot >= 80 or ovr >= 74):
                            cands.append((pot, t, p))
                    except Exception:
                        continue
            except Exception:
                continue
        cands.sort(key=lambda c: c[0], reverse=True)
        for pot, t, p in cands[:4]:
            out.append(_spec(
                "prospect",
                ["{player} ({age}) is knocking on the door in {team} -- \"he's forcing our hand,\" one scout says.",
                 "Prospect buzz: {player} keeps producing down below, and {team} is taking notice."],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p),
                 "age": int(getattr(p, "age", 0) or 0)},
                team_keys=["team"], player_keys=["player"],
                pos_of={"player": "pos"}, num_keys=["age"]))
    except Exception:
        pass
    return out


def _b_injury_return(ctx):
    out = []
    try:
        cands = []
        for t, p in ctx.roster:
            try:
                if not getattr(p, "is_injured", False):
                    continue
                g = int(getattr(p, "games_remaining_injured", 0) or 0)
                if 1 <= g <= 7 and _ovr(p) >= 72:
                    cands.append((g, t, p))
            except Exception:
                continue
        cands.sort(key=lambda c: c[0])
        for g, t, p in cands[:3]:
            out.append(_spec(
                "injury_return",
                ["{player} is skating again in {team} -- could be back within the week.",
                 "Good news on the injury front: {player} is close, and {team} needs him."],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p)},
                team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
    except Exception:
        pass
    return out


def _b_injury_hole(ctx):
    out = []
    try:
        cands = []
        for t, p in ctx.roster:
            try:
                if not getattr(p, "is_injured", False):
                    continue
                g = int(getattr(p, "games_remaining_injured", 0) or 0)
                if g >= 15 and _ovr(p) >= 80:
                    cands.append((g, t, p))
            except Exception:
                continue
        cands.sort(key=lambda c: c[0], reverse=True)
        for g, t, p in cands[:3]:
            out.append(_spec(
                "injury_hole",
                ["{team} will be without {player} for a while -- rival GMs smell opportunity.",
                 "The {player} absence leaves a hole in {team}'s lineup that a trade might have to fill."],
                {"team": _city(t), "player": _pname(p), "pos": _pos_str(p)},
                team_keys=["team"], player_keys=["player"], pos_of={"player": "pos"}))
    except Exception:
        pass
    return out


def _b_market_temp(ctx):
    out = []
    try:
        dm = ctx.deadline_manager
        if dm is None:
            return out
        temp = dm.get_market_temperature() or {}
        words = {"forwards": "forward", "defensemen": "blue-line", "goalies": "goaltending"}
        for key, word in words.items():
            t = str(temp.get(key, "") or "").lower()
            if not t:
                continue
            if t in ("hot", "blazing"):
                txt = "The {pos} market is {temp} as the clock ticks down -- sellers are naming their price."
            elif t == "warm":
                txt = "The {pos} market is warming up -- expect movement before the deadline."
            else:
                txt = "The {pos} market is quiet -- GMs are holding their cards."
            out.append(_spec("market_temp", [txt],
                            {"pos": word, "temp": t}))
    except Exception:
        pass
    return out


def _b_recent_trade(ctx):
    out = []
    try:
        dm = ctx.deadline_manager
        if dm is None:
            return out
        summary = dm.get_deadline_summary() or {}
        acts = summary.get("recent_activity") or []
        for a in acts[-4:]:
            try:
                teams = list(a.get("teams_involved", []) or [])
                n = int(a.get("players_count", 0) or 0)
                if len(teams) < 2:
                    continue
                out.append(_spec(
                    "recent_trade",
                    ["League offices are still buzzing after the {a}-{b} deal ({n} players changing hands).",
                     "The {a}-{b} trade reset the market -- \"everyone's re-calibrating,\" one GM says."],
                    {"a": str(teams[0]), "b": str(teams[1]), "n": n},
                    num_keys=["n"]))
            except Exception:
                continue
    except Exception:
        pass
    return out


_BUILDERS = [
    _b_user_block, _b_ai_block, _b_rental_expiring, _b_unhappy_star,
    _b_seller_firesale, _b_contender_need, _b_hot_streak, _b_cold_drought,
    _b_hot_goalie, _b_coach_pressure, _b_rivalry, _b_award_races,
    _b_prospect, _b_injury_return, _b_injury_hole, _b_market_temp,
    _b_recent_trade,
]

# Cosmetic insider attributions -- flavor only, applied after rendering.
_ATTRIBUTIONS = [
    "Sources: ", "Per league chatter: ", "Rival execs say: ",
    "Insiders report: ", "Around the league: ", "",
]


# ---------------------------------------------------------------------------
# Veracity: systematic distortion, rolled inside the engine
# ---------------------------------------------------------------------------
def _distort(spec, bind, ctx, rng):
    """Apply one systematic distortion to the bindings. Returns True if the
    rumor was distorted, False if no distortion applied."""
    options = []
    if spec["team_keys"]:
        options.append("team")
    if spec["player_keys"]:
        options.append("player")
    if spec["num_keys"]:
        options.append("number")
    if not options:
        return False
    kind = rng.choice(options)
    if kind == "team":
        current = {str(bind.get(k, "")) for k in spec["team_keys"]}
        others = [c for c in ctx.cities if c not in current]
        if not others:
            return False
        # Each team key gets its own distinct replacement -- never "X vs X".
        picks = rng.sample(others, min(len(spec["team_keys"]), len(others)))
        for i, k in enumerate(spec["team_keys"]):
            bind[k] = picks[i % len(picks)]
        return True
    if kind == "player":
        for pk in spec["player_keys"]:
            pos_key = spec["pos_of"].get(pk)
            group = _pos_group(bind.get(pos_key, "F"))
            pool = [(n, ps) for (n, ps) in ctx.player_pool.get(group, [])
                    if n != bind.get(pk)]
            if not pool:
                return False
            new_name, new_pos = rng.choice(pool)
            bind[pk] = new_name
            if pos_key:
                bind[pos_key] = new_pos
        return True
    # kind == "number": inflate the figures -- the classic media exaggeration
    for k in spec["num_keys"]:
        try:
            v = int(bind.get(k, 0))
        except Exception:
            continue
        bump = rng.choice([2, 3, 4, 5]) if v < 12 else rng.choice([5, 8, 10])
        bind[k] = v + bump
    return True


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def _collect_specs(ctx):
    specs = []
    for builder in _BUILDERS:
        try:
            specs.extend(builder(ctx) or [])
        except Exception:
            continue
    return specs


def _generate_with_veracity(game_manager=None, league=None, deadline_manager=None,
                            count=DEFAULT_RUMOR_COUNT, seed=None, fresh=False,
                            date_iso=None):
    """Internal: returns [(text, distorted_bool, family)]. Used by the UI
    (via generate_rumors) and by QA spot-checks of the veracity roll."""
    league = _resolve_league(game_manager, league, deadline_manager)
    gm = game_manager
    if gm is None and deadline_manager is not None:
        gm = getattr(deadline_manager, "game_manager", None)
    if league is None:
        return [("The rumor mill is quiet -- no league data to read.", False, "fallback")]

    iso = date_iso or _date_iso(gm)
    rng = random.Random(_seed_for(iso, seed, fresh))
    ctx = _Ctx(game_manager=gm, league=league, deadline_manager=deadline_manager)
    specs = _collect_specs(ctx)
    if not specs:
        return [("The rumor mill is quiet today -- insiders are holding their cards.", False, "fallback")]
    rng.shuffle(specs)

    # Roll veracity per rumor, then enforce the bounded share cap.
    picks = specs  # already shuffled; family cap below keeps the mix varied
    rolled = [rng.random() < DISTORTION_RATE for _ in picks]
    max_bad = max(1, int(len(picks) * MAX_DISTORTION_SHARE))
    bad_idx = [i for i, b in enumerate(rolled) if b]
    if len(bad_idx) > max_bad:
        rng.shuffle(bad_idx)
        for i in bad_idx[max_bad:]:
            rolled[i] = False

    results = []
    seen_texts = set()
    fam_counts = {}
    for spec, is_bad in zip(picks, rolled):
        if len(results) >= count:
            break
        fam = spec.get("family", "?")
        if fam_counts.get(fam, 0) >= MAX_PER_FAMILY:
            continue
        try:
            template = rng.choice(spec["templates"])
            bind = dict(spec["bind"])
            distorted = False
            if is_bad:
                distorted = _distort(spec, bind, ctx, rng)
            text = template.format(**bind)
        except Exception:
            continue
        if text in seen_texts:
            continue
        seen_texts.add(text)
        fam_counts[fam] = fam_counts.get(fam, 0) + 1
        attr = rng.choice(_ATTRIBUTIONS)
        results.append((f"{attr}{text}" if attr else text, distorted, spec["family"]))

    if not results:
        return [("The rumor mill is quiet today -- insiders are holding their cards.", False, "fallback")]
    return results


def generate_rumors(deadline_manager=None, game_manager=None, league=None,
                    count=DEFAULT_RUMOR_COUNT, seed=None, fresh=False):
    """Rumor lines for the UI. Stable per in-game day (cached); pass
    fresh=True to file a new batch of stories."""
    gm = game_manager
    if gm is None and deadline_manager is not None:
        gm = getattr(deadline_manager, "game_manager", None)
    iso = _date_iso(gm)
    key = (iso, int(count), seed, _fresh_nonce[0] if fresh else 0)
    if not fresh and seed is None and key in _cache:
        return list(_cache[key])
    out = [t for (t, _d, _f) in _generate_with_veracity(
        game_manager=gm, league=league, deadline_manager=deadline_manager,
        count=count, seed=seed, fresh=fresh, date_iso=iso)]
    if not fresh and seed is None:
        _cache[key] = list(out)
    return out


def invalidate_cache():
    _cache.clear()


# ---------------------------------------------------------------------------
# Impact players -- real availability for the "Impact Players Available" panel
# ---------------------------------------------------------------------------
def _team_code(team):
    try:
        return str(getattr(team, "city", "") or "")[:3].upper() or "???"
    except Exception:
        return "???"


def get_impact_players(game_manager=None, league=None, deadline_manager=None,
                       count=8):
    """Derive the impact-players list from real availability:
    AI/user trade blocks, expiring contracts on sellers, unhappy stars.
    Returns [{name, pos, team, status, value}]; [] when nothing is available.
    Read-only."""
    league = _resolve_league(game_manager, league, deadline_manager)
    gm = game_manager
    if gm is None and deadline_manager is not None:
        gm = getattr(deadline_manager, "game_manager", None)
    if league is None:
        return []
    try:
        ctx = _Ctx(game_manager=gm, league=league, deadline_manager=deadline_manager)
    except Exception:
        return []

    found = {}  # player id -> dict

    def _add(p, team, status, rank):
        try:
            pid = int(getattr(p, "id", -1) or -1)
        except Exception:
            return
        if pid in found and found[pid].get("_rank", 99) <= rank:
            return
        ovr = _ovr(p)
        value = "High" if ovr >= 86 else ("Medium" if ovr >= 80 else "Low")
        found[pid] = {"name": _pname(p), "pos": _pos_str(p),
                      "team": _team_code(team), "status": status,
                      "value": value, "_ovr": ovr, "_rank": rank}

    try:
        # 1) AI trade blocks (real listings from the trade market)
        import trade_market as tm
        blocks = tm.get_trade_blocks(league) or {}
        for team_name, pids in blocks.items():
            team = ctx.team_by_name.get(team_name)
            for pid in list(pids or [])[:5]:
                try:
                    p, _listed_team = tm.resolve_player(league, pid)
                except Exception:
                    p = None
                if p is not None and _ovr(p) >= 72:
                    _add(p, team, "Available", 1)
    except Exception:
        pass

    try:
        # 2) the user's own trade block
        user_block = list(getattr(gm, "trade_block", []) or []) if gm else []
        user_team = getattr(gm, "user_team", None) if gm else None
        for p in user_block:
            if _ovr(p) >= 72:
                _add(p, user_team, "Available", 1)
    except Exception:
        pass

    try:
        # 3) expiring contracts on bottom-half clubs (rental market)
        n = len(ctx.standings)
        sellers = {getattr(t, "team_name", "") for t, _w, _l, _o, _p, _pc in ctx.standings[n // 2:]} if n else set()
        for t, p in ctx.roster:
            try:
                c = getattr(p, "contract", None)
                yrs = getattr(c, "years_remaining", None)
                if yrs is None or yrs > 1:
                    continue
                if getattr(t, "team_name", "") not in sellers:
                    continue
                if _ovr(p) >= 78:
                    _add(p, t, "Rumored", 2)
            except Exception:
                continue
    except Exception:
        pass

    try:
        # 4) unhappy quality players (not on a block) -- possible asks
        for t, p in ctx.roster:
            try:
                if _ovr(p) < 80:
                    continue
                morale = int(getattr(p, "morale", 70) or 70)
                happy = int(getattr(p, "happiness", 70) or 70)
                if morale >= 45 and happy >= 45:
                    continue
                _add(p, t, "Possible", 3)
            except Exception:
                continue
    except Exception:
        pass

    rows = sorted(found.values(), key=lambda r: (-r["_ovr"], r["name"]))
    for r in rows:
        r.pop("_ovr", None)
        r.pop("_rank", None)
    return rows[:count]
