"""Pre-season coach expectations meeting -- the CONVERSATION UI half.

Chris's directive: before camp / the fantasy draft / a new coach hire / a new
save starts, the GM sits down with his head coach and outlines the season.
Back-and-forth, driven by the coach's personality (ambition, control_need,
morale, working_with_youngsters, first_nhl_chair, ...).

This module owns:
  - SeasonMeetingView: a Tier-1 full-screen conversation window (Eastside
    gating -- non-modal; the user can leave via the menu bar and come back;
    in-progress state lives on team.season_meeting_draft so the conversation
    resumes where it left off).
  - open_season_meeting(app): the entry point the advance-blocker wires its
    "Open Season Meeting" action to (lazy-import-safe signature).
  - build_season_meeting_banner(parent, app): persistent dashboard entry
    point while the meeting is pending.

The mandate model, trigger hooks, the advance-blocker, downstream wiring and
AI resolution live in the sibling module coach_season_meeting.py (built by
the other builder). This file only CONSUMES that contract, defensively:
every sibling import is lazy and guarded, with sane fallbacks (ai_gm_identity,
season_review, coach_practice) so the window degrades cleanly if the sibling
module is absent.
"""

import random

try:
    import customtkinter as ctk
except Exception:  # pragma: no cover - hard dependency in practice
    ctk = None

__all__ = [
    "SeasonMeetingView",
    "open_season_meeting",
    "build_season_meeting_banner",
    "season_meeting_is_pending",
]


# ---------------------------------------------------------------------------
# Contract-consumption layer (sibling module: coach_season_meeting.py)
# ---------------------------------------------------------------------------

def _sibling():
    """Lazy import of the sibling contract module; None if not landed yet."""
    try:
        import coach_season_meeting as _m
        return _m
    except Exception:
        return None


_RUNGS = ["win_cup", "contend", "playoffs", "rebuild"]


def season_expectations():
    m = _sibling()
    seq = getattr(m, "SEASON_EXPECTATIONS", None) if m is not None else None
    if seq:
        return list(seq)
    return list(_RUNGS)


def expected_pace():
    m = _sibling()
    pace = getattr(m, "EXPECTED_PACE", None) if m is not None else None
    if pace:
        return dict(pace)
    try:
        from ai_gm_identity import EXPECTED_PACE as _p
        return dict(_p)
    except Exception:
        return {"win_cup": 0.650, "contend": 0.600,
                "playoffs": 0.550, "rebuild": 0.450}


def ambition_drive():
    m = _sibling()
    drv = getattr(m, "AMBITION_DRIVE", None) if m is not None else None
    if drv:
        return dict(drv)
    try:
        from ai_gm_identity import AMBITION_DRIVE as _d
        return dict(_d)
    except Exception:
        return {"stanley_cup": 1.00, "climb": 0.70, "hometown": 0.50,
                "lifer": 0.35, "developer": 0.25}


def _get_head_coach(team):
    m = _sibling()
    if m is not None:
        fn = getattr(m, "get_head_coach", None)
        if callable(fn):
            try:
                coach = fn(team)
                if coach is not None:
                    return coach
            except Exception:
                pass
    try:
        from coach_practice import head_coach_of
        return head_coach_of(team)
    except Exception:
        return None


def _expectation_from_strength(strength):
    try:
        from ai_gm_identity import expectation_from_strength as _f
        return _f(strength)
    except Exception:
        pass
    try:
        s = float(strength)
    except (TypeError, ValueError):
        s = 55.0
    if s >= 72:
        return "win_cup"
    if s >= 62:
        return "contend"
    if s >= 52:
        return "playoffs"
    return "rebuild"


def _roster_strength(team):
    try:
        from season_review import roster_strength as _f
        return float(_f(team) or 0.0)
    except Exception:
        return 0.0


def _normalize_expectation(res):
    if isinstance(res, str) and res in _RUNGS:
        return res
    if isinstance(res, dict):
        exp = res.get("expectation")
        if exp in _RUNGS:
            return exp
    return None


def coach_assessment(team, coach):
    """The coach's OWN read on the season. Sibling API first, fallback local."""
    m = _sibling()
    if m is not None:
        fn = getattr(m, "coach_season_assessment", None)
        if callable(fn):
            try:
                norm = _normalize_expectation(fn(team, coach))
                if norm:
                    return norm
            except Exception:
                pass
    # Fallback: strength-based, nudged by ambition.
    base = _expectation_from_strength(_roster_strength(team))
    ambition = (getattr(coach, "ambition", "climb") or "climb")
    i = _RUNGS.index(base)
    if ambition == "stanley_cup" and i > 0:
        i -= 1
    elif ambition == "developer" and i < len(_RUNGS) - 1:
        i += 1
    return _RUNGS[i]


def _board_expectation(app):
    try:
        board = getattr(getattr(app, "career", None), "board", None)
        exp = getattr(board, "expectation", None)
        if exp in _RUNGS:
            return exp
    except Exception:
        pass
    return None


def season_meeting_is_pending(team):
    m = _sibling()
    if m is not None:
        fn = getattr(m, "is_meeting_pending", None)
        if callable(fn):
            try:
                return bool(fn(team))
            except Exception:
                pass
    return bool(getattr(team, "season_meeting_pending", False))


def _finalize_meeting(team, mandate):
    """Completion call: store_mandate is THE sibling API (validates, applies
    trust + downstream wiring, stores the mandate, clears pending). Older
    guessed names follow; the direct write is the last resort."""
    m = _sibling()
    if m is not None:
        for fn_name in ("store_mandate", "complete_season_meeting",
                        "finalize_season_meeting", "finish_season_meeting",
                        "clear_season_meeting"):
            fn = getattr(m, fn_name, None)
            if not callable(fn):
                continue
            try:
                fn(team, mandate)
                return True
            except TypeError:
                try:
                    fn(team)
                    return True
                except Exception:
                    continue
            except Exception:
                continue
    # Fallback: write the contract's model shape directly.
    try:
        team.season_mandate = dict(mandate)
        team.season_meeting_pending = False
        return True
    except Exception:
        return False


def _meeting_reason(team) -> str:
    """The arming reason the sibling stashed in season_meeting_context."""
    try:
        ctx = getattr(team, "season_meeting_context", None) or {}
        return str(ctx.get("reason") or "")
    except Exception:
        return ""


def _identity_presets():
    try:
        from tactics import IDENTITY_PRESETS
        return dict(IDENTITY_PRESETS)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Trust tuning -- ALL constants below need Chris's approval before push.
# ---------------------------------------------------------------------------
TRUST_EXPECT_ALIGNED       = +6   # coach's read == GM's mandate
TRUST_EXPECT_ABOVE_WELCOME = +4   # ambitious coach handed a bigger target
TRUST_EXPECT_DEFER         = +2   # rookie chair defers to the GM
TRUST_EXPECT_PRAGMATIC     = +1   # loyal/pragmatic buy-in
TRUST_EXPECT_MILD          = -3   # mild pushback / disappointment
TRUST_EXPECT_TANK_REFUSAL  = -7   # "I can't coach a tank"
TRUST_ROOKIE_ALIGNED       = +3
TRUST_ROOKIE_FRICTION      = -3
TRUST_ROOKIE_STRONG        = -5   # kids thrown to a win-now wolves den
TRUST_TACTICS_FIT          = +3
TRUST_TACTICS_MISFIT       = -2
TRUST_KEEP_HIGH_CONTROL    = +3   # authoritarian keeps his domain
TRUST_KEEP_LOW_CONTROL     = +2   # collaborative appreciates trust
TRUST_KEEP_MID             = +2
TRUST_TAKE_HIGH_CONTROL    = -6   # authoritarian loses his domain
TRUST_TAKE_MID             = -2
TRUST_TAKE_LOW_CONTROL     = +1   # collaborative rolls with it
TRUST_TAKE_FIRST_CHAIR     = +2   # rookie defers
TRUST_DEPLOYER_REASSURE_HI = +2   # grudging acceptance
TRUST_DEPLOYER_REASSURE_LO = +4
TRUST_DEPLOYER_EXPECT_HI   = -4   # cold "Understood."
TRUST_DEPLOYER_EXPECT_LO   = -1
TRUST_DEPLOYER_DEMAND_HIT  = -3   # proud coach bristles
TRUST_DEPLOYER_DEMAND_LOYAL = +1


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

_EXPECT_LABELS = {
    "win_cup":  ("Win the Cup", "Nothing less."),
    "contend":  ("Contend", "We're in the mix."),
    "playoffs": ("Make the playoffs", "Then see what happens."),
    "rebuild":  ("Rebuild", "Develop, and live with the losses."),
}

_ROOKIE_LABELS = {
    "heavy":     ("Heavy minutes", "Top-six / top-four, mistakes included."),
    "earned":    ("Earned ice", "Win it in camp, keep it with your play."),
    "sheltered": ("Sheltered", "Third line, protected starts, no drowning."),
    "none":      ("AHL year", "Nobody's rushed. They marinate."),
}

_AMBITION_LABELS = {
    "stanley_cup": "Cup-or-bust",
    "climb": "On the climb",
    "developer": "Developer",
    "hometown": "Hometown guy",
    "lifer": "Lifer",
}


# ---------------------------------------------------------------------------
# Coach archetype helpers
# ---------------------------------------------------------------------------

def _num(v, default=50.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _control(coach):
    return _num(getattr(coach, "control_need", 50), 50.0)


def _drive(coach):
    return ambition_drive().get(getattr(coach, "ambition", "climb") or "climb", 0.5)


def _youngsters(coach):
    return _num(getattr(coach, "working_with_youngsters", 50), 50.0)


def _ambition(coach):
    return (getattr(coach, "ambition", "climb") or "climb")


def _is_authoritarian(coach):
    return _control(coach) >= 75


def _is_collaborative(coach):
    return _control(coach) <= 40


def _is_first_chair(coach):
    return bool(getattr(coach, "first_nhl_chair", False))


def _is_developer(coach):
    return _ambition(coach) == "developer" or _youngsters(coach) >= 75


def _is_loyal(coach):
    return _ambition(coach) in ("lifer", "hometown")


def _is_win_now_ambitious(coach):
    return _ambition(coach) == "stanley_cup" or (
        _ambition(coach) == "climb" and _drive(coach) >= 0.7)


def _coach_name(coach):
    try:
        return coach.full_name()
    except Exception:
        first = getattr(coach, "first_name", "") or ""
        last = getattr(coach, "last_name", "") or ""
        return (first + " " + last).strip() or "Coach"


def _coach_role(coach):
    try:
        role = getattr(coach, "role", None)
        return str(getattr(role, "value", role) or "Head Coach")
    except Exception:
        return "Head Coach"


def _personality_chips(coach):
    """Short human reads for the header: (label, value) pairs."""
    chips = []
    chips.append(("Ambition", _AMBITION_LABELS.get(_ambition(coach), "Climb")))
    c = _control(coach)
    chips.append(("Style", "Authoritarian" if c >= 75 else
                  "Collaborative" if c <= 40 else "Balanced"))
    y = _youngsters(coach)
    chips.append(("Youth", "Trusts kids" if y >= 70 else
                  "Veterans-first" if y <= 35 else "Measured"))
    morale = _num(getattr(coach, "morale", 60), 60.0)
    chips.append(("Mood", "Upbeat" if morale >= 70 else
                  "Grumbling" if morale <= 40 else "Steady"))
    if _is_first_chair(coach):
        chips.append(("Note", "First NHL chair"))
    return chips


def _coach_style(coach):
    atk = _num(getattr(coach, "attacking_coaching", 50), 50.0)
    dfn = _num(getattr(coach, "defensive_coaching", 50), 50.0)
    if atk >= dfn + 12:
        return "attack"
    if dfn >= atk + 12:
        return "defense"
    return "balanced"


_PRESET_STYLE = {
    "chaos_pressure": "attack",
    "stranglehold": "defense",
    "hybrid_transition": "balanced",
}


def _trust_text(delta):
    return f"Trust {delta:+d}"


# ---------------------------------------------------------------------------
# Coach voice -- template pools, personality-weighted.
# (Question/answer dict style mirrors manager_career.build_prematch_presser.)
# ---------------------------------------------------------------------------

def _pick(rng, pool):
    return rng.choice(pool) if pool else ""


def _opening_line(coach, rng, reason=""):
    if _is_authoritarian(coach):
        pool = [
            "Sit down. Let's get one thing straight before camp: I coach to win. Tell me that's still the job.",
            "Close the door. I've got a room full of players asking me what this season is -- I'd rather hear it from you.",
            "No speeches. Tell me what you expect, and I'll tell you if I can coach it.",
        ]
    elif _is_collaborative(coach):
        pool = [
            "Appreciate you doing this. I'd rather hear the plan from you than read it in the papers.",
            "Good -- let's get aligned before camp. Nothing worse than a room hearing two different plans.",
            "Coffee's on me. Talk to me about the year you have in mind.",
        ]
    elif _is_developer(coach):
        pool = [
            "Good -- let's talk about the kids too, not just the standings. Both matter to me.",
            "Before we start: whatever the target is, I want the young ones part of it. Deal?",
        ]
    else:
        pool = [
            "Close the door. Before camp opens, I need to know what this season is actually about.",
            "Alright -- the room looks to me, I look to you. What's the plan?",
        ]
    if _is_first_chair(coach):
        pool = pool + [
            "Thanks for this. You gave me this chair -- I want to make sure I'm building what you pictured.",
        ]
    morale = _num(getattr(coach, "morale", 60), 60.0)
    if morale <= 40:
        pool = pool + ["Let's get this over with. What's the plan?"]
    if reason == "new_coach":
        pool = pool + [
            "New chair, new season. Tell me what you expect, and I'll tell you if I can coach it.",
            "First sit-down in this office. I want to hear the plan from you, straight.",
        ]
    elif reason == "fantasy_draft":
        pool = pool + [
            "Fresh roster, blank slate. Tell me what this season is about.",
        ]
    return _pick(rng, pool)

# ---------------------------------------------------------------------------
# Beat: season expectations
# ---------------------------------------------------------------------------

def expectation_options(team, board_exp):
    """The plausible rungs, from roster strength + the board's mandate.

    Rule: spread around the roster-based rung (one above, two below). The
    board's rung joins the menu only if it is at-or-below what the roster
    earns -- patience is always legitimate, ambition the roster can't cash
    is not. 'win_cup' is only ever on the menu when the roster itself says
    win_cup: never offer a Cup mandate to a 50-strength roster.
    """
    base = _expectation_from_strength(_roster_strength(team))
    offered = []

    def spread(rung):
        out = []
        i = _RUNGS.index(rung)
        if i > 0:
            out.append(_RUNGS[i - 1])
        out.append(rung)
        out.extend(_RUNGS[i + 1:i + 3])
        return out

    for rung in spread(base):
        # Win-the-Cup gate: the roster must earn it on the menu.
        if rung == "win_cup" and base != "win_cup":
            continue
        if rung not in offered:
            offered.append(rung)
    # The board's mandate joins the menu only if it is at-or-below what the
    # roster earns (patience is always a legitimate choice; ambition the
    # roster can't cash is not).
    if board_exp in _RUNGS and board_exp not in offered:
        if _RUNGS.index(board_exp) >= _RUNGS.index(base):
            offered.append(board_exp)
    order = {r: i for i, r in enumerate(_RUNGS)}
    return sorted(offered, key=lambda r: order[r])


def _expectation_reaction(coach, chosen, assessed, rng):
    """(coach_text, trust_delta, note, misaligned)."""
    ci, ai = _RUNGS.index(chosen), _RUNGS.index(assessed)
    note, misaligned = "", False
    if chosen == assessed:
        if _is_first_chair(coach):
            text = _pick(rng, [
                "That's the season I pictured when you hired me. I'm in.",
                "Good -- that's exactly how I read this group. We're aligned.",
            ])
            delta = TRUST_EXPECT_ALIGNED
        elif _is_developer(coach) and chosen == "rebuild":
            text = _pick(rng, [
                "Good. No pretending. We develop, we teach, and the wins come when they're ready.",
                "Honest plan. The kids will feel the patience -- that's when they grow.",
            ])
            delta = TRUST_EXPECT_ALIGNED
        elif _is_win_now_ambitious(coach) and chosen in ("win_cup", "contend"):
            text = _pick(rng, [
                "Now you're speaking my language. Give me a healthy room and I'll give you June hockey.",
                "That's why I'm here. Say it to the room too -- they'll run through a wall.",
            ])
            delta = TRUST_EXPECT_ALIGNED
        else:
            text = _pick(rng, [
                "Alright. Then everything we do this year serves that. I can coach that.",
                "Clear target. I'll build the whole year around it.",
                "Good -- one plan, no mixed messages. The room will appreciate that.",
            ])
            delta = TRUST_EXPECT_ALIGNED
        note = (f"Coach's own read matched the mandate "
                f"({_EXPECT_LABELS[assessed][0]}).")
    elif ci < ai:
        # GM is MORE ambitious than the coach's read.
        if _is_win_now_ambitious(coach):
            text = _pick(rng, [
                "You don't have to sell me. I've been waiting for someone to say it out loud.",
                "Bigger than I had it -- good. I'd rather chase something than protect something.",
            ])
            delta = TRUST_EXPECT_ABOVE_WELCOME
            note = "Coach welcomed the bigger target."
        elif _is_authoritarian(coach):
            text = _pick(rng, [
                "Careful. Don't hand me a target I can't hit and then act surprised in March.",
                "Ambitious. Just remember who has to stand in front of the room and sell it.",
            ])
            delta = TRUST_EXPECT_MILD
            note = "Coach thinks the target outruns the roster."
        elif _is_first_chair(coach):
            text = _pick(rng, [
                "If that's what you believe, I believe it. I'll coach like it.",
                "Bigger than my read -- but you're the one who bet on me. I'm in.",
            ])
            delta = TRUST_EXPECT_DEFER
            note = "Rookie coach deferred to the GM's ambition."
        else:
            text = _pick(rng, [
                "Ambitious. ...Alright, I'll find a way. But the room needs to hear it from you too.",
                "Higher than I had it. Fine -- I'd rather aim up. Just don't move the goalposts in January.",
            ])
            delta = TRUST_EXPECT_PRAGMATIC
            note = "Coach bought into the bigger target, with caveats."
    else:
        # GM is LESS ambitious (rebuild-ward) than the coach's read.
        gap = ai - ci
        tank = chosen == "rebuild" or gap >= 2
        if _is_first_chair(coach):
            # The rookie defers to the GM who believed in him -- always.
            text = _pick(rng, [
                "You gave me this chair. I'll coach whatever season you ask me to.",
                "My read was higher -- but I'm not going to argue with the person who believed in me.",
            ])
            delta = TRUST_EXPECT_DEFER
            note = "Rookie coach deferred to the GM's patience."
        elif tank and _is_authoritarian(coach):
            text = _pick(rng, [
                "I can't coach a tank. You want to lose games on purpose, you'll need a different bench boss.",
                "Rebuild? I don't do losing seasons. Find someone who does.",
            ])
            delta = TRUST_EXPECT_TANK_REFUSAL
            note = "Coach refused a tank mandate outright."
            misaligned = True
        elif _is_win_now_ambitious(coach):
            text = _pick(rng, [
                "Lower than I'd like. ...Fine -- but I coach to win every night regardless.",
                "Not the season I pictured. I'll coach hard -- just don't ask me to lose on purpose.",
            ])
            delta = TRUST_EXPECT_MILD
            note = ("Ambitious coach pushed back on a patient mandate."
                    if tank else
                    "Ambitious coach uneasy with the lowered target.")
        elif tank and _is_developer(coach):
            text = _pick(rng, [
                "Honestly? Good. I'd rather build it right than fake it for a year.",
                "Patience is a plan. The kids get real minutes and nobody panics in November.",
            ])
            delta = TRUST_EXPECT_ALIGNED
            note = "Developer coach embraced the patient mandate."
        elif _is_loyal(coach):
            text = _pick(rng, [
                "Whatever the plan is, I'm with you. We'll make it work.",
                "Not the fun answer, but it's an honest one. I'm in.",
            ])
            delta = TRUST_EXPECT_PRAGMATIC
            note = "Loyal coach bought into the patient mandate."
        elif _is_developer(coach):
            text = _pick(rng, [
                "A step back from my read -- but patience is a plan I understand.",
                "Lower than I had it. The kids get room, at least.",
            ])
            delta = TRUST_EXPECT_PRAGMATIC
            note = "Developer coach accepted the lowered target."
        else:
            text = _pick(rng, [
                "Not what I hoped. But I'll coach the team in front of me.",
                "Lower than my read. I'll adjust -- just don't expect me to smile about it in October.",
            ])
            delta = TRUST_EXPECT_MILD if tank else -1
            note = "Coach accepted a patient mandate reluctantly."
    return text, delta, note, misaligned


# ---------------------------------------------------------------------------
# Beat: rookie playing time
# ---------------------------------------------------------------------------

def _rookie_reaction(coach, stance, expectation, rng):
    """(coach_text, trust_delta, note)."""
    y = _youngsters(coach)
    win_now = expectation in ("win_cup", "contend")
    note = ""
    if stance == "heavy":
        if _is_developer(coach):
            text = _pick(rng, [
                "That's why I'm here. Give me the kids -- I'll make players out of them.",
                "Heavy minutes, real mistakes, real growth. This is how you build a core.",
            ])
            delta = TRUST_ROOKIE_ALIGNED + 1
            note = "Developer coach thrilled with heavy rookie minutes."
        elif y >= 70:
            text = _pick(rng, [
                "Music to my ears. You don't develop a player with six minutes a night.",
                "Good. Sink-or-swim is how you find out who's real.",
            ])
            delta = TRUST_ROOKIE_ALIGNED
            note = "Coach trusts youth and welcomed heavy minutes."
        elif y <= 40:
            text = _pick(rng, [
                "You want me to win with teenagers learning on the job? That's how you ruin a kid AND a season.",
                "Heavy minutes for kids who aren't ready -- the room will eat them alive.",
            ])
            delta = TRUST_ROOKIE_STRONG
            note = "Veterans-first coach strongly resisted heavy rookie minutes."
        elif win_now and y < 70:
            text = _pick(rng, [
                "In a win-now year? You're asking me to develop and contend at the same time. Pick one.",
                "Kids don't win in April. I'll play them -- but don't blame me when it costs us points.",
            ])
            delta = TRUST_ROOKIE_FRICTION
            note = "Win-now coach resisted heavy rookie minutes."
        else:
            text = _pick(rng, [
                "Bold. I'll play them -- but I won't protect them from the consequences.",
                "Alright. They get rope. What they do with it is on them.",
            ])
            delta = -1
            note = "Coach accepted heavy rookie minutes cautiously."
    elif stance == "earned":
        if y >= 60:
            text = _pick(rng, [
                "Earn it in camp, keep it with play. That's how a room stays honest.",
                "Perfect. The kids respect it more when nobody hands them anything.",
            ])
            delta = TRUST_ROOKIE_ALIGNED
        elif y <= 35:
            text = _pick(rng, [
                "Good. Nobody's handed anything around here.",
                "Camp decides. That's the meritocracy I want.",
            ])
            delta = TRUST_ROOKIE_ALIGNED - 1
        else:
            text = _pick(rng, [
                "Fair. Ice time is earned -- that's a message the whole room understands.",
                "Standard. They earn it, they keep it.",
            ])
            delta = +2
        note = "Coach bought into earned-not-given ice time."
    elif stance == "sheltered":
        if y >= 60:
            text = _pick(rng, [
                "Protected minutes, real minutes. I can work with that.",
                "Sheltered doesn't mean soft -- it means smart. Good call.",
            ])
            delta = TRUST_ROOKIE_ALIGNED - 1
        elif win_now:
            text = _pick(rng, [
                "Fine -- as long as 'sheltered' doesn't mean passengers in April.",
                "Sheltered keeps them alive. Just don't ask me to lean on them late.",
            ])
            delta = +1
        else:
            text = _pick(rng, [
                "Third line, soft starts. They'll learn without drowning.",
                "Reasonable. Protected -- but they still have to swim a little.",
            ])
            delta = +2
        note = "Coach accepted sheltered rookie deployment."
    else:  # none
        if _is_developer(coach):
            text = _pick(rng, [
                "None? ...Alright, your call. But a kid rotting in the AHL doesn't develop either.",
                "I hope you know what you're shelving. Some of these kids are ready.",
            ])
            delta = -2
            note = "Developer coach uneasy about a full AHL year for the kids."
        elif y <= 40:
            text = _pick(rng, [
                "Good. They'll be better for the wait.",
                "Patience. The AHL exists for a reason.",
            ])
            delta = TRUST_ROOKIE_ALIGNED - 1
            note = "Veterans-first coach approved the patient path."
        else:
            text = _pick(rng, [
                "AHL year for all of them. Fine -- your prospects, your timeline.",
                "No rush. When they come up, they'll be ready.",
            ])
            delta = 0
            note = "Coach accepted no rookie minutes this year."
    return text, delta, note


# ---------------------------------------------------------------------------
# Beat: tactical approach
# ---------------------------------------------------------------------------

def _tactics_reaction(coach, preset_key, rng):
    """(coach_text, trust_delta, note)."""
    presets = _identity_presets()
    preset = presets.get(preset_key, {})
    pname = preset.get("name", preset_key)
    style = _coach_style(coach)
    want = _PRESET_STYLE.get(preset_key)
    note = ""
    if preset_key == "hybrid_transition":
        text = _pick(rng, [
            "Sound hockey. No gimmicks -- I like it.",
            "Balanced, read-based. That's how you win in May, not just October.",
        ])
        delta = TRUST_TACTICS_FIT - 1
        note = f"Coach comfortable with {pname}."
    elif want == style:
        text = _pick(rng, [
            f"That suits us. The room buys in when the system fits the skates -- {pname} fits ours.",
            "Now you're thinking like a coach. That's our game.",
        ])
        delta = TRUST_TACTICS_FIT
        note = f"{pname} fits the coach's style."
    else:
        if _is_authoritarian(coach):
            text = _pick(rng, [
                "That's not how I coach. I'll run it -- but you're asking a cover band to play jazz.",
                f"{pname}? Fine. But don't be surprised when I coach my instincts in a tie game.",
            ])
            delta = TRUST_TACTICS_MISFIT
            note = f"Authoritarian coach bristled at {pname} (style mismatch)."
        elif _is_collaborative(coach):
            text = _pick(rng, [
                "Not my first choice, but I'll make it work. I'll find our version of it.",
                "I'll adapt -- that's the job. Give me camp and I'll install it right.",
            ])
            delta = 0
            note = f"Collaborative coach accepted {pname} despite the mismatch."
        else:
            text = _pick(rng, [
                "Alright. I'll adapt -- but camp's going to be about unlearning old habits.",
                "Not natural for me, but I can coach it. It'll take October to look right.",
            ])
            delta = TRUST_TACTICS_MISFIT + 1
            note = f"Coach accepted {pname} with reservations (style mismatch)."
    return text, delta, note

# ---------------------------------------------------------------------------
# Beats: lines ownership / tactics ownership
# ---------------------------------------------------------------------------

def _lines_reaction(coach, owner, rng):
    """(coach_text, trust_delta, note)."""
    if owner == "coach":
        if _is_authoritarian(coach):
            text = _pick(rng, [
                "Good. The bench is mine -- that's the deal.",
                "Damn right. You hired a coach, let him coach the bench.",
            ])
            delta = TRUST_KEEP_HIGH_CONTROL
        elif _is_collaborative(coach):
            text = _pick(rng, [
                "I appreciate the trust. I won't waste it.",
                "Thank you. The room responds when the lines come from the bench.",
            ])
            delta = TRUST_KEEP_LOW_CONTROL
        else:
            text = _pick(rng, [
                "Good. I'll own the results.",
                "The lineup's mine -- and so is the accountability.",
            ])
            delta = TRUST_KEEP_MID
        note = "Coach keeps the lineup card."
    else:
        if _is_first_chair(coach):
            text = _pick(rng, [
                "Your team, your lines. I'll coach them hard.",
                "Fair -- you built this roster. I'll make your lines work.",
            ])
            delta = TRUST_TAKE_FIRST_CHAIR
            note = "Rookie coach deferred on line control."
        elif _is_authoritarian(coach):
            text = _pick(rng, [
                "So I'm a substitute teacher now? ...Fine. But when the power play dries up, that's your lineup, not mine.",
                "You set the lines, you own the lines. Remember that in February.",
            ])
            delta = TRUST_TAKE_HIGH_CONTROL
            note = "Authoritarian coach bristled at losing the lineup."
        elif _is_collaborative(coach):
            text = _pick(rng, [
                "Alright -- I'll make your lines work. Just keep me in the loop.",
                "Fine. Clear direction beats a tug-of-war.",
            ])
            delta = TRUST_TAKE_LOW_CONTROL
            note = "Collaborative coach accepted GM-set lines."
        else:
            text = _pick(rng, [
                "Your call. I'll coach whoever's on the sheet.",
                "Not my preference, but I'll make it work.",
            ])
            delta = TRUST_TAKE_MID
            note = "Coach ceded the lineup card reluctantly."
    return text, delta, note


def _tactics_owner_reaction(coach, owner, rng):
    """(coach_text, trust_delta, note)."""
    if owner == "coach":
        if _is_authoritarian(coach):
            text = _pick(rng, [
                "Good -- you hired a coach, let him coach.",
                "My systems, my adjustments. That's the job.",
            ])
            delta = TRUST_KEEP_HIGH_CONTROL
        elif _is_collaborative(coach):
            text = _pick(rng, [
                "Thank you. I'll keep you posted on every adjustment.",
                "I appreciate it. You'll see everything I'm thinking -- no black box.",
            ])
            delta = TRUST_KEEP_LOW_CONTROL
        else:
            text = _pick(rng, [
                "Good. That's my craft.",
                "The whiteboard's mine. I'll own what it produces.",
            ])
            delta = TRUST_KEEP_MID
        note = "Coach keeps tactical control."
    else:
        if _is_first_chair(coach):
            text = _pick(rng, [
                "I'll study it until it's mine.",
                "Your system -- I'll learn it cold and coach it like I drew it up.",
            ])
            delta = TRUST_TAKE_FIRST_CHAIR
            note = "Rookie coach deferred on tactical control."
        elif _is_authoritarian(coach):
            text = _pick(rng, [
                "You want to coach from the press box? ...I'll run your system. But systems don't adjust themselves in the second intermission.",
                "Fine. Your system. When it breaks down in March, we'll see whose adjustments save us.",
            ])
            delta = TRUST_TAKE_HIGH_CONTROL - 1
            note = "Authoritarian coach bristled at losing tactical control."
        elif _is_collaborative(coach):
            text = _pick(rng, [
                "Fine. Clear direction beats no direction.",
                "Alright -- one system, no mixed signals. I can work with that.",
            ])
            delta = TRUST_TAKE_LOW_CONTROL
            note = "Collaborative coach accepted GM-set tactics."
        else:
            text = _pick(rng, [
                "Not how I'd draw it up, but I'll execute.",
                "Your system. I'll coach it straight.",
            ])
            delta = TRUST_TAKE_MID
            note = "Coach ceded tactical control reluctantly."
    return text, delta, note


# ---------------------------------------------------------------------------
# Beat: the deployer (conditional -- GM took BOTH lines and tactics)
# ---------------------------------------------------------------------------

_DEPLOYER_OPTIONS = [
    ("reassure",
     "Reassure him",
     "You're still the voice in the room. Systems don't talk -- I need your feel for the game."),
    ("expectations",
     "Set expectations",
     "That's the job this year. Execute the plan and we'll be fine."),
    ("demand",
     "Demand buy-in",
     "I need you all in. Half-hearted doesn't win in March."),
]


def _deployer_reaction(coach, choice, rng):
    """(coach_text, trust_delta, note, deployer_note, misaligned)."""
    misaligned = False
    if choice == "reassure":
        deployer_note = ("GM reassured the coach: still the voice in the room; "
                         "deploying the GM's vision with his own feel for the game.")
        if _is_authoritarian(coach):
            text = _pick(rng, [
                "...Alright. I can coach inside a structure -- as long as it's not a cage.",
                "The voice in the room. ...Fine. Hold me to that.",
            ])
            delta = TRUST_DEPLOYER_REASSURE_HI
            note = "Authoritarian coach grudgingly accepted the deployer role."
        elif _is_collaborative(coach):
            text = _pick(rng, [
                "That means something, hearing you say it. We're good.",
                "Good. Then we're partners, not a hierarchy. I can do that.",
            ])
            delta = TRUST_DEPLOYER_REASSURE_LO
            note = "Collaborative coach embraced the deployer role."
        else:
            text = _pick(rng, [
                "Fair enough. Let's go to work.",
                "Alright. My voice, your system. Let's see what it does.",
            ])
            delta = TRUST_DEPLOYER_REASSURE_LO - 1
            note = "Coach accepted the deployer role after reassurance."
    elif choice == "expectations":
        deployer_note = ("GM set expectations: the coach deploys the plan as drawn; "
                         "execution is the job this year.")
        if _is_authoritarian(coach):
            text = _pick(rng, [
                "Understood.",
                "...Understood.",
            ])
            delta = TRUST_DEPLOYER_EXPECT_HI
            note = "Authoritarian coach went cold on the deployer role."
        else:
            text = _pick(rng, [
                "Clear is clear. I'll execute.",
                "No ambiguity -- I respect that, even if I don't love it.",
            ])
            delta = TRUST_DEPLOYER_EXPECT_LO
            note = "Coach accepted the deployer role as the job."
    else:  # demand
        deployer_note = ("GM demanded full buy-in: the coach deploys the vision "
                         "all-in, or not at all.")
        if _is_authoritarian(coach) or _is_win_now_ambitious(coach):
            text = _pick(rng, [
                "Careful. I didn't take this job to be a puppet.",
                "All in? I don't do half-measures -- but I don't take ultimatums either.",
            ])
            delta = TRUST_DEPLOYER_DEMAND_HIT
            note = "Proud coach bristled at the buy-in demand."
            misaligned = True
        elif _is_loyal(coach):
            text = _pick(rng, [
                "You have me. All in.",
                "Was never going to be half-hearted. You know that.",
            ])
            delta = TRUST_DEPLOYER_DEMAND_LOYAL
            note = "Loyal coach gave full buy-in."
        elif _is_first_chair(coach):
            text = _pick(rng, [
                "I'm here because you believed in me. I'm in.",
                "All in. You stuck your neck out for me -- I won't forget it.",
            ])
            delta = TRUST_DEPLOYER_DEMAND_LOYAL + 1
            note = "Rookie coach gave full buy-in out of loyalty."
        else:
            text = _pick(rng, [
                "Fine. All in.",
                "...Alright. You want all in, you get all in.",
            ])
            delta = -1
            note = "Coach gave buy-in without warmth."
    return text, delta, note, deployer_note, misaligned


def _closing_line(coach, aligned, rng):
    if aligned:
        pool = [
            "We've got a plan. Now let's go coach a hockey team.",
            "One plan, one room. See you at camp.",
            "Good talk. The rest happens on the ice.",
        ]
    else:
        pool = [
            "We've got your plan. I'll coach it -- but don't mistake obedience for agreement.",
            "It's your call. I'll be professional -- just don't ask me to pretend I agreed.",
            "We'll do it your way. History will judge the rest.",
        ]
    return _pick(rng, pool)


# ---------------------------------------------------------------------------
# Mandate assembly
# ---------------------------------------------------------------------------

def build_mandate(team, draft, season_label):
    """Assemble the contract's mandate dict from the finished draft.

    ``aligned`` uses the sibling's canonical rule (expectation ==
    coach_assessment); store_mandate derives the same value on completion.
    """
    ch = draft.get("choices", {})
    exp = ch.get("expectation")
    assessed = draft.get("coach_assessment")
    return {
        "season": season_label,
        "expectation": exp,
        "coach_assessment": assessed,
        "aligned": bool(exp) and exp == assessed,
        "rookie_stance": ch.get("rookie_stance"),
        "tactical_approach": ch.get("tactical_approach"),
        "lines_owner": ch.get("lines_owner"),
        "tactics_owner": ch.get("tactics_owner"),
        "deployer_notes": draft.get("deployer_note", ""),
        "meeting_done": True,
    }


def mandate_summary_lines(mandate, presets):
    """Plain-language agreement summary (closing screen + read-only view)."""
    exp = mandate.get("expectation")
    pace = expected_pace().get(exp, 0.55)
    exp_label = _EXPECT_LABELS.get(exp, (exp, ""))[0]
    assessed = mandate.get("coach_assessment")
    lines = [
        f"Season expectation: {exp_label} (~{pace:.3f} pace)",
    ]
    if assessed:
        a_label = _EXPECT_LABELS.get(assessed, (assessed, ""))[0]
        align = "aligned" if assessed == exp else "a disagreement carried into camp"
        lines.append(f"Coach's own read: {a_label} -- {align}")
    stance = mandate.get("rookie_stance")
    if stance:
        lines.append(f"Rookie ice time: {_ROOKIE_LABELS.get(stance, (stance, ''))[0]}")
    tap = mandate.get("tactical_approach")
    if tap:
        lines.append(f"Tactical approach: {presets.get(tap, {}).get('name', tap)}")
    lo = mandate.get("lines_owner")
    if lo:
        lines.append(f"Lines: {'GM sets them' if lo == 'gm' else 'Coach runs the bench'}")
    to = mandate.get("tactics_owner")
    if to:
        tactics_label = "GM's direction" if to == "gm" else "Coach's systems"
        lines.append(f"Tactics: {tactics_label}")
    if mandate.get("deployer_notes"):
        lines.append(f"Deployer note: {mandate['deployer_notes']}")
    lines.append(f"Alignment: {'Aligned' if mandate.get('aligned') else 'Misaligned -- tension carried into camp'}")
    return lines


def apply_trust_delta(coach, delta):
    """Move gm_trust (read/write the existing field), clamped 0-100."""
    try:
        cur = _num(getattr(coach, "gm_trust", 70), 70.0)
        setattr(coach, "gm_trust", int(max(0, min(100, cur + delta))))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

_BG = "#1a1d29"
_CARD = "#232738"
_PANEL = "#2a3042"
_TEXT = "#e8eaf0"
_MUTED = "#9aa0b5"
_GOLD = "#d8a93c"
_GREEN = "#6fbf73"
_RED = "#d96a6a"
_BORDER = "#3a4056"


def _font(app, size=13, weight="normal"):
    fam = getattr(app, "FONT_FAMILY", None) or "Helvetica"
    return (fam, size, weight)


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------

_STAGES = ["opening", "expectations", "rookies", "tactics",
           "lines", "tactics_own", "deployer", "closing"]


class SeasonMeetingView(ctk.CTkFrame):
    """Tier-1 full-screen season-expectations meeting with the head coach.

    Non-modal by construction (shown via app.show_screen -- the menu bar
    stays live, so the user can leave and come back). In-progress state is
    kept on team.season_meeting_draft, including the full transcript log,
    so a return visit replays the conversation exactly.
    """

    def __init__(self, parent, team=None, app=None):
        super().__init__(parent)
        if ctk is None:  # pragma: no cover
            raise RuntimeError("customtkinter is required")
        self.app = app if app is not None else parent
        self.team = team if team is not None else getattr(self.app, "user_team", None)
        self._close_screen = None  # set by show_screen()
        self._rng = random.Random()
        self._board_exp = _board_expectation(self.app)
        self.coach = _get_head_coach(self.team) if self.team is not None else None
        self._load_draft()
        self.configure(fg_color=_BG)
        if self.team is None or self.coach is None:
            self._build_degraded()
        else:
            if "coach_assessment" not in self.draft:
                self.draft["coach_assessment"] = coach_assessment(self.team, self.coach)
                self._persist()
            self._build()
            if not self.draft.get("opened"):
                if not season_meeting_is_pending(self.team):
                    # Re-opened after completion: show the sealed agreement,
                    # don't restart the conversation.
                    mandate = getattr(self.team, "season_mandate", None)
                    if isinstance(mandate, dict) and mandate.get("meeting_done"):
                        self.draft["opened"] = True
                        self.draft["stage"] = "done"
                        self._persist()
                        self._render_all()
                        return
                self._log("coach", _opening_line(
                    self.coach, self._rng, reason=_meeting_reason(self.team)))
                self.draft["opened"] = True
                self.draft["stage"] = "opening"
                self._persist()
            self._render_all()

    # ------------------------------------------------------------------
    # Draft persistence (leave-and-return)
    # ------------------------------------------------------------------

    def _load_draft(self):
        d = getattr(self.team, "season_meeting_draft", None)
        if not isinstance(d, dict):
            d = {}
        self.draft = d
        self.draft.setdefault("stage", "opening")
        self.draft.setdefault("log", [])
        self.draft.setdefault("choices", {})
        self.draft.setdefault("notes", [])
        self._persist()

    def _persist(self):
        try:
            self.team.season_meeting_draft = self.draft
        except Exception:
            pass

    def _log(self, speaker, text, trust_delta=None):
        self.draft["log"].append(
            {"speaker": speaker, "text": text, "trust": trust_delta})
        self._persist()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_degraded(self):
        """Coach-less team or missing data: a clean message, never a crash."""
        wrap = ctk.CTkFrame(self, fg_color=_BG)
        wrap.pack(fill="both", expand=True)
        if self.team is None:
            msg = "No team is loaded, so there's no meeting to hold."
        else:
            msg = ("You don't have a head coach on staff yet.\n\n"
                   "Hire one before the season meeting -- the conversation "
                   "needs someone on the other side of the desk.")
        ctk.CTkLabel(wrap, text="Season Meeting",
                     font=_font(self.app, 20, "bold"),
                     text_color=_TEXT).pack(pady=(60, 12))
        ctk.CTkLabel(wrap, text=msg, font=_font(self.app, 14),
                     text_color=_MUTED, wraplength=560,
                     justify="center").pack(pady=12)
        ctk.CTkButton(wrap, text="Back", width=160, height=40,
                      fg_color=_PANEL, hover_color=_BORDER,
                      command=self._close).pack(pady=24)

    def _build(self):
        cname = _coach_name(self.coach)
        # Header -------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color=_CARD, corner_radius=0)
        header.pack(fill="x")
        title_row = ctk.CTkFrame(header, fg_color="transparent")
        title_row.pack(fill="x", padx=20, pady=(14, 4))
        ctk.CTkLabel(title_row, text="Season Meeting",
                     font=_font(self.app, 20, "bold"),
                     text_color=_TEXT).pack(side="left")
        ctk.CTkLabel(title_row, text=f"{cname}  ·  {_coach_role(self.coach)}",
                     font=_font(self.app, 13),
                     text_color=_MUTED).pack(side="left", padx=(14, 0))
        chips = ctk.CTkFrame(header, fg_color="transparent")
        chips.pack(fill="x", padx=20, pady=(0, 12))
        for label, value in _personality_chips(self.coach):
            chip = ctk.CTkFrame(chips, fg_color=_PANEL, corner_radius=12)
            chip.pack(side="left", padx=(0, 8))
            ctk.CTkLabel(chip, text=f"{label}: {value}",
                         font=_font(self.app, 11),
                         text_color=_MUTED).pack(padx=10, pady=4)

        # Body ---------------------------------------------------------
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=12)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)

        convo = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=10)
        convo.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        convo.grid_rowconfigure(0, weight=1)
        convo.grid_columnconfigure(0, weight=1)
        self.transcript = ctk.CTkTextbox(convo, fg_color=_CARD,
                                         text_color=_TEXT,
                                         font=_font(self.app, 13),
                                         wrap="word", state="disabled",
                                         border_width=0)
        self.transcript.grid(row=0, column=0, sticky="nsew",
                             padx=14, pady=14)
        self.transcript.tag_config("speaker_c",
                                   foreground=_GOLD)
        self.transcript.tag_config("speaker_g",
                                   foreground=_TEXT)
        self.transcript.tag_config("trust",
                                   foreground=_MUTED)

        side = ctk.CTkFrame(body, fg_color=_CARD, corner_radius=10,
                            width=300)
        side.grid(row=0, column=1, sticky="ns")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="The agreement so far",
                     font=_font(self.app, 14, "bold"),
                     text_color=_TEXT).pack(anchor="w", padx=16, pady=(14, 8))
        self._agree_vars = {}
        for key in ("expectation", "assessment", "rookies",
                    "approach", "lines", "tactics", "alignment"):
            var = ctk.StringVar(value="")
            self._agree_vars[key] = var
            ctk.CTkLabel(side, textvariable=var,
                         font=_font(self.app, 12),
                         text_color=_MUTED, wraplength=268,
                         justify="left",
                         anchor="w").pack(anchor="w", padx=16, pady=3)
        ctk.CTkLabel(side, text="Leave anytime -- the meeting waits for you.",
                     font=_font(self.app, 11), text_color=_MUTED,
                     wraplength=268, justify="left").pack(
                         anchor="w", padx=16, pady=(14, 8))

        # Prompt + options (fixed area; only the transcript scrolls) ---
        self.prompt_bar = ctk.CTkFrame(self, fg_color=_CARD, corner_radius=0)
        self.prompt_bar.pack(fill="x", padx=20, pady=(0, 20))
        self.prompt_label = ctk.CTkLabel(
            self.prompt_bar, text="", font=_font(self.app, 13, "bold"),
            text_color=_TEXT, wraplength=1100, justify="left", anchor="w")
        self.prompt_label.pack(anchor="w", padx=20, pady=(12, 6))
        self.options_frame = ctk.CTkFrame(self.prompt_bar,
                                          fg_color="transparent")
        self.options_frame.pack(fill="x", padx=20, pady=(0, 14))

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_all(self):
        self._render_transcript()
        self._refresh_agreement()
        self._render_stage()

    def _render_transcript(self):
        box = self.transcript
        box.configure(state="normal")
        box.delete("1.0", "end")
        for entry in self.draft.get("log", []):
            sp = entry.get("speaker")
            text = entry.get("text", "")
            if sp == "coach":
                box.insert("end", "COACH  ", "speaker_c")
                box.insert("end", text + "\n")
                trust = entry.get("trust")
                if trust:
                    box.insert("end", _trust_text(trust) + "\n", "trust")
            elif sp == "gm":
                box.insert("end", "YOU  ", "speaker_g")
                box.insert("end", text + "\n")
            else:
                box.insert("end", text + "\n", "trust")
            box.insert("end", "\n")
        box.configure(state="disabled")
        box.see("end")

    def _refresh_agreement(self):
        ch = self.draft.get("choices", {})
        pace = expected_pace()
        v = self._agree_vars
        exp = ch.get("expectation")
        v["expectation"].set(
            f"Expectation: {_EXPECT_LABELS[exp][0]} (~{pace.get(exp, 0.55):.3f})"
            if exp else "Expectation: —")
        assessed = self.draft.get("coach_assessment")
        v["assessment"].set(
            f"Coach's read: {_EXPECT_LABELS[assessed][0]}"
            if assessed else "Coach's read: —")
        stance = ch.get("rookie_stance")
        v["rookies"].set(
            f"Rookies: {_ROOKIE_LABELS[stance][0]}" if stance else "Rookies: —")
        tap = ch.get("tactical_approach")
        presets = _identity_presets()
        v["approach"].set(
            f"System: {presets.get(tap, {}).get('name', tap)}"
            if tap else "System: —")
        lo = ch.get("lines_owner")
        v["lines"].set(
            "Lines: " + ("GM sets them" if lo == "gm" else "Coach's bench")
            if lo else "Lines: —")
        to = ch.get("tactics_owner")
        v["tactics"].set(
            "Tactics: " + ("GM's direction" if to == "gm" else "Coach's systems")
            if to else "Tactics: —")
        notes = self.draft.get("notes", [])
        v["alignment"].set(
            ("Alignment: MISALIGNED -- " + notes[-1]) if self.draft.get("misaligned")
            else ("Notes: " + notes[-1] if notes else "Alignment: —"))

    def _clear_options(self):
        for child in self.options_frame.winfo_children():
            child.destroy()

    def _option_button(self, label, command):
        btn = ctk.CTkButton(
            self.options_frame, text=label, command=command,
            font=_font(self.app, 12), anchor="w",
            fg_color=_PANEL, hover_color=_BORDER, text_color=_TEXT,
            height=48)
        btn.pack(fill="x", pady=4)
        return btn

    # ------------------------------------------------------------------
    # Stage machine
    # ------------------------------------------------------------------

    def _render_stage(self):
        stage = self.draft.get("stage", "opening")
        if self.draft.get("stage") == "done":
            self._render_done()
            return
        render = getattr(self, f"_stage_{stage}", None)
        if callable(render):
            render()
        else:  # unknown stage: fail forward to closing, never strand
            self._advance_to("closing")

    def _advance_to(self, stage):
        self.draft["stage"] = stage
        prompt = self._stage_prompt(stage)
        if prompt:
            self._log("gm", prompt)
        self._persist()
        self._render_all()

    def _stage_prompt(self, stage):
        prompts = {
            "expectations": ("Here's how I see this season. "
                             "Tell me straight -- can you coach it?"),
            "rookies": "Next: the kids. How much rope do they get?",
            "tactics": "How do you want this team to play?",
            "lines": "The lineup card. Who writes it?",
            "tactics_own": "And the systems -- the forecheck, the special teams?",
            "deployer": ("One more thing -- I need to say it plainly. With the "
                         "lines AND the tactics both coming from my office, "
                         "you're deploying someone else's vision this year."),
        }
        return prompts.get(stage)

    # -- individual stages -------------------------------------------

    def _stage_opening(self):
        self.prompt_label.configure(text="The meeting is yours to run.")
        self._clear_options()
        self._option_button("Sit down and talk.",
                            lambda: self._choose("opening", "begin"))

    def _stage_expectations(self):
        self.prompt_label.configure(
            text="Set the season expectation. The menu is built from your "
                 "roster's strength and the board's mandate.")
        self._clear_options()
        pace = expected_pace()
        for rung in expectation_options(self.team, self._board_exp):
            label, desc = _EXPECT_LABELS[rung]
            self._option_button(
                f"{label} -- {desc}  (~{pace.get(rung, 0.55):.3f} pace)",
                lambda r=rung: self._choose("expectations", r))

    def _stage_rookies(self):
        self.prompt_label.configure(text="Set the rookie playing-time stance.")
        self._clear_options()
        for key in ("heavy", "earned", "sheltered", "none"):
            label, desc = _ROOKIE_LABELS[key]
            self._option_button(f"{label} -- {desc}",
                                lambda k=key: self._choose("rookies", k))

    def _stage_tactics(self):
        self.prompt_label.configure(
            text="Pick the tactical identity. The coach reacts to how well it "
                 "fits the way he coaches.")
        self._clear_options()
        for key, preset in _identity_presets().items():
            name = preset.get("name", key)
            tagline = preset.get("tagline", "")
            label = f"{name} -- {tagline}" if tagline else name
            self._option_button(label,
                                lambda k=key: self._choose("tactics", k))

    def _stage_lines(self):
        self.prompt_label.configure(text="Who owns the lineup card?")
        self._clear_options()
        self._option_button("I set the lines -- you deploy them.",
                            lambda: self._choose("lines", "gm"))
        self._option_button("The bench is yours.",
                            lambda: self._choose("lines", "coach"))

    def _stage_tactics_own(self):
        self.prompt_label.configure(text="Who owns the systems?")
        self._clear_options()
        self._option_button("I set the tactical direction.",
                            lambda: self._choose("tactics_own", "gm"))
        self._option_button("Your systems, your call.",
                            lambda: self._choose("tactics_own", "coach"))

    def _stage_deployer(self):
        self.prompt_label.configure(
            text="He's deploying your vision this year. Address it directly -- "
                 "this beat is mandatory.")
        self._clear_options()
        for key, label, full in _DEPLOYER_OPTIONS:
            self._option_button(f"{label}: \"{full}\"",
                                lambda k=key: self._choose("deployer", k))

    def _stage_closing(self):
        mandate = build_mandate(self.team, self.draft,
                                _season_label(self.app))
        if not self.draft.get("closing_logged"):
            self._log("coach", _closing_line(
                self.coach, not self.draft.get("misaligned", False),
                self._rng))
            self.draft["closing_logged"] = True
            self._persist()
            self._render_transcript()
        presets = _identity_presets()
        summary = "\n".join("• " + ln
                            for ln in mandate_summary_lines(mandate, presets))
        self.prompt_label.configure(
            text="The agreement, as it stands. Seal it and the season begins.")
        self._clear_options()
        ctk.CTkLabel(self.options_frame, text=summary,
                     font=_font(self.app, 12), text_color=_MUTED,
                     justify="left", anchor="w",
                     wraplength=1100).pack(anchor="w", pady=(0, 10))
        self._option_button("Seal the agreement.",
                            lambda: self._seal(mandate))

    def _render_done(self):
        mandate = getattr(self.team, "season_mandate", None) or {}
        presets = _identity_presets()
        summary = "\n".join("• " + ln
                            for ln in mandate_summary_lines(mandate, presets))
        self.prompt_label.configure(text="Meeting complete -- sealed agreement:")
        self._clear_options()
        ctk.CTkLabel(self.options_frame, text=summary or "No mandate on file.",
                     font=_font(self.app, 12), text_color=_MUTED,
                     justify="left", anchor="w",
                     wraplength=1100).pack(anchor="w", pady=(0, 10))
        self._option_button("Back to the dashboard.", self._close)

    # ------------------------------------------------------------------
    # Choices
    # ------------------------------------------------------------------

    def _gm_line(self, stage, key):
        if stage == "opening":
            return "Let's talk about the season."
        if stage == "expectations":
            return f"Here's my call: {_EXPECT_LABELS[key][0].lower()}."
        if stage == "rookies":
            return f"On the kids: {_ROOKIE_LABELS[key][0].lower()}."
        if stage == "tactics":
            name = _identity_presets().get(key, {}).get("name", key)
            return f"I want us playing {name}."
        if stage == "lines":
            return ("I set the lines -- you deploy them."
                    if key == "gm" else "The bench is yours.")
        if stage == "tactics_own":
            return ("I set the tactical direction."
                    if key == "gm" else "Your systems, your call.")
        if stage == "deployer":
            full = dict((k, t) for k, _l, t in _DEPLOYER_OPTIONS).get(key, "")
            return full
        return ""

    def _choose(self, stage, key):
        """GM picks -> coach reacts -> visible consequence -> next beat."""
        if stage != self.draft.get("stage"):
            return  # stale click; ignore
        gm_line = self._gm_line(stage, key)
        if gm_line:
            self._log("gm", gm_line)

        text, delta, note, misaligned = "", 0, "", False
        deployer_note = ""
        if stage == "opening":
            nxt = "expectations"
        elif stage == "expectations":
            assessed = self.draft.get("coach_assessment") or coach_assessment(
                self.team, self.coach)
            self.draft["coach_assessment"] = assessed
            self.draft["choices"]["expectation"] = key
            text, delta, note, misaligned = _expectation_reaction(
                self.coach, key, assessed, self._rng)
            nxt = "rookies"
        elif stage == "rookies":
            self.draft["choices"]["rookie_stance"] = key
            exp = self.draft["choices"].get("expectation", "playoffs")
            text, delta, note = _rookie_reaction(self.coach, key, exp,
                                                self._rng)
            nxt = "tactics"
        elif stage == "tactics":
            self.draft["choices"]["tactical_approach"] = key
            text, delta, note = _tactics_reaction(self.coach, key, self._rng)
            nxt = "lines"
        elif stage == "lines":
            self.draft["choices"]["lines_owner"] = key
            text, delta, note = _lines_reaction(self.coach, key, self._rng)
            nxt = "tactics_own"
        elif stage == "tactics_own":
            self.draft["choices"]["tactics_owner"] = key
            text, delta, note = _tactics_owner_reaction(self.coach, key,
                                                       self._rng)
            ch = self.draft["choices"]
            if ch.get("lines_owner") == "gm" and ch.get("tactics_owner") == "gm":
                nxt = "deployer"
            else:
                nxt = "closing"
        elif stage == "deployer":
            (text, delta, note,
             deployer_note, misaligned) = _deployer_reaction(
                 self.coach, key, self._rng)
            self.draft["deployer_note"] = deployer_note
            nxt = "closing"
        else:
            return

        if delta:
            apply_trust_delta(self.coach, delta)
        if note:
            self.draft["notes"].append(note)
        if misaligned:
            self.draft["misaligned"] = True
        if text:
            self._log("coach", text, delta if delta else None)
        self._advance_to(nxt)

    # Test hook: drive a beat programmatically (used by qa_coach_meeting.py).
    def debug_choose(self, stage, key):
        self._choose(stage, key)

    # ------------------------------------------------------------------
    # Sealing
    # ------------------------------------------------------------------

    def _seal(self, mandate):
        ok = _finalize_meeting(self.team, mandate)
        self.draft = {"stage": "done", "log": self.draft.get("log", []),
                      "choices": {}, "notes": []}
        self._log("sys", "Agreement sealed." if ok
                  else "Agreement recorded (finalize reported a problem).")
        self._render_all()
        # The conversation is over; drop the in-progress draft entirely.
        try:
            if hasattr(self.team, "season_meeting_draft"):
                delattr(self.team, "season_meeting_draft")
        except Exception:
            pass

    def _close(self):
        closer = getattr(self, "_close_screen", None)
        if callable(closer):
            try:
                closer()
                return
            except Exception:
                pass
        try:
            self.app.show_dashboard()
        except Exception:
            pass


def _season_label(app):
    try:
        gm = getattr(app, "game_manager", None)
        d = getattr(gm, "current_date", None)
        if d is not None and hasattr(d, "year"):
            return int(d.year)
        league = getattr(gm, "league", None) or getattr(app, "league", None)
        sy = getattr(league, "season_year", None)
        if sy:
            return int(sy)
    except Exception:
        pass
    return "upcoming"


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def open_season_meeting(app):
    """Open the season meeting (lazy-import-safe).

    The advance-blocker wires its "Open Season Meeting" action here.
    """
    team = getattr(app, "user_team", None)
    if team is None:
        return None
    show = getattr(app, "show_screen", None)
    if callable(show):
        try:
            return show("season_meeting", "Season Meeting",
                        SeasonMeetingView, team)
        except Exception:
            pass
    # Fallback: standalone window if the app has no show_screen.
    try:
        top = ctk.CTkToplevel(app)
        top.title("Season Meeting")
        top.geometry("1280x860")
        view = SeasonMeetingView(top, team=team, app=app)
        view.pack(fill="both", expand=True)
        view._close_screen = top.destroy
        return view
    except Exception:
        return None


def build_season_meeting_banner(parent, app):
    """Persistent dashboard entry point while the meeting is pending.

    Returns a banner widget, or None when there is nothing pending.
    dashboard_home calls this (guarded) on every dashboard build.
    """
    try:
        import tkinter as tk
    except Exception:
        return None
    try:
        team = getattr(app, "user_team", None)
        if team is None or not season_meeting_is_pending(team):
            return None
        coach = _get_head_coach(team)
        cname = _coach_name(coach) if coach is not None else "your head coach"
        frame = tk.Frame(parent, bg="#3d2f10",
                         highlightbackground="#d8a93c", highlightthickness=1)
        inner = tk.Frame(frame, bg="#3d2f10")
        inner.pack(fill="x", padx=14, pady=10)
        tk.Label(inner, text="SEASON MEETING PENDING",
                 font=("Segoe UI", 11, "bold"),
                 fg="#f0c75e", bg="#3d2f10").pack(side="left")
        tk.Label(inner,
                 text=(f"{cname} is waiting to talk about the season. "
                       "The day can't advance until you sit down."),
                 font=("Segoe UI", 11), fg="#e8eaf0",
                 bg="#3d2f10", wraplength=700,
                 justify="left").pack(side="left", padx=(12, 0))
        tk.Button(inner, text="Open Season Meeting",
                  font=("Segoe UI", 11, "bold"),
                  fg="#1a1d29", bg="#d8a93c", activebackground="#f0c75e",
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=lambda: open_season_meeting(app)).pack(side="right")
        return frame
    except Exception:
        return None
