"""AI GM identity: personality, job security, and risk appetite.

Pure logic module (no tkinter) so it can be unit-tested headless.

Every AI club is run by its actual General Manager staff member. This module
reads that GM's attributes, personality, reputation, and tenure, combines them
with the club's board confidence (job security) and recent success, and
produces a risk appetite that drives how the AI behaves:

- A GM on the hot seat (low board confidence, high expectations) may get
  brash: win-now trades, aggressive free-agent overpays, rushing prospects.
  But the hot seat does NOT turn every GM into Peter Chiarelli: a patient
  builder trusts his vision and barely bends, while an aggressive,
  controversial GM panics. `pressure_response` (0..1) captures how much the
  seat bends each GM's behavior.
- The leash comes from the owner, not a stat line: when confidence sinks,
  the owner may issue an ultimatum -- win 3 of the next 5 games or you're
  done. ONLY while that warning is active does the board veto
  franchise-altering moves, so a GM never gets leashed (or fired) without
  the owner saying so first.
- A tenured GM who just won the Cup gets conservative: patient, developmental,
  protects assets.
- Personality modulates everything: a "win-now aggressor" archetype behaves
  differently from a "patient builder" even with identical records.

User and AI share every mechanic: the same identity model could describe a
human player's tendencies; the AI simply acts on its own.
"""

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Board expectations keyed like manager_career.EXPECTATIONS (kept local so
# this module stays dependency-free).
EXPECTATION_KEYS = ("win_cup", "contend", "playoffs", "rebuild")

# Points-pace (points pct) the board expects for each expectation level.
EXPECTED_PACE = {
    "win_cup": 0.650,
    "contend": 0.600,
    "playoffs": 0.550,
    "rebuild": 0.450,
}

# Win-now drive per GM ambition tag (game_classes.Staff.ambition).
AMBITION_DRIVE = {
    "stanley_cup": 1.00,
    "climb": 0.70,
    "hometown": 0.50,
    "lifer": 0.35,
    "developer": 0.25,
}

POTENTIAL_ORDER = ["F", "D", "C", "B-", "B", "B+", "A-", "A", "A+"]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _attr100(v, default: int = 65) -> float:
    """Staff attribute on the 1-100 scale -> 0..1."""
    try:
        return _clamp01((float(v) - 1.0) / 99.0)
    except (TypeError, ValueError):
        return _clamp01((default - 1.0) / 99.0)


# ---------------------------------------------------------------------------
# GM identity
# ---------------------------------------------------------------------------

@dataclass
class GMIdentity:
    """Who the AI GM is: personality, reputation, tenure, archetype."""
    team_name: str
    gm_name: str
    age: int = 45
    experience_years: int = 10
    tenure_years: int = 2          # years_with_team

    # Personality axes, 0..1 (derived from Staff attributes)
    aggression: float = 0.5        # brashness / win-now drive
    patience: float = 0.5          # developmental, long-view
    loyalty: float = 0.5           # sticks with his people / club
    adaptability: float = 0.5      # flexible vs stubborn

    reputation: int = 50           # 0-100 career standing
    archetype: str = "Pragmatist"

    # 0..1: how much a hot seat bends this GM's behavior. 0 = trusts his
    # vision completely (a patient builder on the hot seat keeps building);
    # 1 = full Chiarelli panic mode (mortgages the future to save his job).
    pressure_response: float = 0.5

    def describe(self) -> str:
        return (f"{self.gm_name} ({self.archetype}) -- tenure {self.tenure_years}y, "
                f"rep {self.reputation}, aggression {self.aggression:.2f}, "
                f"patience {self.patience:.2f}")


def _ambition_drive(ambition) -> float:
    try:
        return AMBITION_DRIVE.get(str(ambition or "").strip().lower(), 0.5)
    except Exception:
        return 0.5


def gm_identity_from_staff(team_name: str, gm_staff) -> GMIdentity:
    """Build a GMIdentity from the team's GM Staff member.

    gm_staff may be None (old saves / missing staff): falls back to a
    middle-of-the-road generated identity so the AI still behaves sanely.
    """
    if gm_staff is None:
        return GMIdentity(
            team_name=team_name,
            gm_name="Interim GM",
            age=50, experience_years=12, tenure_years=1,
            aggression=0.5, patience=0.5, loyalty=0.5, adaptability=0.5,
            reputation=50, archetype="Pragmatist",
        )

    g = lambda name, d=65: _attr100(getattr(gm_staff, name, d), d)
    drive = _ambition_drive(getattr(gm_staff, "ambition", "climb"))

    determination = g("determination")
    controversy = g("controversy")
    adapt = g("adaptability")
    youngsters = g("working_with_youngsters")
    development = g("player_development")
    man_mgmt = g("man_management")
    leadership = g("leadership")
    control = g("control_need")

    # Brashness: driven, win-now ambition, makes waves, stubborn (low
    # adaptability), authoritarian control need.
    aggression = _clamp01(
        0.35 * determination + 0.30 * drive + 0.15 * controversy
        + 0.10 * (1.0 - adapt) + 0.10 * control
    )
    # Patience: develops youth, low controversy, developer/lifer ambition.
    patience = _clamp01(
        0.35 * youngsters + 0.30 * development + 0.15 * (1.0 - controversy)
        + 0.20 * (1.0 - drive)
    )
    # Loyalty: sticks with his club and his people.
    tenure = int(getattr(gm_staff, "years_with_team", 0) or 0)
    loyalty = _clamp01(
        0.40 * min(1.0, tenure / 6.0) + 0.25 * man_mgmt + 0.20 * leadership
        + 0.15 * (1.0 - controversy)
    )

    try:
        reputation = int(getattr(gm_staff, "reputation", 50) or 50)
    except (TypeError, ValueError):
        reputation = 50
    reputation = max(0, min(100, reputation))
    # career_reputation, when present, is the deeper track record.
    try:
        career_rep = int(getattr(gm_staff, "career_reputation", 0) or 0)
        if career_rep > 0:
            reputation = int(round(0.6 * reputation + 0.4 * max(0, min(100, career_rep))))
    except (TypeError, ValueError):
        pass

    try:
        age = int(getattr(gm_staff, "age", 45) or 45)
    except (TypeError, ValueError):
        age = 45
    try:
        experience = int(getattr(gm_staff, "experience", 10) or 10)
    except (TypeError, ValueError):
        experience = 10

    first = str(getattr(gm_staff, "first_name", "") or "")
    last = str(getattr(gm_staff, "last_name", "") or "")
    gm_name = (first + " " + last).strip() or "Interim GM"

    # How the hot seat bends THIS gm: aggressive, controversial GMs panic
    # and go brash; patient builders trust their vision and barely move.
    # Calibrated so a Win-Now Aggressor lands ~0.7, a Patient Builder ~0.1,
    # a Pragmatist ~0.4.
    pressure_response = _clamp01(
        0.70 * aggression - 0.60 * patience + 0.25 * controversy + 0.25
    )

    # Archetype: the strongest readable signal.
    if aggression >= 0.65 and drive >= 0.7:
        archetype = "Win-Now Aggressor"
    elif patience >= 0.65 and drive <= 0.4:
        archetype = "Patient Builder"
    elif loyalty >= 0.65 and tenure >= 4:
        archetype = "Franchise Stabilizer"
    elif controversy >= 0.65 and aggression >= 0.55:
        archetype = "Wild Card"
    elif aggression >= 0.6:
        archetype = "Aggressive Trader"
    elif patience >= 0.55:
        archetype = "Developer"
    else:
        archetype = "Pragmatist"

    return GMIdentity(
        team_name=team_name, gm_name=gm_name, age=age,
        experience_years=experience, tenure_years=tenure,
        aggression=aggression, patience=patience, loyalty=loyalty,
        adaptability=adapt, reputation=reputation, archetype=archetype,
        pressure_response=pressure_response,
    )


# ---------------------------------------------------------------------------
# Job security
# ---------------------------------------------------------------------------

@dataclass
class GMJobSecurity:
    """Board confidence for one AI club."""
    team_name: str
    expectation: str = "playoffs"   # win_cup | contend | playoffs | rebuild
    confidence: float = 60.0        # 0-100
    hot_seat: bool = False
    tenured_winner: bool = False
    # The owner's ultimatum: win warning_wins_needed of the next
    # warning_games_left games or you're done. ONLY while a warning is
    # active does the board leash the GM -- no franchise-altering moves,
    # so he can't torch the future on his way out. A warning is never
    # issued silently: it always comes from the owner first.
    owner_warning: bool = False
    warning_wins_needed: int = 0
    warning_games_left: int = 0
    warning_start_gp: int = 0      # team GP snapshot at issuance
    warning_start_wins: int = 0    # team wins snapshot at issuance
    # Set when a warning's terms weren't met. The manager installs an
    # interim GM and resets the seat; the identity layer doesn't hire.
    gm_fired: bool = False
    last_cup_season: Optional[int] = None

    def describe(self) -> str:
        if self.owner_warning:
            seat = (f"OWNER WARNING (need {self.warning_wins_needed} wins in "
                    f"{self.warning_games_left} games)")
        elif self.hot_seat:
            seat = "HOT SEAT"
        elif self.tenured_winner:
            seat = "tenured winner"
        else:
            seat = "stable"
        return (f"{self.team_name}: board expects {self.expectation}, "
                f"confidence {self.confidence:.0f} ({seat})")


def expectation_from_strength(avg_overall_100: float) -> str:
    """Board expectation from roster strength (mirrors career auto_expectation)."""
    try:
        s = float(avg_overall_100)
    except (TypeError, ValueError):
        s = 55.0
    if s >= 72:
        return "win_cup"
    if s >= 62:
        return "contend"
    if s >= 52:
        return "playoffs"
    return "rebuild"


def update_job_security(sec: GMJobSecurity, identity: GMIdentity,
                        team, last_cup_champ_name: Optional[str],
                        season_year: int) -> GMJobSecurity:
    """Weekly board-confidence update from the club's record vs expectation.

    Pure function of (record, expectation): wins raise confidence, losing
    against a contend-or-better expectation erodes it. A recent Cup plus
    tenure buys patience; a rebuild board is patient by definition.
    """
    try:
        w = int(getattr(team, "wins", 0) or 0)
        l = int(getattr(team, "losses", 0) or 0)
        otl = int(getattr(team, "ot_losses", 0) or 0)
    except (TypeError, ValueError):
        w = l = otl = 0
    gp = w + l + otl
    if gp <= 0:
        return sec  # no games yet: no information

    pace = (2.0 * w + otl) / (2.0 * gp)
    expected = EXPECTED_PACE.get(sec.expectation, 0.55)

    # Drift toward deserved confidence: each week moves ~15% of the gap.
    deserved = 50.0 + 90.0 * (pace - expected)
    deserved = max(0.0, min(100.0, deserved))
    sec.confidence += 0.15 * (deserved - sec.confidence)
    sec.confidence = max(0.0, min(100.0, sec.confidence))

    # Cup memory: defending champion's GM gets a long leash.
    is_champ = bool(last_cup_champ_name) and getattr(team, "team_name", "") == last_cup_champ_name
    if is_champ:
        sec.last_cup_season = season_year
        sec.confidence = max(sec.confidence, 75.0)

    sec.hot_seat = sec.confidence < 35.0 and sec.expectation != "rebuild"
    # The owner's ultimatum: win 3 of the next 5 or you're done. Issued
    # only when confidence has truly cratered -- never silently, and
    # never for a GM who's merely bad: bad GMs get leash.
    # Rebuild boards are patient by definition; tenured winners are safe.
    if sec.owner_warning:
        _gp_since = gp - sec.warning_start_gp
        _wins_since = w - sec.warning_start_wins
        _games_left = sec.warning_games_left - _gp_since
        _need = sec.warning_wins_needed - _wins_since
        if _wins_since >= sec.warning_wins_needed:
            # Survived: the owner backs off, confidence rebounds.
            sec.owner_warning = False
            sec.warning_wins_needed = 0
            sec.warning_games_left = 0
            sec.confidence = min(100.0, sec.confidence + 12.0)
        elif _games_left <= 0 or _need > _games_left:
            # Failed -- or mathematically eliminated early. You're done.
            sec.owner_warning = False
            sec.gm_fired = True
    elif (sec.confidence < 15.0 and sec.expectation != "rebuild"
            and not sec.tenured_winner and not sec.gm_fired):
        sec.owner_warning = True
        sec.warning_wins_needed = 3
        sec.warning_games_left = 5
        sec.warning_start_gp = gp
        sec.warning_start_wins = w
    sec.hot_seat = sec.confidence < 35.0 and sec.expectation != "rebuild"
    sec.tenured_winner = (
        sec.last_cup_season is not None
        and (season_year - sec.last_cup_season) <= 2
        and identity.tenure_years >= 2
        and sec.confidence >= 60.0
    )
    return sec


# ---------------------------------------------------------------------------
# Risk appetite
# ---------------------------------------------------------------------------

def compute_risk_appetite(identity: GMIdentity, sec: GMJobSecurity) -> float:
    """0.0-1.0: how much variance the GM will accept in pursuit of wins.

    - Personality sets the base: aggressive GMs gamble more.
    - Hot seat: the brashness is scaled by THIS gm's pressure_response --
      a safe .500 finish gets him fired anyway, so high-variance swings
      are rational, but only a GM wired for panic actually takes them.
      A patient builder trusts his vision and barely moves.
    - Owner warning: while the ultimatum is active the board vetoes big
      gambles, so realized risk is capped no matter how desperate he feels.    - Tenured winner: conservative -- don't fix what just won.
    - Reputation: high-rep GMs trust their process a touch more.
    """
    base = 0.15 + 0.70 * identity.aggression
    if sec.hot_seat:
        base += 0.25 * identity.pressure_response
    if sec.owner_warning:
        base = min(base, 0.45)
    if sec.tenured_winner:
        base -= 0.20
    base -= (identity.reputation - 50) / 500.0
    return _clamp01(round(base, 3))


def signing_urgency(identity: GMIdentity, sec: GMJobSecurity) -> float:
    """0.0-1.0: how eagerly the GM signs prospects to ELCs.

    Patient developers lock up talent early; a hot-seat GM rushes help
    only to the extent his personality bends under pressure -- a builder
    who trusts his vision doesn't rush anyone.
    """
    u = 0.30 + 0.40 * identity.patience + 0.20 * identity.aggression
    if sec.hot_seat:
        u += 0.15 * identity.pressure_response
    if sec.tenured_winner:
        u -= 0.10
    return _clamp01(round(u, 3))
