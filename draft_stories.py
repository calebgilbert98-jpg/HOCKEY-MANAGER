# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Draft Story Engine: prospect storylines and draft-day drama.

When the draft class is generated, top prospects get storylines:
- Generational talent (consensus #1)
- Riser (climbing rankings)
- Faller (dropping due to concerns)
- Injury comeback
- Size concerns (small but skilled)
- Character concerns

During the draft, drama events fire:
- Surprise picks (team reaches)
- Slides (top prospect falls)
- Trade-ups

All delivered via headlines.deliver() to the inbox (Muck: inbox, never modal).

Engine boundary: purely narrative, never changes draft logic or player ratings.
"""

import random
from typing import Any, Dict, List, Optional


# Storyline templates
STORYLINES = {
    "generational": {
        "title": "Generational Talent: {name}",
        "body": ("{name} isn't just the consensus #1 pick — scouts are calling "
                 "him a franchise-defining talent. '{quote}' The hype is real."),
        "quotes": [
            "He's the best prospect I've scouted in 20 years",
            "You don't pass on a player like this. Ever.",
            "He changes the math for whoever drafts him",
        ],
    },
    "riser": {
        "title": "Draft Riser: {name}",
        "body": ("{name} has shot up draft boards after a dominant second half. "
                 "Once projected as a mid-first-rounder, he's now in the top-5 "
                 "conversation. '{quote}'"),
        "quotes": [
            "His trajectory is straight up",
            "Teams are falling in love with the compete level",
            "He's forcing his way into the conversation",
        ],
    },
    "faller": {
        "title": "Draft Faller: {name}",
        "body": ("{name} was once in the #1 conversation, but concerns about "
                 "{concern} have him sliding. '{quote}' One team's risk is "
                 "another's steal."),
        "quotes": [
            "The talent is undeniable, but the questions are real",
            "Someone's going to get a bargain — or a headache",
            "He needs the right development situation",
        ],
        "concerns": ["his defensive game", "his consistency", "his skating stride",
                     "his size against men", "his injury history"],
    },
    "injury_comeback": {
        "title": "Comeback Story: {name}",
        "body": ("{name} missed three months with {injury}, but returned to "
                 "dominate the playoffs. '{quote}' The medicals check out, "
                 "and the character shines through."),
        "quotes": [
            "You can't teach that kind of resilience",
            "He was our best player when it mattered most",
            "The injury is behind him — the future isn't",
        ],
        "injuries": ["a shoulder injury", "a knee sprain", "a broken wrist",
                     "a concussion"],
    },
    "small_skilled": {
        "title": "Small But Mighty: {name}",
        "body": ("At {height}, {name} gets the 'too small' label. Then he "
                 "puts up {points} points and silences the room. '{quote}' "
                 "Skill is skill."),
        "quotes": [
            "He plays like he's 6-foot-3",
            "The puck follows him around",
            "Size matters less when you think the game this fast",
        ],
    },
    "character": {
        "title": "Character Questions: {name}",
        "body": ("{name} has top-10 talent, but teams are doing extra homework "
                 "on {issue}. '{quote}' Talent gets you drafted; character "
                 "keeps you employed."),
        "quotes": [
            "We need to be comfortable with the person, not just the player",
            "The interviews will matter as much as the tape",
            "High ceiling, but the floor needs work",
        ],
        "issues": ["his coachability", "his off-ice maturity", "his work ethic",
                   "his attitude after being benched"],
    },
}


def assign_prospect_storylines(prospects: List[Any], seed: Optional[int] = None) -> Dict[Any, Dict[str, Any]]:
    """Assign storylines to top prospects.

    Returns dict mapping prospect -> {type, title, body}.
    Top 30 prospects get storylines. Only a flagged obvious-generational
    prospect (generational=True) gets the 'generational' treatment -- media
    hypes perceived talent, and the flag is what makes perceived talent
    generational. Everyone else, even the consensus #1, gets riser/spotlight
    storylines. Sorted by draft_ranking (the media consensus order).
    """
    if seed is not None:
        random.seed(seed)
    storylines = {}
    if not prospects:
        return storylines

    # Sort by draft_ranking (the media consensus order), overall as tiebreak.
    try:
        ranked = sorted(prospects,
                        key=lambda p: (getattr(p, 'draft_ranking', 0) or 0,
                                       getattr(p, 'overall', 70) or 70),
                        reverse=True)
    except Exception:
        ranked = list(prospects)

    # #1 prospect: 'generational' ONLY for the flagged obvious-generational
    # talent. No flag -- no once-in-a-decade headline, however hyped the name.
    if ranked:
        p1 = ranked[0]
        if getattr(p1, 'generational', False):
            stype = "generational"
        else:
            stype = "riser" if random.random() < 0.6 else "small_skilled"
        storylines[p1] = _make_storyline(p1, stype)

    # Next 29: assign varied storylines
    types = ["riser", "faller", "injury_comeback", "small_skilled", "character"]
    for p in ranked[1:30]:
        # Don't double-assign
        if p in storylines:
            continue
        # Weight: riser/faller more common
        weights = [0.3, 0.25, 0.15, 0.15, 0.15]
        stype = random.choices(types, weights=weights)[0]
        storylines[p] = _make_storyline(p, stype)

    return storylines


def _make_storyline(prospect: Any, stype: str) -> Dict[str, Any]:
    """Build a storyline dict for a prospect."""
    template = STORYLINES.get(stype, STORYLINES["riser"])
    name = getattr(prospect, 'full_name', getattr(prospect, 'name', 'Unknown'))
    quote = random.choice(template.get("quotes", ["He's a player."]))

    # Build format kwargs based on type
    kwargs = {"name": name, "quote": quote}
    if stype == "faller":
        kwargs["concern"] = random.choice(template.get("concerns", ["his game"]))
    elif stype == "injury_comeback":
        kwargs["injury"] = random.choice(template.get("injuries", ["an injury"]))
    elif stype == "small_skilled":
        kwargs["height"] = getattr(prospect, 'height', '5\'9"')
        kwargs["points"] = getattr(getattr(prospect, 'stats', None), 'points', 65) or 65
    elif stype == "character":
        kwargs["issue"] = random.choice(template.get("issues", ["his maturity"]))

    body = template["body"].format(**kwargs)
    title = template["title"].format(name=name)
    return {"type": stype, "title": title, "body": body, "prospect": prospect}


def deliver_prospect_stories(app: Any, storylines: Dict[Any, Dict[str, Any]]):
    """Deliver prospect storyline headlines to the inbox."""
    try:
        from headlines import deliver
        from game_classes import EmailMessage
        import uuid
        from datetime import date
    except Exception:
        return

    # Deliver top 5 storylines (avoid spam)
    count = 0
    for prospect, story in list(storylines.items())[:5]:
        try:
            msg = EmailMessage(
                id=str(uuid.uuid4()),
                subject=story["title"],
                body=story["body"],
                sender="Draft Central",
                date=getattr(app, "current_date", date.today()).isoformat(),
                category="draft",
            )
            # involved: no specific team (league-wide)
            deliver(app, msg, involved=())
            count += 1
        except Exception:
            continue


def draft_pick_drama(app: Any, pick_number: int, prospect: Any,
                     team: Any, projected_rank: int):
    """Fire draft-day drama for a pick.

    - Reach: picked 10+ spots above projection -> "Surprise Pick!"
    - Slide: picked 10+ spots below projection -> "Steal of the Draft?"
    - Expected: top-3 pick at projection -> milestone
    """
    try:
        from headlines import deliver
        from game_classes import EmailMessage
        import uuid
        from datetime import date
    except Exception:
        return

    name = getattr(prospect, 'full_name', getattr(prospect, 'name', 'Unknown'))
    team_name = getattr(team, 'team_name', 'Unknown')
    diff = projected_rank - pick_number  # positive = reached, negative = slid

    subject = None
    body = None
    if pick_number <= 3 and abs(diff) <= 2:
        # Expected top pick
        subject = f"#{pick_number} Pick: {name} to {team_name}"
        body = (f"As expected, {team_name} selects {name} with the "
                f"#{pick_number} overall pick.")
    elif diff >= 10:
        # Reach!
        subject = f"Surprise! {team_name} reaches for {name} at #{pick_number}"
        body = (f"{team_name} stuns the draft floor, taking {name} at "
                f"#{pick_number} — {diff} spots above his #{projected_rank} "
                f"projection. 'We had him ranked much higher internally,' "
                f"said the GM.")
    elif diff <= -10:
        # Slide!
        subject = f"Steal? {name} slides to {team_name} at #{pick_number}"
        body = (f"{name} tumbles to #{pick_number}, {abs(diff)} spots below "
                f"his #{projected_rank} projection. {team_name} couldn't "
                f"believe he was still there.")

    if subject:
        try:
            msg = EmailMessage(
                id=str(uuid.uuid4()),
                subject=subject,
                body=body,
                sender="Draft Central",
                date=getattr(app, "current_date", date.today()).isoformat(),
                category="draft",
                is_milestone=(pick_number <= 3),
            )
            deliver(app, msg, involved=(team_name,))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Part 3: headline storylines + monthly season beats (narrative only).
#
# Pure functions: they build story dicts and never mutate game state.
# Prospect attributes draft_hype / draft_pressure / junior_league may not
# exist on old saves, so every read goes through getattr with a fallback.
# Deterministic under a pinned random.seed (random module only).
# ---------------------------------------------------------------------------

_NA_NATIONS = {"canada", "canadian", "usa", "united states", "american", "us"}

_BEAT_QUOTES = [
    "He's the name that keeps coming up in every war room.",
    "The tools are all there — it's just a matter of when, not if.",
    "You can feel the buzz every time he steps on the ice.",
    "Scouts leave his games shaking their heads, in a good way.",
]


def _beat_name(p):
    return getattr(p, 'full_name', getattr(p, 'name', 'Unknown Prospect'))


def _beat_id(p):
    return getattr(p, 'id', None) or _beat_name(p)


def _rank_score(p):
    try:
        return float(getattr(p, 'draft_ranking', 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _nation_of(p):
    return str(getattr(p, 'nationality', '') or '').strip()


def _league_of(p):
    return str(getattr(p, 'junior_league', '') or '').strip()


def _hype_of(p, rank_pos=None, total=None):
    """draft_hype (0-100) with a consensus-rank fallback for old saves."""
    h = getattr(p, 'draft_hype', None)
    try:
        if h is not None:
            return max(0.0, min(100.0, float(h)))
    except (TypeError, ValueError):
        pass
    if rank_pos is not None and total:
        # Top-ranked prospect ~100, fading down the board.
        return max(0.0, 100.0 - (rank_pos - 1) * (95.0 / max(total, 1)))
    return 0.0


def _pressure_of(p):
    pr = getattr(p, 'draft_pressure', None)
    try:
        if pr is not None:
            return max(0.0, min(100.0, float(pr)))
    except (TypeError, ValueError):
        pass
    return 0.0


def _is_na(p):
    return _nation_of(p).lower() in _NA_NATIONS


def _projected_range(rank_pos):
    """Human-readable projected range from a 1-based consensus rank."""
    if rank_pos <= 1:
        return "in the #1 overall conversation"
    if rank_pos <= 3:
        return "a projected top-3 pick"
    if rank_pos <= 5:
        return "a projected top-5 pick"
    if rank_pos <= 10:
        return "a projected top-10 pick"
    if rank_pos <= 32:
        return "a projected first-rounder"
    if rank_pos <= 64:
        return "a projected second-rounder"
    return "a projected mid-round pick"


def _ranked(prospects):
    """Prospects sorted best-first by draft_ranking (higher = better)."""
    return sorted(prospects, key=_rank_score, reverse=True)


def _situation_bits(p):
    """'Swedish winger out of the SHL'-style context, old-save safe."""
    nat = _nation_of(p)
    league = _league_of(p)
    if nat and league:
        return "%s out of the %s" % (nat, league)
    if nat:
        return nat
    if league:
        return "a product of the %s" % league
    return "a junior standout"


def assign_headline_storylines(prospects, draft_year):
    """Pick 3-5 headline storylines for the draft class.

    - Headliner: the highest-hype prospect. ONLY a flagged obvious-generational
      talent gets the "Generational Watch" once-in-a-decade treatment; any
      other headliner is a "Top Prospect Spotlight" -- media hypes perceived
      talent, and only the flag means perceived-generational.
    - Highest-hype non-NA prospect -> "international intrigue" headline.
    - Highest draft_pressure prospect -> "pressure cooker" feature.
    - Filled out to 3-5 with a runner-up riser and/or a class-depth note.

    Returns a list of story dicts: {title, text, tags, prospect_id}.
    Narrative-only: never mutates prospects or game state.
    """
    stories = []
    prospects = list(prospects or [])
    if not prospects:
        return stories

    ranked = _ranked(prospects)
    pos_of = {id(p): i + 1 for i, p in enumerate(ranked)}
    total = len(ranked)
    used = set()

    def hype(p):
        return _hype_of(p, pos_of.get(id(p)), total)

    # 1. Headliner: the highest-hype prospect in the class. Only a flagged
    # obvious-generational talent gets the once-in-a-decade "Generational
    # Watch" treatment; any other headliner is a spotlight story, never
    # generational language. Hidden gems are never hyped here -- this runs
    # on perceived stock, not hidden true ceiling.
    top = max(ranked, key=hype)
    used.add(id(top))
    name = _beat_name(top)
    rng = _projected_range(pos_of[id(top)])
    sit = _situation_bits(top)
    if getattr(top, 'generational', False):
        stories.append({
            "title": "Generational Watch: %s" % name,
            "text": ("%s, %s, is %s and the %s class runs through him. "
                     "Scouts are using the word nobody uses lightly: "
                     "generational, a once-in-a-decade talent. '%s'"
                     % (name, sit, rng, draft_year,
                        random.choice(_BEAT_QUOTES))),
            "tags": ["draft", "headline", "generational"],
            "prospect_id": _beat_id(top),
        })
    else:
        stories.append({
            "title": "Top Prospect Spotlight: %s" % name,
            "text": ("%s, %s, is %s and the name every war room has circled "
                     "for the %s class. The debate isn't whether he goes "
                     "early -- it's how early. '%s'"
                     % (name, sit, rng, draft_year,
                        random.choice(_BEAT_QUOTES))),
            "tags": ["draft", "headline", "top-prospect"],
            "prospect_id": _beat_id(top),
        })

    # 2. International intrigue: highest-hype prospect from outside North
    # America (needs a real nationality; old saves without one are skipped).
    intl_candidates = [p for p in ranked
                       if id(p) not in used and _nation_of(p) and not _is_na(p)]
    if intl_candidates:
        intl = max(intl_candidates, key=hype)
        used.add(id(intl))
        iname = _beat_name(intl)
        irng = _projected_range(pos_of[id(intl)])
        isit = _situation_bits(intl)
        stories.append({
            "title": "International Intrigue: %s" % iname,
            "text": ("%s, %s, is %s and the most debated overseas name in the "
                     "%s class. Cross-ice scouts call him the draft's great "
                     "unknown — '%s'"
                     % (iname, isit, irng, draft_year, random.choice(_BEAT_QUOTES))),
            "tags": ["draft", "headline", "international"],
            "prospect_id": _beat_id(intl),
        })

    # 3. Pressure cooker: the prospect carrying the most draft pressure.
    press_candidates = [p for p in ranked if id(p) not in used]
    if press_candidates:
        press = max(press_candidates, key=_pressure_of)
        used.add(id(press))
        pname = _beat_name(press)
        prng = _projected_range(pos_of[id(press)])
        psit = _situation_bits(press)
        stories.append({
            "title": "Pressure Cooker: %s" % pname,
            "text": ("No prospect faces a bigger spotlight than %s, %s, %s. "
                     "Every shift is dissected, every interview graded — "
                     "how he handles the glare may decide his draft slot."
                     % (pname, psit, prng)),
            "tags": ["draft", "headline", "pressure"],
            "prospect_id": _beat_id(press),
        })

    # 4-5. Fillers: hype runner-up + class-depth note (keeps it at 3-5).
    remaining = [p for p in ranked if id(p) not in used]
    if remaining:
        runner = max(remaining, key=hype)
        used.add(id(runner))
        rname = _beat_name(runner)
        rrng = _projected_range(pos_of[id(runner)])
        rsit = _situation_bits(runner)
        stories.append({
            "title": "Riser to Watch: %s" % rname,
            "text": ("%s, %s, is %s and climbing — scouts say his second half "
                     "forced its way into every first-round conversation for %s."
                     % (rname, rsit, rrng, draft_year)),
            "tags": ["draft", "headline", "riser"],
            "prospect_id": _beat_id(runner),
        })
    if len(stories) < 5 and total >= 20:
        stories.append({
            "title": "The %s Class Has Depth" % draft_year,
            "text": ("Beyond the headliners, scouts rave about the %s class's "
                     "depth — legitimate NHL bets are projected well into the "
                     "second round, and day-two steals feel inevitable."
                     % draft_year),
            "tags": ["draft", "headline", "depth"],
            "prospect_id": None,
        })

    return stories[:5]


def season_beats(prospects, draft_year, month):
    """Monthly draft build-up stories, January through June.

    - Jan: mid-season mock draft (top 10 by draft_ranking, risers/fallers
      vs a jittered earlier list).
    - Feb/Mar: "hometown kid" feature.
    - Apr: combine standouts (3 prospects, hype-flavored).
    - May: final mock draft (top 5).
    - Jun: draft-week buzz (1-2 items).

    Returns 1-3 story dicts {title, text, tags, prospect_id}. Other months
    return []. Narrative-only; deterministic under a pinned random.seed.
    """
    prospects = list(prospects or [])
    if not prospects or month not in (1, 2, 3, 4, 5, 6):
        return []
    ranked = _ranked(prospects)
    pos_of = {id(p): i + 1 for i, p in enumerate(ranked)}
    total = len(ranked)

    def hype(p):
        return _hype_of(p, pos_of.get(id(p)), total)

    if month == 1:
        # Mid-season mock: jitter the board to fake an "earlier" ranking,
        # then flag risers/fallers among the current top 10.
        jittered = {id(p): _rank_score(p) + random.uniform(-8, 8) for p in ranked}
        earlier = sorted(ranked, key=lambda p: jittered[id(p)], reverse=True)
        earlier_pos = {id(p): i + 1 for i, p in enumerate(earlier)}
        top10 = ranked[:10]
        risers, fallers = [], []
        for p in top10:
            delta = earlier_pos[id(p)] - pos_of[id(p)]  # + = climbed
            if delta >= 3:
                risers.append((_beat_name(p), delta))
            elif delta <= -3:
                fallers.append((_beat_name(p), -delta))
        board = ", ".join("%d. %s" % (i, _beat_name(p))
                          for i, p in enumerate(top10, 1))
        text = "Mid-season mock draft (%s): %s." % (draft_year, board)
        if risers:
            text += " Risers: %s." % ", ".join(
                "%s (+%d)" % (n, d) for n, d in risers[:3])
        if fallers:
            text += " Fallers: %s." % ", ".join(
                "%s (-%d)" % (n, d) for n, d in fallers[:3])
        return [{
            "title": "Mid-Season Mock Draft: %s" % draft_year,
            "text": text,
            "tags": ["draft", "beat", "mock", "january"],
            "prospect_id": _beat_id(top10[0]),
        }]

    if month in (2, 3):
        # Hometown kid: the highest-hype prospect from a traditional
        # hockey market (Canada/USA); falls back to the top-hype prospect.
        na = [p for p in ranked if _is_na(p)]
        kid = max(na, key=hype) if na else max(ranked, key=hype)
        kname = _beat_name(kid)
        krng = _projected_range(pos_of[id(kid)])
        ksit = _situation_bits(kid)
        nat = _nation_of(kid) or "North American"
        return [{
            "title": "Hometown Kid: %s" % kname,
            "text": ("%s, %s, is %s — and the %s kid every local broadcast "
                     "has adopted. '%s'"
                     % (kname, ksit, krng, nat, random.choice(_BEAT_QUOTES))),
            "tags": ["draft", "beat", "hometown"],
            "prospect_id": _beat_id(kid),
        }]

    if month == 4:
        # Combine standouts: 3 highest-hype prospects, testing-flavored.
        standouts = sorted(ranked, key=hype, reverse=True)[:3]
        drills = ["the shuttle run", "the VO2 bike test", "the agility circuit",
                  "the wingate sprint", "the reaction drills"]
        bits = ["%s (%s)" % (_beat_name(p), random.choice(drills))
                for p in standouts]
        lead = standouts[0]
        lname = _beat_name(lead)
        lrng = _projected_range(pos_of[id(lead)])
        lsit = _situation_bits(lead)
        return [{
            "title": "Combine Standouts Turn Heads",
            "text": ("Testing week belonged to %s and %s. %s, %s, %s, looked "
                     "every bit the athlete the hype promised."
                     % (", ".join(bits[:-1]), bits[-1], lname, lsit, lrng)),
            "tags": ["draft", "beat", "combine"],
            "prospect_id": _beat_id(lead),
        }]

    if month == 5:
        # Final mock: top 5 by consensus ranking.
        top5 = ranked[:5]
        board = ", ".join("%d. %s" % (i, _beat_name(p))
                          for i, p in enumerate(top5, 1))
        return [{
            "title": "Final Mock Draft: %s" % draft_year,
            "text": ("One month out, the %s board has settled: %s. After this, "
                     "it's interviews, medicals, and poker faces."
                     % (draft_year, board)),
            "tags": ["draft", "beat", "mock", "may"],
            "prospect_id": _beat_id(top5[0]),
        }]

    # month == 6: draft-week buzz, 1-2 items.
    buzz = []
    top = max(ranked, key=hype)
    tname = _beat_name(top)
    trng = _projected_range(pos_of[id(top)])
    tsit = _situation_bits(top)
    buzz.append({
        "title": "Draft-Week Buzz",
        "text": ("%s, %s, %s, is the name on every scout's lips as draft week "
                 "opens. '%s'"
                 % (tname, tsit, trng, random.choice(_BEAT_QUOTES))),
        "tags": ["draft", "beat", "buzz"],
        "prospect_id": _beat_id(top),
    })
    intl = next((p for p in sorted(ranked, key=hype, reverse=True)
                 if id(p) != id(top) and _nation_of(p) and not _is_na(p)), None)
    if intl is not None:
        iname = _beat_name(intl)
        isit = _situation_bits(intl)
        buzz.append({
            "title": "Last-Minute Whispers",
            "text": ("Whispers out of war rooms: %s, %s, could go earlier than "
                     "anyone's mock has him. Draft week loves a surprise."
                     % (iname, isit)),
            "tags": ["draft", "beat", "buzz"],
            "prospect_id": _beat_id(intl),
        })
    return buzz


# ---------------------------------------------------------------------------
# Post-draft "steal of the draft" retrospective
# ---------------------------------------------------------------------------

_STEAL_GRADES = {"B+", "A-", "A", "A+"}


def steal_retrospective(league) -> list:
    """Find late-round draft picks whose stock has exploded since draft day.

    Scans every club's roster + prospect pool for players drafted in round 4+
    whose DISPLAYED potential grade has since risen to B+ or better while
    their draft-day hype was modest (draft_hype <= 45) -- the Datsyuk story:
    nobody hyped them then, everyone knows the name now. Narrative-only:
    never mutates prospects or game state.

    Returns a list of story dicts {title, text, tags, prospect_id} (max 2 per
    call). Already-covered players (league.steal_retro_posted) are skipped so
    the same steal isn't celebrated twice.
    """
    stories = []
    try:
        teams = getattr(league, "teams", None) or []
        posted = getattr(league, "steal_retro_posted", None)
        if posted is None:
            posted = set()
            league.steal_retro_posted = posted

        candidates = []
        for team in teams:
            pool = list(getattr(team, "roster", None) or []) + \
                list(getattr(team, "prospects", None) or [])
            for p in pool:
                try:
                    dround = int(getattr(p, "draft_round", 0) or 0)
                    if dround < 4:
                        continue
                    if int(getattr(p, "age", 99) or 99) > 26:
                        continue
                    grade = (getattr(p, "potential_grade", "") or "").strip()
                    if grade not in _STEAL_GRADES:
                        continue
                    if float(getattr(p, "draft_hype", 100) or 100) > 45:
                        continue
                    key = _beat_id(p)
                    if key in posted:
                        continue
                    candidates.append((dround, p))
                except Exception:
                    continue

        # Latest rounds first (bigger steals), then by grade.
        _order = {"B+": 0, "A-": 1, "A": 2, "A+": 3}
        candidates.sort(
            key=lambda t: (t[0],
                           _order.get((getattr(t[1], "potential_grade", "") or "").strip(), 0)),
            reverse=True)

        for dround, p in candidates[:2]:
            name = _beat_name(p)
            grade = (getattr(p, "potential_grade", "") or "").strip()
            team_name = getattr(p, "team_name", "") or ""
            tname = getattr(
                getattr(p, "team", None), "team_name", team_name) or team_name
            stories.append({
                "title": "Steal of the Draft: %s" % name,
                "text": ("Remember the %s draft? %s went in round %d, barely "
                         "a footnote on draft night. Now he's tracking as a "
                         "%s-grade talent%s -- the kind of pick scouting "
                         "departments get remembered for. Every war room has "
                         "a story about the one that got away; %s is %s's."
                         % (getattr(p, "drafted_year", "that"),
                            name, dround, grade,
                            " for %s" % tname if tname else "",
                            name, tname or "someone's")),
                "tags": ["draft", "retrospective", "steal"],
                "prospect_id": _beat_id(p),
            })
            posted.add(_beat_id(p))
    except Exception:
        pass
    return stories
