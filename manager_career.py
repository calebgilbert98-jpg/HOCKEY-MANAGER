"""Football Manager-style career systems for Puck Dynasty.

Pure logic module (no tkinter) so it can be unit-tested headless.
Covers: board confidence & job security, player happiness & private chats,
press conferences, team talks, opposition scout reports, training schedules,
youth intake, and manager reputation.

All state is plain data (dicts/lists/str/int/float) so CareerState can be
pickled into save files via to_dict()/from_dict().
"""

import random
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Board & job security
# ---------------------------------------------------------------------------

EXPECTATIONS = {
    "win_cup": {
        "label": "Win the Stanley Cup",
        "description": "The board expects a championship. Anything less is failure.",
        "min_confidence_for_sack": 15,
    },
    "contend": {
        "label": "Contend (reach Conference Final)",
        "description": "The board expects a deep playoff run.",
        "min_confidence_for_sack": 10,
    },
    "playoffs": {
        "label": "Make the playoffs",
        "description": "The board expects postseason hockey.",
        "min_confidence_for_sack": 5,
    },
    "rebuild": {
        "label": "Rebuild and develop youth",
        "description": "The board is patient. Develop young players; results matter less.",
        "min_confidence_for_sack": 0,
    },
}


class BoardSystem:
    """Tracks board confidence and job security."""

    def __init__(self):
        self.expectation: Optional[str] = None
        self.confidence: int = 60  # 0-100
        self.season_wins: int = 0
        self.season_losses: int = 0
        self.season_otl: int = 0
        self.last_review: str = ""
        self.warnings_given: int = 0
        self.sacked: bool = False

    # -- setup ------------------------------------------------------------
    def set_expectation(self, key: str):
        if key in EXPECTATIONS:
            self.expectation = key

    def auto_expectation(self, team_strength: float):
        """Pick a sensible expectation from team strength (0-100)."""
        if team_strength >= 72:
            self.set_expectation("win_cup")
        elif team_strength >= 62:
            self.set_expectation("contend")
        elif team_strength >= 52:
            self.set_expectation("playoffs")
        else:
            self.set_expectation("rebuild")

    # -- results ----------------------------------------------------------
    def record_result(self, won: bool, went_ot: bool, was_favorite: bool,
                      is_playoff: bool = False) -> int:
        """Update confidence after a game. Returns the delta applied."""
        if is_playoff:
            delta = 6 if won else -8
        elif won:
            delta = 4 if was_favorite else 7  # bonus for upset wins
        else:
            delta = -6 if was_favorite else -3  # harsher for upset losses
            if went_ot:
                delta += 2  # at least took a point
        self.confidence = max(0, min(100, self.confidence + delta))
        if won:
            self.season_wins += 1
        elif went_ot:
            self.season_otl += 1
        else:
            self.season_losses += 1
        self._check_sack()
        return delta

    def record_big_event(self, kind: str) -> int:
        """Off-ice events: 'good_trade', 'bad_trade', 'star_signing',
        'star_leaves', 'scandal'."""
        deltas = {
            "good_trade": 4, "bad_trade": -5, "star_signing": 6,
            "star_leaves": -7, "scandal": -10,
        }
        delta = deltas.get(kind, 0)
        self.confidence = max(0, min(100, self.confidence + delta))
        self._check_sack()
        return delta

    def _check_sack(self):
        if self.confidence <= 0 and not self.sacked:
            self.sacked = True

    # -- reviews ----------------------------------------------------------
    @property
    def job_status(self) -> str:
        if self.sacked:
            return "Sacked"
        if self.confidence >= 70:
            return "Secure"
        if self.confidence >= 40:
            return "Stable"
        if self.confidence >= 20:
            return "Under Pressure"
        return "In Danger"

    def monthly_review(self, points_pct: float) -> Tuple[str, str]:
        """Return (headline, body) for the monthly board email."""
        exp = EXPECTATIONS.get(self.expectation or "playoffs")
        if points_pct >= 0.65:
            tone, d = "delighted", 6
        elif points_pct >= 0.55:
            tone, d = "satisfied", 3
        elif points_pct >= 0.45:
            tone, d = "concerned", -4
        else:
            tone, d = "alarmed", -8
        self.confidence = max(0, min(100, self.confidence + d))
        self._check_sack()
        headline = f"Board review: {tone.capitalize()} with progress"
        body = (
            f"The board is {tone} with the team's direction. "
            f"Expectation: {exp['label']}. Current points percentage: {points_pct:.1%}. "
            f"Board confidence is now {self.confidence}/100 ({self.job_status})."
        )
        self.last_review = body
        return headline, body

    def season_review(self, made_playoffs: bool, playoff_rounds_won: int,
                      won_cup: bool) -> Tuple[str, str, int]:
        """End-of-season review. Returns (headline, body, confidence_delta)."""
        exp = self.expectation or "playoffs"
        met = (
            (exp == "win_cup" and won_cup)
            or (exp == "contend" and playoff_rounds_won >= 2)
            or (exp == "playoffs" and made_playoffs)
            or (exp == "rebuild")
        )
        delta = 15 if met else -20
        if won_cup:
            delta = max(delta, 20)
        self.confidence = max(0, min(100, self.confidence + delta))
        self._check_sack()
        headline = ("Board delighted: expectations met"
                    if met else "Board disappointed: expectations missed")
        body = (
            f"Season review complete. Expectation was '{EXPECTATIONS[exp]['label']}'. "
            f"{'You met it. ' if met else 'You fell short. '}"
            f"Board confidence is now {self.confidence}/100 ({self.job_status})."
        )
        # Reset season counters
        self.season_wins = self.season_losses = self.season_otl = 0
        self.warnings_given = 0
        return headline, body, delta

    # -- persistence ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "expectation": self.expectation,
            "confidence": self.confidence,
            "season_wins": self.season_wins,
            "season_losses": self.season_losses,
            "season_otl": self.season_otl,
            "last_review": self.last_review,
            "warnings_given": self.warnings_given,
            "sacked": self.sacked,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BoardSystem":
        b = cls()
        for k, v in (data or {}).items():
            if hasattr(b, k):
                setattr(b, k, v)
        return b


# ---------------------------------------------------------------------------
# Player happiness, squad status & private chats
# ---------------------------------------------------------------------------

SQUAD_STATUSES = [
    "Star Player", "Key Player", "Regular Starter",
    "Rotation", "Prospect", "Surplus",
]

# Expected share of team games played for each status
STATUS_EXPECTED_SHARE = {
    "Star Player": 0.95,
    "Key Player": 0.85,
    "Regular Starter": 0.70,
    "Rotation": 0.40,
    "Prospect": 0.15,
    "Surplus": 0.05,
}

PERSONALITIES = [
    "Driven", "Professional", "Laid-back", "Volatile", "Loyal", "Ambitious",
]


def get_player_personality(player) -> str:
    """Stable personality derived from player id (no extra storage needed)."""
    pid = getattr(player, "id", 0) or 0
    return PERSONALITIES[pid % len(PERSONALITIES)]


def morale_label(morale: int) -> str:
    if morale >= 9:
        return "Superb"
    if morale >= 7:
        return "Good"
    if morale >= 5:
        return "Okay"
    if morale >= 3:
        return "Poor"
    return "Abysmal"


def happiness_label(happiness: int) -> str:
    if happiness >= 80:
        return "Delighted"
    if happiness >= 60:
        return "Happy"
    if happiness >= 40:
        return "Content"
    if happiness >= 25:
        return "Unhappy"
    return "Very unhappy"


def update_player_happiness(player, team_games_played: int) -> List[str]:
    """Weekly happiness update. Returns noteworthy event strings."""
    events = []
    gp = getattr(player, "games_played", 0) or 0
    status = getattr(player, "squad_status", "Rotation") or "Rotation"
    expected = STATUS_EXPECTED_SHARE.get(status, 0.4)
    happiness = getattr(player, "happiness", 70) or 70
    concern = getattr(player, "playing_time_concern", 0) or 0

    if team_games_played > 0:
        actual_share = gp / team_games_played
        shortfall = expected - actual_share
        if shortfall > 0.25:
            concern = min(100, concern + 12)
            happiness = max(0, happiness - 8)
        elif shortfall > 0.10:
            concern = min(100, concern + 5)
            happiness = max(0, happiness - 3)
        elif shortfall < -0.05:
            # Playing more than expected: small boost
            concern = max(0, concern - 8)
            happiness = min(100, happiness + 2)

    # Personality drift
    personality = get_player_personality(player)
    if personality == "Volatile":
        happiness = max(0, min(100, happiness + random.randint(-6, 4)))
    elif personality == "Laid-back":
        happiness = max(0, min(100, happiness + random.randint(-2, 2)))
    elif personality == "Loyal":
        concern = max(0, concern - 2)

    # Promise tracking
    promise = getattr(player, "promise_made", "") or ""
    if promise == "more_icetime" and team_games_played > 0:
        recent_share = gp / team_games_played
        if recent_share >= expected * 0.8:
            promise = ""
            happiness = min(100, happiness + 10)
            events.append(f"{player.first_name} {player.last_name} is pleased you kept your playing-time promise.")

    # Transfer request trigger
    if happiness < 25 and concern > 70 and not getattr(player, "transfer_requested", False):
        player.transfer_requested = True
        events.append(f"TRANSFER REQUEST: {player.first_name} {player.last_name} has asked to leave the club.")

    # Morale follows happiness loosely
    morale = getattr(player, "morale", 7) or 7
    if happiness >= 70 and morale < 10:
        player.morale = min(10, morale + 1)
    elif happiness < 30 and morale > 1:
        player.morale = max(1, morale - 1)

    player.happiness = happiness
    player.playing_time_concern = concern
    player.promise_made = promise
    return events


def check_squad_concerns(team) -> List[Tuple]:
    """Return [(player, concern_text)] for players needing attention."""
    concerns = []
    for p in getattr(team, "roster", []) or []:
        happiness = getattr(p, "happiness", 70) or 70
        concern = getattr(p, "playing_time_concern", 0) or 0
        if getattr(p, "transfer_requested", False):
            concerns.append((p, f"{p.first_name} {p.last_name} has requested a transfer and is refusing to back down."))
        elif concern >= 60:
            concerns.append((p, f"{p.first_name} {p.last_name} ({getattr(p, 'squad_status', 'Rotation')}) is concerned about his lack of playing time."))
        elif happiness <= 30:
            concerns.append((p, f"{p.first_name} {p.last_name} is unhappy. His agent hints he may seek a move."))
    return concerns


CHAT_ACTIONS = {
    "praise": {
        "label": "Praise his recent form",
        "desc": "Boosts morale and happiness. Works best when the player is performing.",
    },
    "criticize": {
        "label": "Criticize his performances",
        "desc": "Risky: may motivate driven players but anger others.",
    },
    "promise_icetime": {
        "label": "Promise more playing time",
        "desc": "Calms playing-time concerns, but you must deliver.",
    },
    "reassure_future": {
        "label": "Reassure him about his future",
        "desc": "Small happiness boost. Safe option.",
    },
    "discipline": {
        "label": "Discipline for poor attitude",
        "desc": "For very unhappy players. May backfire with volatile personalities.",
    },
    "discuss_transfer": {
        "label": "Discuss his transfer request",
        "desc": "Try to convince him to stay.",
    },
}


def chat_with_player(player, action: str) -> Tuple[str, Dict[str, int]]:
    """Apply a private chat action. Returns (result_text, effects_dict)."""
    personality = get_player_personality(player)
    happiness = getattr(player, "happiness", 70) or 70
    morale = getattr(player, "morale", 7) or 7
    name = f"{player.first_name} {player.last_name}"
    effects = {"happiness": 0, "morale": 0, "concern": 0}

    if action == "praise":
        dh, dm = 8, 1
        if personality == "Driven":
            dh, dm = 12, 2
        text = f"{name} appreciated the praise and looks motivated."
    elif action == "criticize":
        if personality in ("Driven", "Professional"):
            dh, dm = -4, 1
            text = f"{name} took the criticism on the chin and vows to respond on the ice."
        else:
            dh, dm = -12, -2
            text = f"{name} reacted badly to the criticism. His agent called to complain."
    elif action == "promise_icetime":
        player.promise_made = "more_icetime"
        dh, dm, dc = 10, 1, -25
        effects["concern"] = dc
        text = f"You promised {name} more ice time. He'll be watching your line selections."
        player.happiness = max(0, min(100, happiness + dh))
        player.morale = max(1, min(10, morale + dm))
        player.playing_time_concern = max(0, (getattr(player, "playing_time_concern", 0) or 0) + dc)
        return text, {"happiness": dh, "morale": dm, "concern": dc}
    elif action == "reassure_future":
        dh, dm = 5, 1
        text = f"{name} seemed reassured by your words."
    elif action == "discipline":
        if personality == "Volatile":
            dh, dm = -15, -2
            text = f"{name} exploded at the discipline. This could get ugly."
        else:
            dh, dm, dc = -5, 0, -15
            effects["concern"] = dc
            text = f"{name} accepted the discipline sullenly."
    elif action == "discuss_transfer":
        if personality in ("Loyal", "Professional") and happiness >= 35:
            player.transfer_requested = False
            dh, dm = 10, 1
            text = f"Your talk worked — {name} has withdrawn his transfer request."
        else:
            dh, dm = -8, -1
            text = f"{name} isn't listening. He still wants out."
    else:
        return "Nothing was said.", effects

    effects["happiness"] = dh
    effects["morale"] = dm
    player.happiness = max(0, min(100, happiness + dh))
    player.morale = max(1, min(10, morale + dm))
    if effects["concern"]:
        player.playing_time_concern = max(0, (getattr(player, "playing_time_concern", 0) or 0) + effects["concern"])
    return text, effects


# ---------------------------------------------------------------------------
# Press conferences
# ---------------------------------------------------------------------------

# Each answer: (label, tone, morale_effect, board_effect, fan_effect, media_reaction)
PREMATCH_QUESTIONS = [
    {
        "id": "form",
        "ask": "Your team's form has been {form_word} lately. Are you confident going into this one?",
        "answers": [
            ("Very confident — we'll win", "confident", 1, 0, 2,
             "The press loves the confidence. Players feel backed."),
            ("We take it one game at a time", "calm", 0, 1, 0,
             "A measured response. The board appreciates the professionalism."),
            ("We need to be much better", "honest", -1, 0, -1,
             "Honest but gloomy. Some players took it personally."),
        ],
    },
    {
        "id": "opponent",
        "ask": "{opp} are {opp_word} this season. How do you rate them?",
        "answers": [
            ("They're a top side, we respect them", "respectful", 0, 1, 1,
             "Classy. No bulletin-board material for the opponent."),
            ("We're better than them, simple as that", "confident", 1, -1, 2,
             "Bold! The fans love it, but the board winces at the arrogance."),
            ("No comment on the opposition", "defensive", 0, 0, -1,
             "Terse. Journalists grumble about your media manner."),
        ],
    },
    {
        "id": "pressure",
        "ask": "There's pressure on you after recent results. Is your job under threat?",
        "answers": [
            ("I have the full backing of the board", "calm", 0, 2, 1,
             "The board liked hearing that. Whether it's true is another matter."),
            ("I don't listen to the noise", "defensive", 1, -1, 0,
             "Defiant. The dressing room respects the siege mentality."),
            ("Every manager is under pressure", "honest", 0, 0, 0,
             "A shrug. Nobody learned anything."),
        ],
    },
    {
        "id": "injuries",
        "ask": "Any team news? Are the injured players close to returning?",
        "answers": [
            ("The squad is in great shape", "confident", 1, 0, 1,
             "Positive vibes around the camp."),
            ("We're managing a few knocks", "honest", 0, 0, 0,
             "Straightforward injury update."),
            ("I'd rather not discuss injuries", "defensive", -1, 0, -1,
             "Cagey. Fans speculate the worst."),
        ],
    },
    {
        "id": "youth",
        "ask": "Will we see any young players given a chance soon?",
        "answers": [
            ("If they're good enough, they'll play", "confident", 1, 1, 2,
             "The academy prospects are buzzing."),
            ("They need to earn it in practice", "calm", 0, 1, 0,
             "Sensible. Nobody is upset."),
            ("We're not a development charity", "defensive", -2, 0, -2,
             "Harsh. Young players were hurt by that."),
        ],
    },
]

POSTMATCH_QUESTIONS_WIN = [
    {
        "id": "verdict",
        "ask": "A {score} win over {opp}. Your verdict?",
        "answers": [
            ("The players were magnificent", "confident", 2, 1, 2,
             "The dressing room is bouncing after that praise."),
            ("A good win, but we can improve", "calm", 0, 2, 1,
             "The board loves the standards you're setting."),
            ("We got lucky today", "honest", -1, -1, -1,
             "Nobody likes hearing the win dismissed."),
        ],
    },
    {
        "id": "star",
        "ask": "{star} was superb today. Is he your most important player?",
        "answers": [
            ("He's world class, no doubt", "confident", 2, 0, 2,
             "{star} is thrilled. Teammates slightly less so."),
            ("It's a team game", "calm", 1, 1, 0,
             "Diplomatic. The squad appreciates it."),
            ("Let's not get carried away", "defensive", -1, 0, -1,
             "{star} looked stung by that."),
        ],
    },
]

POSTMATCH_QUESTIONS_LOSS = [
    {
        "id": "verdict",
        "ask": "A {score} defeat to {opp}. What went wrong?",
        "answers": [
            ("I take full responsibility", "honest", 1, 2, 1,
             "The players respect a manager who shields them."),
            ("The players didn't show up", "defensive", -2, -1, -1,
             "The dressing room is furious at being thrown under the bus."),
            ("The officials were poor", "defensive", 0, -2, 1,
             "Fans agree, but the board hates excuses."),
        ],
    },
    {
        "id": "future",
        "ask": "That's {n} defeats now. Are you worried?",
        "answers": [
            ("We'll turn it around, I promise", "confident", 1, 0, 1,
             "Fighting talk. The fans needed to hear it."),
            ("We need to work harder", "calm", 0, 1, 0,
             "Steady. Nobody panics."),
            ("Ask me after the next game", "defensive", -1, -1, -1,
             "Snappy. The vultures are circling."),
        ],
    },
]

POSTMATCH_QUESTIONS_DRAW = [
    {
        "id": "verdict",
        "ask": "A {score} draw with {opp} after overtime. Fair result?",
        "answers": [
            ("We deserved more", "confident", 1, 0, 1,
             "The players feel their effort was recognized."),
            ("A point is a point", "calm", 0, 1, 0,
             "Pragmatic. The board nods along."),
            ("Two points dropped", "honest", -1, 0, -1,
             "Gloomy. The mood dips."),
        ],
    },
]


def _fill(template: str, ctx: dict) -> str:
    try:
        return template.format(**ctx)
    except KeyError:
        return template


def build_prematch_presser(user_team, opponent, ctx: dict) -> List[dict]:
    """Return 3 question dicts: {id, journalist, question, answers[...]}."""
    journalists = ["Sarah Chen (Hockey Night)", "Mike Ross (The Athletic)",
                   "Dave Tremblay (TSN)", "Lisa Park (Sportsnet)"]
    picked = random.sample(PREMATCH_QUESTIONS, min(3, len(PREMATCH_QUESTIONS)))
    out = []
    for i, q in enumerate(picked):
        answers = []
        for label, tone, me, be, fe, reaction in q["answers"]:
            answers.append({
                "label": label, "tone": tone,
                "morale_effect": me, "board_effect": be, "fan_effect": fe,
                "reaction": _fill(reaction, ctx),
            })
        out.append({
            "id": q["id"],
            "journalist": journalists[i % len(journalists)],
            "question": _fill(q["ask"], ctx),
            "answers": answers,
        })
    return out


def build_postmatch_presser(user_team, opponent, won: bool, drew: bool,
                            score: str, star_name: str, ctx: dict) -> List[dict]:
    journalists = ["Sarah Chen (Hockey Night)", "Mike Ross (The Athletic)",
                   "Dave Tremblay (TSN)"]
    bank = POSTMATCH_QUESTIONS_DRAW if drew else (
        POSTMATCH_QUESTIONS_WIN if won else POSTMATCH_QUESTIONS_LOSS)
    full_ctx = dict(ctx)
    full_ctx.update({"score": score, "star": star_name,
                     "opp": getattr(opponent, "team_name", "them")})
    out = []
    for i, q in enumerate(bank):
        answers = []
        for label, tone, me, be, fe, reaction in q["answers"]:
            answers.append({
                "label": label, "tone": tone,
                "morale_effect": me, "board_effect": be, "fan_effect": fe,
                "reaction": _fill(_fill(reaction, full_ctx), full_ctx),
            })
        out.append({
            "id": q["id"],
            "journalist": journalists[i % len(journalists)],
            "question": _fill(q["ask"], full_ctx),
            "answers": answers,
        })
    return out


# ---------------------------------------------------------------------------
# Team talks
# ---------------------------------------------------------------------------

TEAM_TALK_OPTIONS = {
    "prematch": [
        {"id": "passionate_fav", "label": "Passionate: 'Go out and dominate!'",
         "tone": "passionate",
         "text": "You're the better team — prove it from the first shift!",
         "best_when": "favorite", "boost": 1.04, "morale": 1},
        {"id": "calm_fav", "label": "Calm: 'Stick to the game plan'",
         "tone": "calm",
         "text": "Trust the system, stay patient, the chances will come.",
         "best_when": "favorite", "boost": 1.02, "morale": 0},
        {"id": "siege", "label": "Siege mentality: 'Nobody believes in us'",
         "tone": "passionate",
         "text": "Nobody gives us a chance tonight. Let's shock them all!",
         "best_when": "underdog", "boost": 1.05, "morale": 1},
        {"id": "relaxed_dog", "label": "Relaxed: 'No pressure, enjoy it'",
         "tone": "calm",
         "text": "No pressure tonight — go out, work hard, enjoy your hockey.",
         "best_when": "underdog", "boost": 1.01, "morale": 1},
        {"id": "demanding", "label": "Demanding: 'I expect a response'",
         "tone": "demanding",
         "text": "Last game wasn't good enough. I expect a response tonight.",
         "best_when": "after_loss", "boost": 1.03, "morale": 0},
    ],
    "intermission": [
        {"id": "encourage_win", "label": "Encouraged: 'More of the same!'",
         "tone": "encouraging",
         "text": "Excellent period — more of the same and this game is ours.",
         "best_when": "winning", "boost": 1.03, "morale": 1},
        {"id": "demand_win", "label": "Demanding: 'Don't sit back!'",
         "tone": "demanding",
         "text": "The lead means nothing if we sit back. Keep pushing!",
         "best_when": "winning", "boost": 1.02, "morale": 0},
        {"id": "rally", "label": "Passionate: 'We can turn this around!'",
         "tone": "passionate",
         "text": "One goal changes everything. Win the next period!",
         "best_when": "losing", "boost": 1.04, "morale": 1},
        {"id": "calm_lose", "label": "Calm: 'Stick with it'",
         "tone": "calm",
         "text": "Stay calm, stick to the plan. The game is still there for us.",
         "best_when": "losing", "boost": 1.02, "morale": 0},
        {"id": "tied_push", "label": "Encouraging: 'The next goal wins it'",
         "tone": "encouraging",
         "text": "Dead even. Who wants it more? Go take it!",
         "best_when": "tied", "boost": 1.03, "morale": 1},
    ],
    "postmatch": [
        {"id": "praise_win", "label": "Praise the performance",
         "tone": "encouraging",
         "text": "Outstanding — that's the standard now.",
         "best_when": "won", "boost": 1.0, "morale": 2},
        {"id": "grounded_win", "label": "Keep them grounded",
         "tone": "calm",
         "text": "Good win, but the next game starts 0-0.",
         "best_when": "won", "boost": 1.0, "morale": 1},
        {"id": "angry_loss", "label": "Angry: 'Not good enough!'",
         "tone": "demanding",
         "text": "That was nowhere near good enough. Think about it tonight.",
         "best_when": "lost", "boost": 1.0, "morale": -2},
        {"id": "support_loss", "label": "Supportive: 'Heads up'",
         "tone": "encouraging",
         "text": "Heads up. We win together, we lose together.",
         "best_when": "lost", "boost": 1.0, "morale": 1},
    ],
}


def get_team_talk_options(when: str, context: dict) -> List[dict]:
    """Return talk options annotated with a 'fit' hint for the UI."""
    opts = TEAM_TALK_OPTIONS.get(when, [])
    situation = context.get("situation", "")
    out = []
    for o in opts:
        fit = "good" if o["best_when"] == situation else "neutral"
        # Demanding talks after poor runs risk backlash; passionate as favorite can fall flat
        if o["tone"] == "demanding" and context.get("losing_streak", 0) >= 3:
            fit = "risky"
        out.append({**o, "fit": fit})
    return out


def apply_team_talk(team, option: dict, context: dict) -> Tuple[str, float]:
    """Apply a team talk. Returns (reaction_text, sim_boost_multiplier)."""
    boost = float(option.get("boost", 1.0))
    morale_delta = int(option.get("morale", 0))
    fit = option.get("fit", "neutral")
    if fit == "risky":
        # Backlash: half the squad tunes out
        morale_delta = -1
        boost = 0.98
        reaction = "Your harsh words fell flat — several players stared at the floor."
    elif fit == "good":
        morale_delta += 1
        boost = min(1.08, boost + 0.01)
        reaction = "The room responded — sticks banging, everyone locked in."
    else:
        reaction = "The players nodded along."

    for p in getattr(team, "roster", []) or []:
        m = getattr(p, "morale", 7) or 7
        # Leaders and big-game players respond more
        leadership = getattr(p, "leadership", 10) or 10
        adj = morale_delta + (1 if leadership >= 15 and morale_delta > 0 else 0)
        p.morale = max(1, min(10, m + adj))

    return reaction, boost


# ---------------------------------------------------------------------------
# Opposition scout report
# ---------------------------------------------------------------------------

def _team_avg(players, attr: str) -> float:
    vals = [getattr(p, attr, 10) or 10 for p in players
            if getattr(p, "primary_position", None) is not None
            and str(getattr(p, "primary_position", "")).upper() != "GOALIE"]
    return sum(vals) / len(vals) if vals else 10.0


def _player_rating(p) -> float:
    attrs = ["skating", "shooting", "passing", "defense", "physicality",
             "goaltending", "offensive_awareness", "defensive_awareness"]
    vals = [getattr(p, a, 10) or 10 for a in attrs if hasattr(p, a)]
    return sum(vals) / len(vals) if vals else 10.0


def generate_opposition_report(opponent, standings: dict) -> dict:
    """Build a pre-match scout report on the opponent."""
    roster = [p for p in (getattr(opponent, "roster", []) or [])
              if not getattr(p, "is_injured", False)]
    skaters = [p for p in roster
               if str(getattr(p, "primary_position", "")).upper() != "GOALIE"]
    goalies = [p for p in roster
               if str(getattr(p, "primary_position", "")).upper() == "GOALIE"]

    offense = _team_avg(skaters, "shooting")
    defense = _team_avg(skaters, "defense")
    physical = _team_avg(skaters, "physicality")
    skating = _team_avg(skaters, "skating")
    goaltending = (_team_avg(goalies, "goaltending") if goalies else 10.0)

    strengths, weaknesses = [], []
    facets = [("Attack", offense, "their forwards finish chances clinically"),
              ("Defense", defense, "they defend the slot very well"),
              ("Physicality", physical, "they outhit and wear teams down"),
              ("Skating", skating, "their transition game is dangerous"),
              ("Goaltending", goaltending, "their goalie steals games")]
    for name, val, desc in sorted(facets, key=lambda f: f[1], reverse=True)[:2]:
        strengths.append(f"{name} ({val:.1f}): {desc}.")
    for name, val, desc in sorted(facets, key=lambda f: f[1])[:2]:
        weaknesses.append(f"{name} ({val:.1f}): exploitable — {desc} is lacking.")

    key_players = sorted(skaters, key=_player_rating, reverse=True)[:3]
    key_names = [f"{p.first_name} {p.last_name} ({_player_rating(p):.1f})"
                 for p in key_players]

    rec = standings.get(getattr(opponent, "team_name", ""), {}) if standings else {}
    record = f"{rec.get('W', '?')}-{rec.get('L', '?')}-{rec.get('OTL', '?')}" if rec else "unknown"

    advice = []
    if offense >= 14:
        advice.append("Contain their top line — double-shift your shutdown pair against them.")
    if goaltending < 11:
        advice.append("Their goaltending is shaky: shoot early and crash the net for rebounds.")
    if physical < 11:
        advice.append("They don't like physical hockey — finish every check.")
    if skating >= 14:
        advice.append("Beware their rush: keep a forward high and protect the blue line.")
    if not advice:
        advice.append("No glaring weakness — win the special-teams battle.")

    danger = "High" if (offense + goaltending) / 2 >= 14 else (
        "Medium" if (offense + goaltending) / 2 >= 11.5 else "Low")

    return {
        "team": getattr(opponent, "team_name", "Opponent"),
        "record": record,
        "danger_level": danger,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "key_players": key_names,
        "tactical_advice": advice,
    }


# ---------------------------------------------------------------------------
# Training schedules
# ---------------------------------------------------------------------------

TRAINING_INTENSITIES = ["Light", "Normal", "Intense"]
TRAINING_FOCI = ["Balanced", "Attacking", "Defensive", "Physical", "Tactical", "Recovery"]
TRAINING_UNITS = ["Forwards", "Defense", "Goalies"]

TRAINING_PRESETS = {
    "Balanced Week": {"Forwards": ("Normal", "Balanced"),
                      "Defense": ("Normal", "Balanced"),
                      "Goalies": ("Normal", "Balanced")},
    "Attacking Blitz": {"Forwards": ("Intense", "Attacking"),
                        "Defense": ("Normal", "Attacking"),
                        "Goalies": ("Normal", "Balanced")},
    "Defensive Lockdown": {"Forwards": ("Normal", "Defensive"),
                           "Defense": ("Intense", "Defensive"),
                           "Goalies": ("Normal", "Balanced")},
    "Physical Camp": {"Forwards": ("Intense", "Physical"),
                      "Defense": ("Intense", "Physical"),
                      "Goalies": ("Normal", "Recovery")},
    "Tactical Week": {"Forwards": ("Normal", "Tactical"),
                      "Defense": ("Normal", "Tactical"),
                      "Goalies": ("Light", "Tactical")},
    "Recovery Week": {"Forwards": ("Light", "Recovery"),
                      "Defense": ("Light", "Recovery"),
                      "Goalies": ("Light", "Recovery")},
}


class TrainingSystem:
    """Weekly training schedule per unit."""

    def __init__(self):
        self.schedule: Dict[str, Tuple[str, str]] = {
            u: ("Normal", "Balanced") for u in TRAINING_UNITS
        }
        self.preset_name: str = "Balanced Week"

    def set_preset(self, name: str):
        if name in TRAINING_PRESETS:
            self.schedule = {u: v for u, v in TRAINING_PRESETS[name].items()}
            self.preset_name = name

    def set_unit(self, unit: str, intensity: str, focus: str):
        if unit in TRAINING_UNITS and intensity in TRAINING_INTENSITIES \
                and focus in TRAINING_FOCI:
            self.schedule[unit] = (intensity, focus)
            self.preset_name = "Custom"

    def weekly_effects(self) -> dict:
        """Aggregate effects across units."""
        dev_mult = 1.0
        injury_mult = 1.0
        morale_delta = 0
        notes = []
        for unit, (intensity, focus) in self.schedule.items():
            if intensity == "Intense":
                dev_mult *= 1.18
                injury_mult *= 1.35
                morale_delta -= 1
            elif intensity == "Light":
                dev_mult *= 0.85
                injury_mult *= 0.7
                morale_delta += 1
            if focus == "Recovery":
                injury_mult *= 0.8
                morale_delta += 1
                notes.append(f"{unit}: recovery focus — players feel fresh.")
            elif focus == "Physical":
                injury_mult *= 1.15
                notes.append(f"{unit}: heavy contact work — bruises expected.")
            elif focus == "Attacking":
                notes.append(f"{unit}: attacking patterns sharpened.")
            elif focus == "Defensive":
                notes.append(f"{unit}: defensive structure drilled.")
            elif focus == "Tactical":
                notes.append(f"{unit}: video + systems work.")
        return {
            "development_mult": round(dev_mult, 2),
            "injury_risk_mult": round(injury_mult, 2),
            "morale_delta": morale_delta,
            "notes": notes,
        }

    def to_dict(self) -> dict:
        return {"schedule": {u: list(v) for u, v in self.schedule.items()},
                "preset_name": self.preset_name}

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingSystem":
        t = cls()
        sched = (data or {}).get("schedule", {})
        for u in TRAINING_UNITS:
            if u in sched and len(sched[u]) == 2:
                t.schedule[u] = (sched[u][0], sched[u][1])
        t.preset_name = (data or {}).get("preset_name", "Balanced Week")
        return t


# ---------------------------------------------------------------------------
# Youth intake
# ---------------------------------------------------------------------------

def generate_youth_intake(team_name: str, count: int = 4) -> List[dict]:
    """Generate raw prospect data for the annual youth intake.

    Returns plain dicts; the GUI converts them to Player objects.
    """
    first_names = ["Liam", "Noah", "Lucas", "Ethan", "Mason", "Logan", "Owen",
                   "Nathan", "Gabriel", "Félix", "Alexis", "Thomas", "Jake",
                   "Cole", "Brady", "Dylan", "Ryan", "Kyle", "Tyler", "Zach"]
    last_names = ["Tremblay", "Gagnon", "Roy", "Côté", "Bouchard", "Gauthier",
                  "Morin", "Lavoie", "Fortin", "Leblanc", "Bergeron", "Pelletier",
                  "Smith", "Johnson", "Brown", "Wilson", "Clark", "Miller",
                  "Novak", "Lindqvist", "Virtanen", "Kuznetsov", "Dube", "Stützle"]
    positions = ["C", "LW", "RW", "LW", "RW", "C", "D", "D", "D", "G"]
    prospects = []
    for _ in range(count):
        age = random.randint(17, 19)
        potential = random.randint(12, 19)
        overall = max(5, potential - random.randint(4, 8))
        pos = random.choice(positions)
        prospects.append({
            "first_name": random.choice(first_names),
            "last_name": random.choice(last_names),
            "age": age,
            "position": pos,
            "overall": overall,
            "potential": potential,
            "personality": random.choice(PERSONALITIES),
            "scout_note": random.choice([
                "Silky hands and great vision.",
                "A relentless forechecker.",
                "Big shot from the point.",
                "Calm beyond his years in net.",
                "Elite skating, raw offensively.",
                "High hockey IQ, needs strength.",
            ]),
        })
    return prospects


# ---------------------------------------------------------------------------
# Manager reputation
# ---------------------------------------------------------------------------

REPUTATION_LEVELS = [
    (95, "Legend"), (80, "Elite"), (60, "Renowned"),
    (40, "Respected"), (20, "Promising"), (0, "Unknown"),
]


class ManagerProfile:
    def __init__(self):
        self.reputation: int = 30
        self.career_wins: int = 0
        self.career_losses: int = 0
        self.career_otl: int = 0
        self.titles_won: int = 0
        self.playoff_appearances: int = 0
        self.seasons_managed: int = 0

    @property
    def level(self) -> str:
        for threshold, name in REPUTATION_LEVELS:
            if self.reputation >= threshold:
                return name
        return "Unknown"

    def record_result(self, won: bool, went_ot: bool, is_playoff: bool):
        if won:
            self.career_wins += 1
            self.reputation = min(100, self.reputation + (2 if is_playoff else 1))
        elif went_ot:
            self.career_otl += 1
        else:
            self.career_losses += 1
            self.reputation = max(0, self.reputation - 1)

    def record_title(self, title: str):
        self.titles_won += 1
        self.reputation = min(100, self.reputation + 15)

    def to_dict(self) -> dict:
        return {
            "reputation": self.reputation, "career_wins": self.career_wins,
            "career_losses": self.career_losses, "career_otl": self.career_otl,
            "titles_won": self.titles_won,
            "playoff_appearances": self.playoff_appearances,
            "seasons_managed": self.seasons_managed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ManagerProfile":
        m = cls()
        for k, v in (data or {}).items():
            if hasattr(m, k):
                setattr(m, k, v)
        return m


# ---------------------------------------------------------------------------
# CareerState container
# ---------------------------------------------------------------------------

class CareerState:
    """All FM-style career state for one manager career."""

    def __init__(self):
        self.board = BoardSystem()
        self.training = TrainingSystem()
        self.profile = ManagerProfile()
        self.press_history: List[dict] = []   # {date, type, summary}
        self.youth_history: List[dict] = []   # past intakes
        self.last_intake_year: int = 0
        self.intake_preview_sent: int = 0
        self.prompts_enabled: bool = True
        self.career_start_date: str = ""

    def to_dict(self) -> dict:
        return {
            "board": self.board.to_dict(),
            "training": self.training.to_dict(),
            "profile": self.profile.to_dict(),
            "press_history": self.press_history[-50:],
            "youth_history": self.youth_history[-10:],
            "last_intake_year": self.last_intake_year,
            "intake_preview_sent": self.intake_preview_sent,
            "prompts_enabled": self.prompts_enabled,
            "career_start_date": self.career_start_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CareerState":
        c = cls()
        data = data or {}
        c.board = BoardSystem.from_dict(data.get("board", {}))
        c.training = TrainingSystem.from_dict(data.get("training", {}))
        c.profile = ManagerProfile.from_dict(data.get("profile", {}))
        c.press_history = data.get("press_history", [])
        c.youth_history = data.get("youth_history", [])
        c.last_intake_year = data.get("last_intake_year", 0)
        c.intake_preview_sent = data.get("intake_preview_sent", 0)
        c.prompts_enabled = data.get("prompts_enabled", True)
        c.career_start_date = data.get("career_start_date", "")
        return c
