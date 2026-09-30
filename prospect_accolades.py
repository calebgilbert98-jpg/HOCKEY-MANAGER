# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Junior/college accolades + light reputation for prospects.

The major-league reputation system (reputation_system.py: controversy,
dynamics, social groups, room status, trade/contract modifiers) is
deliberately NOT run for prospects. What prospects get is the light
version:

  * a small public reputation seeded from PERCEIVED potential only
    (never hidden truth -- no leak into the perception-vs-truth engine);
  * real-life-accurate junior/college awards banked as plain dicts in
    ``player.career_accolades`` (the same save-safe format as pro
    accolades): Memorial Cup, league playoff championships, league
    MVP/scoring/defenceman/goalie/rookie awards, Hobey Baker, WJC medals.

Cost model (Chris's constraint: no load-time or responsiveness hit):

  * Draft-class generation: one O(224) pass -- reputation seeds plus a
    small subset of pre-draft junior stories (the season they just
    played). No per-day work, ever.
  * Season rollover: one extra O(prospects) pass inside
    ``League.end_of_season``, reading the farm_season that
    prospect_development already simulated. Pure Python, no UI, no
    per-prospect heavy evaluation.
  * Reputation for prospects is a single int with small ratcheted bumps,
    capped at PROSPECT_REP_CAP. No histories, no controversy.

Awards are keyed off the SIMULATED season performance (observed
production, like real scouting) -- never off true_potential_grade.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

# Prospects stay publicly obscure next to NHLers: hype bumps exist, but
# the ceiling is far below a major-league star's reputation.
PROSPECT_REP_CAP = 40

# ---------------------------------------------------------------------------
# Award catalog: farm-league -> award slate (real-life trophy names; the
# display labels live in accolades.ACCOLADE_LABELS).
# ---------------------------------------------------------------------------

_CHL_AWARDS = {
    "OHL": {
        "cup": "robertson_cup", "mvp": "red_tilson",
        "scoring": "eddie_powers", "defence": "max_kaminsky",
        "goalie": "jim_rutherford", "rookie": "emms_family",
    },
    "WHL": {
        "cup": "ed_chynoweth_cup", "mvp": "four_broncos",
        "scoring": "bob_clarke", "defence": "bill_hunter",
        "goalie": "del_wilson", "rookie": "jim_piggott",
    },
    "QMJHL": {
        "cup": "courteau_trophy", "mvp": "michel_briere",
        "scoring": "jean_beliveau", "defence": "emile_bouchard",
        "goalie": "jacques_plante", "rookie": "rds_cup",
    },
}

# Farm leagues that get the junior treatment (AHL is a pro minor league
# and stays out of this system).
_JUNIOR_FARM_LEAGUES = {
    "OHL", "WHL", "QMJHL", "USHL", "NCAA",
    "SHL", "Liiga", "KHL", "NL",
}

# European pro-league championships a teen prospect can (rarely) lift.
_PRO_CUP = {
    "SHL": "le_mat",
    "Liiga": "kanada_malja",
    "KHL": "gagarin_cup",
    "NL": "nl_champion",
}

# Traditional WJC powers get a selection weight; everyone else can still
# medal (Slovakia 2015, Czechia runs, etc.).
_WJC_POWER = {
    "canada": 3.0, "usa": 2.6, "united states": 2.6,
    "sweden": 2.4, "finland": 2.2, "russia": 2.0,
    "czechia": 1.6, "czech republic": 1.6, "slovakia": 1.4,
    "switzerland": 1.2, "germany": 1.1, "latvia": 1.0,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _is_goalie(player: Any) -> bool:
    try:
        pos = getattr(getattr(player, "primary_position", None), "value", "")
        return str(pos or "").upper() == "G"
    except Exception:
        return False


def _is_defenceman(player: Any) -> bool:
    try:
        pos = str(getattr(getattr(player, "primary_position", None),
                          "value", "") or "").upper()
        return "D" in pos and pos != "G"
    except Exception:
        return False


def _nhle_map() -> Dict[str, float]:
    try:
        import prospect_development as _pd
        return {k: float(v.get("nhle", 0.3))
                for k, v in _pd.LEAGUE_ENVIRONMENTS.items()}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Performance-reflective award scoring
#
# Awards key off the full picture of a prospect's season, not just raw
# rate stats. Production (rate + volume, league-difficulty adjusted)
# leads; every other factor the prospect system tracks nudges it:
#   - sample reliability: skaters need 40% of league games, goalies 12
#     appearances -- 5-game wonders can't win scoring titles
#   - league difficulty: nhle normalization, so a Liiga point counts more
#     than a DNL point
#   - age curve: teenage dominance impresses more than an overager
#     feasting on kids
#   - form: the season's breakout/bust/noticed/cooled evaluation
#     (persisted as farm_result by process_prospect_offseason)
#   - track record: prior farm_history seasons -- voters remember names
#   - two-way play: defensive attributes feed MVP and best-defenceman
#     races, so shutdown defencemen aren't invisible
#   - goalie wins + temperament alongside sv%/gaa
#   - narrative whisper: draft hype and consistency tint close races the
#     way media attention does in real voting -- never decisive alone
# ---------------------------------------------------------------------------

_SKATER_GP_FRAC = 0.40
_GOALIE_GP_MIN = 12
_DISQUALIFIED = -99.0


def _league_games(league: str) -> int:
    try:
        import prospect_development as _pd
        return int((_pd.LEAGUE_ENVIRONMENTS.get(league, {})
                    .get("games", 60)) or 60)
    except Exception:
        return 60


def _farm(p: Any) -> Dict[str, Any]:
    return getattr(p, "farm_season", None) or {}


def _age_mult(p: Any) -> float:
    age = getattr(p, "age", 20) or 20
    m = 1.0 + min(0.10, max(0, 20 - age) * 0.025)
    if age >= 21:
        m *= 0.95
    return m


def _form_mult(p: Any) -> float:
    r = getattr(p, "farm_result", None)
    if r == "breakout":
        return 1.12
    if r == "noticed":
        return 1.05
    if r == "bust":
        return 0.90
    if r == "cooled":
        return 0.93
    return 1.0


def _trend_mult(p: Any, nhle: Dict[str, float]) -> float:
    hist = getattr(p, "farm_history", None) or []
    vals = []
    for s in hist[-2:]:
        s = s or {}
        if int(s.get("gp", 0) or 0) < 15:
            continue
        n = float(nhle.get(s.get("league", ""), 0.3) or 0.3)
        vals.append(float(s.get("ppg", 0) or 0) * (n / 0.30))
    if not vals:
        return 1.0
    return 1.0 + min(0.06, (sum(vals) / len(vals)) * 0.08)


def _hype_mult(p: Any) -> float:
    m = 1.0 + min(0.06, (float(getattr(p, "draft_hype", 0) or 0)
                         / 100.0) * 0.06)
    if getattr(p, "generational", False):
        m += 0.03
    return m


def _cons_mult(p: Any) -> float:
    c = float(getattr(p, "consistency", 50) or 50)
    return 1.0 + ((c - 50.0) / 100.0) * 0.04


def _shared_mults(p: Any, nhle: Dict[str, float]) -> float:
    return (_age_mult(p) * _form_mult(p) * _trend_mult(p, nhle)
            * _hype_mult(p) * _cons_mult(p))


def _two_way(p: Any) -> float:
    """Defensive contribution read from SIMULATED performance
    (plus/minus), not raw attributes -- awards follow what the player
    did, the way real voting does. Missing data (old saves) is neutral."""
    s = _farm(p)
    if s.get("plus_minus", None) is None:
        return 0.10
    gp = int(s.get("gp", 0) or 0)
    if gp <= 0:
        return 0.10
    rate = float(s["plus_minus"]) / gp  # ~[-0.5, +0.5]
    return max(-0.25, min(0.35, rate * 1.1))


def _skater_impact(player: Any, nhle: Dict[str, float]) -> float:
    """Composite value score: league-normalized production (rate with a
    durability weight), two-way play, age curve, form, track record,
    and a whisper of narrative. Unqualified samples score -99."""
    try:
        s = _farm(player)
        gp = int(s.get("gp", 0) or 0)
        league = s.get("league", "")
        if gp < _SKATER_GP_FRAC * _league_games(league):
            return _DISQUALIFIED
        ppg = float(s.get("ppg", 0) or 0)
        rate = ppg * (float(nhle.get(league, 0.3) or 0.3) / 0.30)
        games = _league_games(league)
        durability = 0.55 + 0.45 * min(1.0, gp / games) if games else 0.55
        return ((rate * durability + _two_way(player))
                * _shared_mults(player, nhle))
    except Exception:
        return _DISQUALIFIED


def _scoring_pts(player: Any) -> float:
    """Total points for scoring titles -- durability over rate."""
    try:
        return float(_farm(player).get("pts", 0) or 0)
    except Exception:
        return 0.0


def _qualified_skaters(pool: List[Any]) -> List[Any]:
    """Skaters meeting the GP gate (mirrors _skater_impact's -99)."""
    out = []
    for p in pool:
        try:
            s = _farm(p)
            if int(s.get("gp", 0) or 0) >= _SKATER_GP_FRAC * _league_games(
                    s.get("league", "")):
                out.append(p)
        except Exception:
            continue
    return out


def _defence_impact(player: Any, nhle: Dict[str, float]) -> float:
    """Best-defenceman: scoring blended with SIMULATED defensive
    performance (plus/minus per game). The shutdown defender who
    actually shut people down beats the power-play specialist who
    bled chances against."""
    try:
        s = _farm(player)
        gp = int(s.get("gp", 0) or 0)
        league = s.get("league", "")
        if gp < _SKATER_GP_FRAC * _league_games(league):
            return _DISQUALIFIED
        ppg = float(s.get("ppg", 0) or 0)
        rate = ppg * (float(nhle.get(league, 0.3) or 0.3) / 0.30)
        pm_rate = float(s.get("plus_minus", 0) or 0) / max(gp, 1)
        pm_rate = max(-0.5, min(0.5, pm_rate))
        return ((rate * 0.45 + pm_rate * 2.2 + 0.55)
                * _shared_mults(player, nhle))
    except Exception:
        return _DISQUALIFIED


def _goalie_impact(player: Any) -> float:
    """Goalies: sv% leads; gaa, win%, age curve, form, and temperament
    all count. Unqualified samples score -99."""
    try:
        s = _farm(player)
        gp = int(s.get("gp", 0) or 0)
        sv = float(s.get("sv_pct", 0) or 0)
        if sv <= 0 or gp < _GOALIE_GP_MIN:
            return _DISQUALIFIED
        gaa = float(s.get("gaa", 9) or 9)
        w = int(s.get("w", 0) or 0)
        base = (sv - 0.890) * 120.0
        base -= max(0.0, gaa - 2.6) * 1.2
        base += (w / gp - 0.5) * 8.0
        t = float(getattr(player, "goalie_temperament", 50) or 50)
        mult = _shared_mults(player, _nhle_map()) * (
            1.0 + ((t - 50.0) / 100.0) * 0.05)
        return base * mult
    except Exception:
        return _DISQUALIFIED


def _impact(player: Any, nhle: Dict[str, float]) -> float:
    return _goalie_impact(player) if _is_goalie(player) \
        else _skater_impact(player, nhle) * 10.0


def _bank(player: Any, award_key: str, year_label: str) -> bool:
    try:
        import accolades as _acc
        return bool(_acc.bank_accolade(player, award_key, year_label))
    except Exception:
        return False


def _bump_rep(player: Any, pts: int) -> None:
    """Small ratcheted hype bump for a junior honor. Never a decrease,
    never above the prospect cap -- the light version of the rep system."""
    try:
        import reputation_system as _rs
        _rs.ensure_reputation_fields(player)
        cur = int(getattr(player, "reputation", 0) or 0)
        player.reputation = max(0, min(PROSPECT_REP_CAP, cur + int(pts)))
    except Exception:
        pass


def _name(player: Any) -> str:
    return str(getattr(player, "full_name", "Prospect") or "Prospect")


# ---------------------------------------------------------------------------
# Light reputation seeding (perceived potential only -- never truth)
# ---------------------------------------------------------------------------

_PERCEIVED_REP = {
    "A+": 24, "A": 21, "A-": 18,
    "B+": 15, "B": 12, "B-": 9,
    "C+": 7, "C": 5, "C-": 4,
}


def seed_prospect_reputation(player: Any) -> int:
    """Seed a small public reputation from PERCEIVED potential grade.

    The generational flag and potential_grade are the belief side of the
    perception-vs-truth engine, so this can never leak hidden truth.
    Most prospects land near-unknown; hyped names arrive with buzz.
    """
    try:
        import reputation_system as _rs
        _rs.ensure_reputation_fields(player)
        if bool(getattr(player, "generational", False)):
            rep = 30
        else:
            grade = str(getattr(player, "potential_grade", "") or "").strip()
            rep = _PERCEIVED_REP.get(grade, 2)
        player.reputation = max(0, min(30, int(rep)))
        return int(player.reputation)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Draft-class generation: pre-draft junior stories
# ---------------------------------------------------------------------------

def _story_family(junior_league: str) -> Optional[str]:
    u = str(junior_league or "").upper()
    if u in ("OHL", "WHL", "QMJHL"):
        return u
    if "NCAA" in u:
        return "NCAA"
    if "USHL" in u or "NTDP" in u:
        return "USHL"
    if "MHL" in u:
        return "MHL"
    if "J20" in u:
        return "J20"
    if "U20" in u and "SM" in u:
        return "U20SM"
    if "SHL" in u or "ALLSVENSKAN" in u:
        return "SHL"
    if "LIIGA" in u:
        return "LIIGA"
    if "KHL" in u:
        return "KHL"
    return None


def _story_pool(family: str, is_goalie: bool, is_d: bool) -> List[Tuple[str, float]]:
    """(award_key, weight) choices for one pre-draft junior story."""
    if family in _CHL_AWARDS:
        a = _CHL_AWARDS[family]
        pool = [(a["cup"], 30.0), (a["mvp"], 12.0), (a["scoring"], 10.0),
                (a["rookie"], 12.0), ("memorial_cup", 6.0),
                ("wjc_gold", 5.0), ("wjc_silver", 6.0), ("wjc_bronze", 8.0)]
        pool.append((a["goalie"] if is_goalie else a["defence"], 15.0) if
                    (is_goalie or is_d) else (a["mvp"], 6.0))
        return pool
    if family == "NCAA":
        pool = [("ncaa_championship", 30.0), ("hobey_baker", 8.0),
                ("tim_taylor", 15.0), ("wjc_gold", 5.0),
                ("wjc_silver", 6.0), ("wjc_bronze", 8.0)]
        if is_goalie:
            pool.append(("mike_richter", 15.0))
        return pool
    if family == "USHL":
        return [("clark_cup", 35.0), ("ushl_player_of_year", 12.0),
                ("wjc_gold", 5.0), ("wjc_silver", 6.0), ("wjc_bronze", 8.0)]
    if family == "MHL":
        return [("kharlamov_cup", 35.0), ("wjc_gold", 6.0),
                ("wjc_silver", 7.0), ("wjc_bronze", 9.0)]
    if family == "J20":
        return [("j20_champion", 35.0), ("wjc_gold", 6.0),
                ("wjc_silver", 7.0), ("wjc_bronze", 9.0)]
    if family == "U20SM":
        return [("u20_sm_champion", 35.0), ("wjc_gold", 6.0),
                ("wjc_silver", 7.0), ("wjc_bronze", 9.0)]
    if family in ("SHL", "LIIGA", "KHL"):
        cup = {"SHL": "le_mat", "LIIGA": "kanada_malja",
               "KHL": "gagarin_cup"}[family]
        return [(cup, 25.0), ("wjc_gold", 5.0),
                ("wjc_silver", 6.0), ("wjc_bronze", 8.0)]
    return []


_CUP_KEYS = {
    "robertson_cup", "courteau_trophy", "ed_chynoweth_cup", "memorial_cup",
    "clark_cup", "ncaa_championship", "kharlamov_cup", "j20_champion",
    "u20_sm_champion", "le_mat", "kanada_malja", "gagarin_cup",
}


def _temp_draft_year_score(p: Any, sim_league: str,
                           nhle: Dict[str, float], rng: Any) -> float:
    """Simulate the prospect's draft-year season into a scratch slot,
    score it with the award composite, then restore the player
    untouched. Zero persistent side effects."""
    try:
        import prospect_development as _pd
        snap_league = getattr(p, "farm_league", "")
        snap_season = getattr(p, "farm_season", None)
        snap_hist = list(getattr(p, "farm_history", None) or [])
        try:
            _pd.simulate_prospect_season(p, league=sim_league, rng=rng)
            return _impact(p, nhle)
        finally:
            p.farm_league = snap_league
            if snap_season is None:
                try:
                    del p.farm_season
                except Exception:
                    p.farm_season = {}
            else:
                p.farm_season = snap_season
            p.farm_history = snap_hist
    except Exception:
        return _DISQUALIFIED


def seed_draft_class(prospects: List[Any], draft_year: int,
                     rng: Any = None) -> Dict[str, int]:
    """Reputation seeds + pre-draft junior stories for a draft class.

    Runs once at class generation (O(n), trivial). Instead of handing
    stories to prospects by perceived hype, each prospect's draft-year
    season is simulated into a scratch slot (restored afterwards -- no
    side effects) and stories go to the top performers in each junior
    family. The best players arrive with the honors, which is what the
    draft stories and media consensus are describing.
    """
    rng = rng or random
    stats = {"seeded": 0, "storied": 0}
    try:
        dy = int(draft_year)
    except Exception:
        return stats
    cup_year = f"{dy - 1}-{str(dy)[2:]}"   # 2025-26
    award_year = str(dy)                    # 2026
    nhle = _nhle_map()
    by_family: Dict[str, List[Any]] = {}
    for p in prospects or []:
        try:
            seed_prospect_reputation(p)
            stats["seeded"] += 1
            fam = _story_family(getattr(p, "junior_league", ""))
            if fam:
                by_family.setdefault(fam, []).append(p)
        except Exception:
            continue
    for fam, pool in by_family.items():
        try:
            sim_league = fam if fam in ("OHL", "WHL", "QMJHL",
                                        "NCAA") else "USHL"
            scored = []
            for p in pool:
                s = _temp_draft_year_score(p, sim_league, nhle, rng)
                if s > _DISQUALIFIED:
                    scored.append((s, p))
            if not scored:
                continue
            scored.sort(key=lambda t: t[0], reverse=True)
            n_stories = min(4, max(1, len(scored) // 10))
            storied = set()
            for i in range(n_stories):
                cands = [p for _, p in scored[:8] if id(p) not in storied]
                if not cands:
                    break
                weights = list(range(len(cands), 0, -1))
                p = rng.choices(cands, weights=weights, k=1)[0]
                storied.add(id(p))
                choices = [c for c in _story_pool(
                    fam, _is_goalie(p), _is_defenceman(p))
                    if not (c[0].startswith("wjc_")
                            and int(getattr(p, "age", 18) or 18) > 19)]
                if not choices:
                    continue
                keys = [c[0] for c in choices]
                weights = [c[1] for c in choices]
                first = rng.choices(keys, weights=weights, k=1)[0]
                _bank(p, first,
                      cup_year if first in _CUP_KEYS else award_year)
                stats["storied"] += 1
                if rng.random() < 0.12:
                    rest = [k for k in keys if k != first]
                    if rest:
                        second = rng.choice(rest)
                        _bank(p, second,
                              cup_year if second in _CUP_KEYS else award_year)
        except Exception:
            continue
    return stats


# ---------------------------------------------------------------------------
# Season rollover: junior awards from the simulated farm seasons
# ---------------------------------------------------------------------------

def _collect(league: Any) -> List[Any]:
    """Prospects with a fresh junior farm_season (the dev sim already ran)."""
    nhl_ids = set()
    try:
        for t in getattr(league, "teams", []) or []:
            for p in getattr(t, "roster", []) or []:
                nhl_ids.add(getattr(p, "id", None))
    except Exception:
        pass
    out = []
    try:
        players = league.get_all_players()
    except Exception:
        return out
    for p in players or []:
        try:
            if getattr(p, "id", None) in nhl_ids:
                continue
            if int(getattr(p, "age", 99) or 99) > 23:
                continue
            # Mirror the dev-sim gate: this uses prior_nhl_gp because
            # end_of_season wipes player.stats before the awards pass
            # runs. Only prospects who actually skated a junior/college
            # season (not NHL call-ups) are award-eligible.
            try:
                _prior = getattr(p, "prior_nhl_gp", None) or []
                _nhl_gp = int(_prior[-1]) if _prior else 0
            except Exception:
                _nhl_gp = 0
            if _nhl_gp >= 15:
                continue
            season = getattr(p, "farm_season", None) or {}
            if season.get("league") not in _JUNIOR_FARM_LEAGUES:
                continue
            out.append(p)
        except Exception:
            continue
    return out


def _best(pool: List[Any], key, n: int = 1) -> List[Any]:
    try:
        ranked = sorted(pool, key=key, reverse=True)
        return [p for p in ranked[:max(1, n)] if key(p) > -50]
    except Exception:
        return []


def _pick_champions(pool: List[Any], nhle: Dict[str, float],
                    rng: Any, k: int = 3) -> List[Any]:
    """League playoff champions: weighted draw from the top 8 by impact.

    The best player isn't always on the best team -- the weight favors
    stars without guaranteeing them, like real junior playoffs.
    """
    try:
        cands = sorted(pool, key=lambda p: _impact(p, nhle),
                       reverse=True)[:8]
        if not cands:
            return []
        weights = list(range(len(cands), 0, -1))
        k = max(1, min(k, len(cands)))
        # random.choices can repeat; de-dupe while keeping weight order.
        picked: List[Any] = []
        for _ in range(k * 3):
            if len(picked) >= k:
                break
            c = rng.choices(cands, weights=weights, k=1)[0]
            if c not in picked:
                picked.append(c)
        return picked
    except Exception:
        return []


def roll_prospect_awards(league: Any, season_label: str,
                         ceremony_year: str, rng: Any = None) -> List[str]:
    """Roll one season of junior/college awards. Called once per
    ``League.end_of_season`` after the prospect offseason sim.

    Returns short news lines (major honors only) for the UI layer.
    """
    rng = rng or random
    news: List[str] = []
    try:
        import accolades as _acc
    except Exception:
        return news
    labels = getattr(_acc, "ACCOLADE_LABELS", {})

    def _lbl(key: str) -> str:
        return str(labels.get(key, key))

    prospects = _collect(league)
    if not prospects:
        return news
    nhle = _nhle_map()
    by_league: Dict[str, List[Any]] = {}
    for p in prospects:
        lg = (getattr(p, "farm_season", None) or {}).get("league", "")
        by_league.setdefault(lg, []).append(p)

    skaters = [p for p in prospects if not _is_goalie(p)]
    goalies = [p for p in prospects if _is_goalie(p)]

    def _sk(p: Any) -> float:
        return _skater_impact(p, nhle)

    def _gl(p: Any) -> float:
        return _goalie_impact(p)

    def _df(p: Any) -> float:
        return _defence_impact(p, nhle)

    # ---- CHL leagues: full slate ----
    chl_champs: Dict[str, List[Any]] = {}
    league_mvps: List[Any] = []
    for lg in ("OHL", "WHL", "QMJHL"):
        pool = by_league.get(lg, [])
        if len(pool) < 3:
            continue
        a = _CHL_AWARDS[lg]
        champs = _pick_champions(pool, nhle, rng,
                                 k=min(3, len(pool)))
        for c in champs:
            if _bank(c, a["cup"], season_label):
                _bump_rep(c, 2)
        chl_champs[lg] = champs
        if champs:
            names = ", ".join(_name(c) for c in champs[:3])
            news.append(f"{names} lift the {_lbl(a['cup'])} ({lg}).")

        lg_skaters = [p for p in pool if not _is_goalie(p)]
        mvp = _best(lg_skaters, _sk, 1)
        if mvp and _bank(mvp[0], a["mvp"], ceremony_year):
            _bump_rep(mvp[0], 3)
            league_mvps.append(mvp[0])
            news.append(f"{_name(mvp[0])} wins the {_lbl(a['mvp'])} ({lg}).")
        s = _best(_qualified_skaters(lg_skaters), _scoring_pts, 1)
        if s and (not mvp or s[0] is not mvp[0]) and \
                _bank(s[0], a["scoring"], ceremony_year):
            _bump_rep(s[0], 2)
        dmen = [p for p in lg_skaters if _is_defenceman(p)]
        d = _best(dmen, _df, 1)
        if d and _bank(d[0], a["defence"], ceremony_year):
            _bump_rep(d[0], 2)
        g = _best([p for p in pool if _is_goalie(p)], _gl, 1)
        if g and _bank(g[0], a["goalie"], ceremony_year):
            _bump_rep(g[0], 2)
        rook = _best([p for p in pool
                      if int(getattr(p, "age", 99) or 99) <= 18], _sk, 1)
        if rook and _bank(rook[0], a["rookie"], ceremony_year):
            _bump_rep(rook[0], 2)

    # ---- Memorial Cup: one CHL champion takes the tournament ----
    if chl_champs:
        lgs = list(chl_champs.keys())
        weights = [0.4, 0.35, 0.25][:len(lgs)]
        winner_lg = rng.choices(lgs, weights=weights, k=1)[0]
        winners = chl_champs[winner_lg]
        for w in winners:
            if _bank(w, "memorial_cup", season_label):
                _bump_rep(w, 4)
        if winners:
            names = ", ".join(_name(w) for w in winners[:3])
            news.append(f"Memorial Cup champions: {names} ({winner_lg}).")
            smythe = _best([p for p in winners if not _is_goalie(p)],
                           _sk, 1)
            if smythe and _bank(smythe[0], "stafford_smythe",
                                ceremony_year):
                _bump_rep(smythe[0], 3)
                news.append(f"{_name(smythe[0])} named Memorial Cup MVP "
                            f"({_lbl('stafford_smythe')}).")
            lead = _best(_qualified_skaters(
                [p for p in winners if not _is_goalie(p)]),
                _scoring_pts, 1)
            if lead and (not smythe or lead[0] is not smythe[0]) and \
                    _bank(lead[0], "ed_chynoweth_trophy", ceremony_year):
                _bump_rep(lead[0], 2)

    # ---- CHL-wide honors ----
    if len(league_mvps) >= 2:
        poy = _best(league_mvps, _sk, 1)
        if poy and _bank(poy[0], "chl_player_of_year", ceremony_year):
            _bump_rep(poy[0], 3)
            news.append(f"{_name(poy[0])} named {_lbl('chl_player_of_year')}.")
    chl_skaters = [p for p in skaters
                   if (getattr(p, "farm_season", None) or {}).get("league")
                   in _CHL_AWARDS]
    if len(chl_skaters) >= 6:
        ts = _best(_qualified_skaters(chl_skaters), _scoring_pts, 1)
        if ts and _bank(ts[0], "chl_top_scorer", ceremony_year):
            _bump_rep(ts[0], 2)
        cg = _best([p for p in prospects
                    if _is_goalie(p) and
                    (getattr(p, "farm_season", None) or {}).get("league")
                    in _CHL_AWARDS], _gl, 1)
        if cg and _bank(cg[0], "chl_goaltender_of_year", ceremony_year):
            _bump_rep(cg[0], 2)
        cr = _best([p for p in chl_skaters
                    if int(getattr(p, "age", 99) or 99) <= 18], _sk, 1)
        if cr and _bank(cr[0], "chl_rookie_of_year", ceremony_year):
            _bump_rep(cr[0], 2)

    # ---- USHL ----
    ushl = by_league.get("USHL", [])
    if len(ushl) >= 3:
        champs = _pick_champions(ushl, nhle, rng, k=min(2, len(ushl)))
        for c in champs:
            if _bank(c, "clark_cup", season_label):
                _bump_rep(c, 2)
        poy = _best([p for p in ushl if not _is_goalie(p)], _sk, 1)
        if poy and _bank(poy[0], "ushl_player_of_year", ceremony_year):
            _bump_rep(poy[0], 3)
            news.append(f"{_name(poy[0])} named {_lbl('ushl_player_of_year')}.")

    # ---- NCAA ----
    ncaa = by_league.get("NCAA", [])
    if len(ncaa) >= 3:
        champs = _pick_champions(ncaa, nhle, rng, k=min(3, len(ncaa)))
        for c in champs:
            if _bank(c, "ncaa_championship", season_label):
                _bump_rep(c, 2)
        if champs:
            names = ", ".join(_name(c) for c in champs[:3])
            news.append(f"NCAA champions: {names}.")
        hobey = _best([p for p in ncaa if not _is_goalie(p)], _sk, 1)
        if hobey and _bank(hobey[0], "hobey_baker", ceremony_year):
            _bump_rep(hobey[0], 3)
            news.append(f"{_name(hobey[0])} wins the {_lbl('hobey_baker')}.")
        richter = _best([p for p in ncaa if _is_goalie(p)], _gl, 1)
        if richter and _bank(richter[0], "mike_richter", ceremony_year):
            _bump_rep(richter[0], 2)
        frosh = _best([p for p in ncaa
                       if int(getattr(p, "age", 99) or 99) <= 19],
                      _sk, 1)
        if frosh and _bank(frosh[0], "tim_taylor", ceremony_year):
            _bump_rep(frosh[0], 2)

    # ---- European junior / teen-pro leagues: championship only ----
    euro_cups = [("SHL", "le_mat"), ("Liiga", "kanada_malja"),
                 ("KHL", "gagarin_cup"), ("NL", "nl_champion")]
    for lg, cup in euro_cups:
        pool = by_league.get(lg, [])
        if len(pool) >= 2:
            champs = _pick_champions(pool, nhle, rng, k=min(2, len(pool)))
            for c in champs:
                if _bank(c, cup, season_label):
                    _bump_rep(c, 2)

    # ---- World Juniors: one lightweight tournament ----
    juniors = [p for p in prospects
               if int(getattr(p, "age", 99) or 99) <= 19]
    if len(juniors) >= 9:
        def _w(p: Any) -> float:
            nat = str(getattr(p, "nationality", "") or "").lower()
            base = _WJC_POWER.get(nat, 0.9)
            return max(0.01, _impact(p, nhle) * base
                       * rng.uniform(0.7, 1.3))

        ordered = sorted(juniors, key=_w, reverse=True)[:9]
        medals = ([("wjc_gold", 3)] * 3 + [("wjc_silver", 2)] * 3
                  + [("wjc_bronze", 1)] * 3)
        golds: List[Any] = []
        for p, (medal, pts) in zip(ordered, medals):
            if _bank(p, medal, ceremony_year):
                _bump_rep(p, pts)
                if medal == "wjc_gold":
                    golds.append(p)
        if golds:
            names = ", ".join(_name(g) for g in golds)
            news.append(f"World Junior gold: {names}.")
            mvp = _best(golds, _sk, 1)
            if mvp and _bank(mvp[0], "wjc_mvp", ceremony_year):
                _bump_rep(mvp[0], 2)
                news.append(f"{_name(mvp[0])} named {_lbl('wjc_mvp')}.")

    return news
