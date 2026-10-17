"""News screen: Media Center -- news wire, journalists, narratives, fines, fan buzz.

Wired to real engine systems:
- News wire: app.news_log (fed by daily_news.py story generators via
  app.add_news(), plus trades/injuries/signings from the sim core).
  Categories are derived from the generator prefixes (e.g. "HOT SEAT:"),
  falling back to a generic PREFIX: pattern, then keyword scan.
- Journalists: media_engine (Reporter, ensure_media_state, reporters_for,
  market_of) -- 3 real reporters per NHL market (stirrer/loyalist/neutral).
- Narratives: league.media_narratives (Narrative objects) and
  league.coach_media_beefs (CoachMediaBeef) from media_engine.
- Fines: league.media_fines, the same ledger media_center_window.py reads.
- Fan buzz: fan_sentiment (get_fan_sentiment, sentiment_label) +
  fan_narratives (sentiment_tier, media_tone_for_sentiment), including the
  per-team sentiment trail (buzz drivers).

All endpoints return 200 with empty-state payloads when no game is
attached. Nothing here fabricates data; empty states render in the UI.
"""
import re
from datetime import date, datetime
from urllib.parse import quote

from flask import Blueprint, jsonify, render_template

from web_ui.bridge import _safe, _resolve_gm

bp = Blueprint("news", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


def _league(live):
    """gm-first league lookup."""
    gm = _resolve_gm(live)
    league = _safe(lambda: getattr(gm, "league", None))
    if league is None:
        league = _safe(lambda: getattr(live, "league", None))
    return league


def _teams(league):
    if league is None:
        return []
    return _safe(lambda: list(getattr(league, "teams", None) or []), []) or []


def _team_name(t):
    return _safe(lambda: str(getattr(t, "team_name", "") or ""), "") or ""


def _fnum(v, default=0.0):
    """Float coercion that never raises and never mistakes 0.0 for missing."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Existing /api/news payload (kept working unchanged)
# ---------------------------------------------------------------------------

def _news_payload(app):
    """app.news_log -> newest-first JSON-safe list. Never raises."""
    raw = _safe(lambda: list(getattr(app, "news_log", None) or []), []) or []
    items = []
    for entry in raw:
        try:
            if isinstance(entry, dict):
                d = entry.get("date")
                story = entry.get("story", "")
            else:
                # defensive: non-dict entries get a blank date, stringified story
                d, story = None, entry
            if story is None:
                story_text = ""
            else:
                story_text = _safe(lambda: str(story), "") or ""
            if isinstance(d, (date, datetime)):
                date_iso = d.isoformat()
                date_label = d.strftime("%b %d, %Y")
            else:
                date_iso = ""
                date_label = _safe(lambda: str(d), "") or ""
            items.append({
                "date": date_iso,          # sort key (may be "" when unknown)
                "date_label": date_label,  # display label
                "story": story_text,
            })
        except Exception:
            continue
    # newest first; entries without a parseable date sink to the bottom
    try:
        items.sort(key=lambda x: x["date"], reverse=True)
    except Exception:
        items.reverse()
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# News wire enrichment: categories + clickable team links
# ---------------------------------------------------------------------------

# Known story prefixes from daily_news.py generators -> category.
_PREFIX_CATS = {
    "RISING STAR": "Prospects",
    "PROSPECT WATCH": "Prospects",
    "FUTURE WATCH": "Prospects",
    "DEVELOPMENT CAMP": "Prospects",
    "HOT SEAT": "Coaches",
    "COACHING MASTERCLASS": "Coaches",
    "SCRATCH WATCH": "Rumors",
    "RUMOR MILL": "Rumors",
    "CONTRACT WATCH": "Rumors",
    "DRAFT RISERS": "Draft",
    "MOCK DRAFT BUZZ": "Draft",
    "DRAFT DEPTH": "Draft",
    "MILESTONE WATCH": "Milestones",
    "GOALIE DEBATE": "Players",
    "UNDERDOG": "Players",
    "SCORCHING": "Players",
    "SLUMP WATCH": "Teams",
    "SCORING RACE": "League",
    "POWER RANKINGS": "League",
}

_GENERIC_PREFIX_RE = re.compile(r"^([A-Z][A-Z0-9 /&.'-]{2,28}):\s")


def _categorize(story):
    """Category for a story string. Known prefixes first, then a generic
    PREFIX: pattern, then a keyword scan. Never raises."""
    try:
        s = story or ""
        for prefix, cat in _PREFIX_CATS.items():
            if s.startswith(prefix + ":") or s.startswith(prefix + " "):
                return cat
        m = _GENERIC_PREFIX_RE.match(s)
        if m:
            return m.group(1).strip().title()
        low = s.lower()
        if "trade" in low or "rumor" in low:
            return "Rumors"
        if "injur" in low:
            return "Injuries"
        if "suspend" in low or "fine" in low:
            return "Discipline"
        if "sign" in low or "extension" in low or "buyout" in low:
            return "Signings"
        if "coach" in low or "fired" in low or "hired" in low:
            return "Coaches"
        if "draft" in low:
            return "Draft"
        if "career" in low or "milestone" in low:
            return "Milestones"
        return "League"
    except Exception:
        return "League"


def _story_teams(story, team_names):
    """Team names mentioned in the story (longest match first, max 2)."""
    try:
        low = (story or "").lower()
        found = []
        for name in team_names:
            if name and name.lower() in low:
                found.append(name)
                if len(found) >= 2:
                    break
        return found
    except Exception:
        return []


def _wire_payload(live):
    base = _news_payload(live)
    names = [_team_name(t) for t in _teams(_league(live))]
    names = sorted([n for n in names if n], key=len, reverse=True)
    items = []
    for it in base["items"]:
        story = it["story"]
        teams = _story_teams(story, names)
        items.append({
            "date": it["date"],
            "date_label": it["date_label"],
            "story": story,
            "category": _categorize(story),
            "teams": [{"name": n, "url": "/team/" + quote(n)} for n in teams],
        })
    categories = sorted({i["category"] for i in items})
    return {"items": items, "count": len(items), "categories": categories}


# ---------------------------------------------------------------------------
# Journalists: media_engine reporters
# ---------------------------------------------------------------------------

_ARCHETYPE_BLURB = {
    "stirrer": "Pokes the bear. Asks the questions nobody wants asked.",
    "loyalist": "Homer press. Defends the team through thick and thin.",
    "neutral": "Straight down the middle. Just the facts.",
}


def _journalists_payload(live):
    empty = {"markets": [], "count": 0}
    league = _league(live)
    if league is None:
        return empty
    try:
        import media_engine as me
    except Exception:
        return empty
    try:
        me.ensure_media_state(league)
        markets = []
        for market in me.MARKET_PROFILES:
            prof = me.market_of(market)
            reps = me.reporters_for(market, league) or []
            reporters = []
            for r in reps:
                arch = _safe(lambda: str(getattr(r, "archetype", "") or ""), "") or "neutral"
                reporters.append({
                    "name": _safe(lambda: str(getattr(r, "name", "") or ""), "") or "Unknown",
                    "archetype": arch,
                    "archetype_blurb": _ARCHETYPE_BLURB.get(arch, ""),
                    "credibility": round(_fnum(getattr(r, "credibility", 50), 50.0), 1),
                    "fan_approval": round(_fnum(getattr(r, "fan_approval", 50), 50.0), 1),
                })
            markets.append({
                "market": market,
                "url": "/team/" + quote(market),
                "intensity": int(prof.get("intensity", 0)),
                "adversarial": int(prof.get("adversarial", 0)),
                "loyalty": int(prof.get("loyalty", 0)),
                "patience": int(prof.get("patience", 0)),
                "reporters": reporters,
            })
        # Fishbowls first: the loudest markets lead the directory.
        markets.sort(key=lambda m: -m["intensity"])
        return {"markets": markets,
                "count": sum(len(m["reporters"]) for m in markets)}
    except Exception:
        return empty


# ---------------------------------------------------------------------------
# Narratives & beefs: league.media_narratives / league.coach_media_beefs
# ---------------------------------------------------------------------------

_NARR_KINDS = {
    "hot_seat": "Hot Seat",
    "leadership": "Leadership Questions",
    "goalie": "Goalie Controversy",
    "trade_rumor": "Trade Rumor",
    "prospect_watch": "Prospect Watch",
    "trust_process": "Trust the Process",
    "cup_window": "Cup Window",
    "legacy_chase": "Legacy Chase",
    "deadline_race": "Deadline Race",
    "fan_unrest": "Fan Unrest",
    "fan_buzz": "Fan Buzz",
}

_BEEF_LEVELS = {1: "Testy exchange", 2: "Open hostility", 3: "Full circus"}


def _player_index(league):
    """player id -> display name across rosters + prospects. Never raises."""
    idx = {}
    try:
        for t in _teams(league):
            for coll in ("roster", "prospects"):
                for p in _safe(lambda: list(getattr(t, coll, None) or []), []) or []:
                    try:
                        pid = getattr(p, "id", None)
                        if pid is None or pid in idx:
                            continue
                        name = (_safe(lambda: str(getattr(p, "full_name", "") or ""), "")
                                or (f"{_safe(lambda: str(getattr(p, 'first_name', '') or ''), '')} "
                                    f"{_safe(lambda: str(getattr(p, 'last_name', '') or ''), '')}".strip())
                                or "Unknown Player")
                        idx[pid] = name
                    except Exception:
                        continue
    except Exception:
        pass
    return idx


def _narratives_payload(live):
    empty = {"narratives": [], "beefs": [], "count": 0}
    league = _league(live)
    if league is None:
        return empty
    try:
        import media_engine as me
        me.ensure_media_state(league)
    except Exception:
        return empty
    try:
        names = _player_index(league)
        raw_narrs = _safe(lambda: list(getattr(league, "media_narratives", None) or []), []) or []
        narratives = []
        for n in raw_narrs:
            try:
                kind = _safe(lambda: str(getattr(n, "kind", "") or ""), "")
                team = _safe(lambda: str(getattr(n, "team_name", "") or ""), "")
                heat = _fnum(getattr(n, "heat", 0), 0.0)
                subjects = []
                for s in _safe(lambda: list(getattr(n, "subjects", None) or []), []) or []:
                    if s:
                        subjects.append({
                            "id": str(s),
                            "name": names.get(s, names.get(str(s), "Unknown Player")),
                        })
                narratives.append({
                    "id": _safe(lambda: str(getattr(n, "id", "") or ""), ""),
                    "kind": kind,
                    "kind_label": _NARR_KINDS.get(kind, kind.replace("_", " ").title() or "Storyline"),
                    "team": team,
                    "team_url": ("/team/" + quote(team)) if team else "",
                    "title": _safe(lambda: str(getattr(n, "title", "") or ""), ""),
                    "subjects": subjects,
                    "heat": round(max(0.0, min(100.0, heat)), 1),
                })
            except Exception:
                continue
        narratives.sort(key=lambda x: -x["heat"])

        raw_beefs = _safe(lambda: list(getattr(league, "coach_media_beefs", None) or []), []) or []
        beefs = []
        for b in raw_beefs:
            try:
                level = int(_fnum(getattr(b, "level", 1), 1))
                team = _safe(lambda: str(getattr(b, "team_name", "") or ""), "")
                beefs.append({
                    "coach": _safe(lambda: str(getattr(b, "coach_name", "") or ""), ""),
                    "reporter": _safe(lambda: str(getattr(b, "reporter_name", "") or ""), ""),
                    "team": team,
                    "team_url": ("/team/" + quote(team)) if team else "",
                    "level": level,
                    "level_label": _BEEF_LEVELS.get(level, f"Level {level}"),
                    "days_quiet": int(_fnum(getattr(b, "days_quiet", 0), 0)),
                })
            except Exception:
                continue
        beefs.sort(key=lambda x: -x["level"])
        return {"narratives": narratives, "beefs": beefs,
                "count": len(narratives) + len(beefs)}
    except Exception:
        return empty


# ---------------------------------------------------------------------------
# Fines ledger: league.media_fines (same source as media_center_window.py)
# ---------------------------------------------------------------------------

def _fines_payload(live):
    empty = {"fines": [], "count": 0, "season_total": 0,
             "season_total_label": "$0"}
    league = _league(live)
    if league is None:
        return empty
    try:
        raw = _safe(lambda: list(getattr(league, "media_fines", None) or []), []) or []
        fines = []
        for f in raw:
            try:
                if not isinstance(f, dict):
                    continue
                d = f.get("date")
                if isinstance(d, (date, datetime)):
                    date_iso = d.isoformat()
                    date_label = d.strftime("%b %d, %Y")
                else:
                    date_iso = ""
                    date_label = _safe(lambda: str(d), "") or ""
                amount = int(_fnum(f.get("amount", 0), 0))
                team = _safe(lambda: str(f.get("team", "") or ""), "")
                fines.append({
                    "date": date_iso,
                    "date_label": date_label,
                    "name": _safe(lambda: str(f.get("name", "") or ""), ""),
                    "team": team,
                    "team_url": ("/team/" + quote(team)) if team else "",
                    "amount": amount,
                    "amount_label": f"${amount:,}",
                    "reason": _safe(lambda: str(f.get("reason", "") or ""), ""),
                    "role": _safe(lambda: str(f.get("role", "") or ""), ""),
                })
            except Exception:
                continue
        fines.sort(key=lambda x: x["date"], reverse=True)
        total = sum(f["amount"] for f in fines)
        return {"fines": fines, "count": len(fines), "season_total": total,
                "season_total_label": f"${total:,}"}
    except Exception:
        return empty


# ---------------------------------------------------------------------------
# Fan buzz: fan_sentiment + fan_narratives per team
# ---------------------------------------------------------------------------

def _fanbuzz_payload(live):
    empty = {"teams": [], "count": 0, "summary": {}}
    league = _league(live)
    if league is None:
        return empty
    try:
        import fan_sentiment as fs
        import fan_narratives as fn
    except Exception:
        return empty
    try:
        current = _safe(lambda: live.current_date)
        teams = []
        for t in _teams(league):
            try:
                name = _team_name(t)
                if not name:
                    continue
                value = _fnum(fs.get_fan_sentiment(t, current), 60.0)
                value = max(0.0, min(100.0, value))
                label = _safe(lambda: str(fs.sentiment_label(value) or ""), "") or "Content"
                tier = _safe(lambda: str(fn.sentiment_tier(value) or ""), "") or "content"
                tone = _safe(lambda: str(fn.media_tone_for_sentiment(t, current) or ""), "") or "neutral"
                trail = _safe(lambda: list(getattr(t, "fan_sentiment_trail", None) or []), []) or []
                drivers = []
                for entry in reversed(trail[-4:]):
                    try:
                        if isinstance(entry, dict):
                            drivers.append({
                                "date": _safe(lambda: str(entry.get("date", "") or ""), ""),
                                "delta": round(_fnum(entry.get("delta", 0.0), 0.0), 1),
                                "reason": _safe(lambda: str(entry.get("reason", "") or ""), ""),
                            })
                    except Exception:
                        continue
                teams.append({
                    "name": name,
                    "url": "/team/" + quote(name),
                    "sentiment": round(value, 1),
                    "label": label,
                    "tier": tier,
                    "media_tone": tone,
                    "drivers": drivers,
                })
            except Exception:
                continue
        # Happiest fanbases first.
        teams.sort(key=lambda x: -x["sentiment"])
        summary = {}
        for tm in teams:
            summary[tm["label"]] = summary.get(tm["label"], 0) + 1
        return {"teams": teams, "count": len(teams), "summary": summary}
    except Exception:
        return empty


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/news")
def news_page():
    return render_template("news.html")


@bp.route("/api/news")
def api_news():
    live = _live()
    if live is None:
        return jsonify({"items": [], "count": 0})
    return jsonify(_news_payload(live))


@bp.route("/api/news/wire")
def api_news_wire():
    live = _live()
    if live is None:
        return jsonify({"items": [], "count": 0, "categories": []})
    return jsonify(_wire_payload(live))


@bp.route("/api/news/journalists")
def api_news_journalists():
    live = _live()
    if live is None:
        return jsonify({"markets": [], "count": 0})
    return jsonify(_journalists_payload(live))


@bp.route("/api/news/narratives")
def api_news_narratives():
    live = _live()
    if live is None:
        return jsonify({"narratives": [], "beefs": [], "count": 0})
    return jsonify(_narratives_payload(live))


@bp.route("/api/news/fines")
def api_news_fines():
    live = _live()
    if live is None:
        return jsonify({"fines": [], "count": 0, "season_total": 0,
                        "season_total_label": "$0"})
    return jsonify(_fines_payload(live))


@bp.route("/api/news/fanbuzz")
def api_news_fanbuzz():
    live = _live()
    if live is None:
        return jsonify({"teams": [], "count": 0, "summary": {}})
    return jsonify(_fanbuzz_payload(live))


# ------------------------------------------------------------------
# Batch C (League) minor: news refresh endpoint. The wire payload is
# already live on every fetch; this returns the lightweight freshness
# signal the refresh button shows ("N stories, updated <time>").
# ------------------------------------------------------------------

@bp.route("/api/news/refresh", methods=["POST"])
def api_news_refresh():
    """Re-read the wire and report freshness. Read-only: the engine owns
    story generation; this just re-pulls the latest."""
    live = _live()
    if live is None:
        return jsonify({"ok": False, "count": 0})
    try:
        payload = _news_payload(live)
        items = payload.get("items", [])
        latest = items[0].get("date_label", "") if items else ""
        return jsonify({"ok": True, "count": len(items),
                        "latest": latest})
    except Exception:
        return jsonify({"ok": False, "count": 0})
