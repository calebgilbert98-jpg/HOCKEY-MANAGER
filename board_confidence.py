"""
Board confidence and job security (roadmap F5).

The board's confidence in the manager, fed by:
- Results vs expectation (win pace vs the board's preseason target)
- Dressing-room climate (F3: morale cascades affect results)
- Media climate (narrative pressure)

States: SECURE -> STABLE -> UNDER_PRESSURE -> SACKED.
"""

from enum import Enum


class JobSecurity(Enum):
    SECURE = "secure"               # 80-100
    STABLE = "stable"               # 60-79
    UNDER_PRESSURE = "under_pressure"  # 40-59
    SACK_RACE = "sack_race"         # 20-39
    SACKED = "sacked"               # 0-19


# Expectation -> required point pace (points per game)
EXPECTATION_PACE = {
    'cup_contender': 1.35,   # ~110 pts
    'playoff_team': 1.15,    # ~95 pts
    'bubble_team': 1.00,     # ~82 pts
    'rebuilding': 0.80,      # ~65 pts
}


class BoardConfidence:
    """Tracks the board's faith in the manager."""

    def __init__(self, expectation='bubble_team'):
        self.expectation = expectation
        self.confidence = 70.0  # start stable
        self.history = []  # (games, confidence) snapshots

    def update(self, games_played, points, avg_morale=5.0,
               media_pressure=0.0):
        """Recalculate confidence.

        games_played: int. points: int. avg_morale: 1-10 (F3).
        media_pressure: 0-1 (0 = calm, 1 = firestorm).
        """
        if games_played == 0:
            return self.confidence
        pace = points / games_played
        target = EXPECTATION_PACE.get(self.expectation, 1.0)

        # Results vs expectation (the big driver)
        pace_delta = pace - target
        # +/- 20 confidence for +/- 0.3 pace delta
        result_shift = max(-20, min(20, pace_delta * 65))

        # Dressing room: low morale erodes the board's faith
        morale_shift = (avg_morale - 5.0) * 2.0

        # Media: firestorms cost confidence
        media_shift = -media_pressure * 10.0

        self.confidence = max(0, min(100,
            self.confidence * 0.7 +  # inertia: the board doesn't panic weekly
            (70 + result_shift + morale_shift + media_shift) * 0.3))
        self.history.append((games_played, round(self.confidence, 1)))
        return self.confidence

    def security_state(self):
        c = self.confidence
        if c >= 80: return JobSecurity.SECURE
        if c >= 60: return JobSecurity.STABLE
        if c >= 40: return JobSecurity.UNDER_PRESSURE
        if c >= 20: return JobSecurity.SACK_RACE
        return JobSecurity.SACKED

    def board_message(self):
        """What the board tells you at this confidence level."""
        state = self.security_state()
        msgs = {
            JobSecurity.SECURE: "The board is delighted with your work.",
            JobSecurity.STABLE: "The board is satisfied with progress.",
            JobSecurity.UNDER_PRESSURE:
                "The board expects improvement. Your job is under review.",
            JobSecurity.SACK_RACE:
                "The board is losing patience. Results must turn now.",
            JobSecurity.SACKED:
                "The board has relieved you of your duties.",
        }
        return msgs[state]
