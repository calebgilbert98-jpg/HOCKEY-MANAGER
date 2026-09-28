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
    Top 30 prospects get storylines; #1 is always 'generational' (or 'riser'
    if they're not clearly ahead).
    """
    if seed is not None:
        random.seed(seed)
    storylines = {}
    if not prospects:
        return storylines

    # Sort by projected rank (assume prospects are already ranked, or sort by overall)
    try:
        ranked = sorted(prospects,
                        key=lambda p: getattr(p, 'overall', 70),
                        reverse=True)
    except Exception:
        ranked = list(prospects)

    # #1 prospect: generational (70%) or riser (30%)
    if ranked:
        p1 = ranked[0]
        stype = "generational" if random.random() < 0.7 else "riser"
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
