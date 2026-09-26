"""
EHM roster importer for Puck Dynasty.

Reads a pre-built Eastside Hockey Manager database (``database.db`` as shipped
with community roster packs such as xECK29x's Premier Pivot Rosters) and
converts its clubs/players into a Puck Dynasty ``League``.

The exact physical schema of EHM's SQLite database is not publicly documented,
so this module does NOT hard-code table/column names.  Instead it:

  1. Opens the file read-only and discovers the real schema via
     ``sqlite_master`` / ``PRAGMA table_info``.
  2. Fuzzy-matches tables and columns against prioritized candidate names and
     synonym sets (built from the EHM Editor / ehm_dal logical model, whose
     attribute names such as Wristshot/Slapshot/Passing are public knowledge).
  3. Reports a per-field detection confidence so the UI can show what was
     found and let the user remap anything the auto-detector missed.

Only the standard library is used (sqlite3).  The source database is never
modified.

Typical use::

    from ehm_roster_importer import probe_database, import_league_from_db

    probe = probe_database("/path/to/database.db")
    print(probe.report())
    league = import_league_from_db("/path/to/database.db",
                                   options={"team_scope": "nhl_only"})
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """Normalise a table/column name for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# ---------------------------------------------------------------------------
# Candidate tables / columns
# ---------------------------------------------------------------------------
# Logical entity -> candidate physical table names, most likely first.

TABLE_CANDIDATES: Dict[str, List[str]] = {
    "staff": ["staff", "players", "people", "persons", "player"],
    "clubs": ["clubs", "teams", "club"],
    "nations": ["nations", "countries", "nation"],
    "competitions": ["club_competitions", "competitions", "leagues",
                     "competition"],
    "affiliations": ["affiliations", "club_affiliations", "affiliation"],
    "draft_history": ["draft_history", "drafts", "draft"],
}

# Logical field -> candidate physical column names, most likely first.
# Names are matched after normalisation, so "FirstName", "first_name" and
# "FIRSTNAME" all match the "firstname" candidate.

COLUMN_SYNONYMS: Dict[str, List[str]] = {
    # identity
    "first_name": ["firstname", "first_name", "forename", "first",
                   "givenname"],
    "last_name": ["lastname", "last_name", "surname", "secondname",
                  "second_name", "familyname", "last"],
    "dob": ["dateofbirth", "dob", "birthdate", "birth_date", "born",
             "date_of_birth"],
    "nation": ["nation", "nationality", "nationid", "nation_id", "country",
               "countryid", "birthnation"],
    "birthplace": ["birthplace", "birth_city", "birthcity", "cityofbirth",
                   "born_in"],
    # player status
    "classification": ["classification", "class", "persontype",
                       "stafftype"],
    "job_for_club": ["jobforclub", "job_for_club", "job", "role",
                     "clubjob"],
    "club_contracted": ["clubcontracted", "club_contracted", "contractedclub",
                        "clubid", "club_id", "teamid", "team_id",
                        "contractclub"],
    "club_playing": ["clubplaying", "club_playing", "playingclub",
                     "playing_for", "currentclub"],
    "wage": ["estimatedwage", "wage", "salary", "annualwage", "yearlywage",
             "contractwage"],
    "wage_weekly": ["estimatedwageweekly", "wageweekly", "weeklywage",
                    "weekly_salary"],
    "contract_expiry": ["contractexpiresclub", "contract_expiry",
                        "contractexpires", "expirydate", "contractend",
                        "expiry_year", "expiryyear"],
    "date_joined": ["datejoinedclub", "date_joined", "joined", "signed"],
    "squad_number": ["squadnumber", "squad_number", "jerseynumber",
                     "jersey_number", "number", "squadno"],
    "height_cm": ["heightcentimetres", "height_cm", "height", "heightcm"],
    "weight_kg": ["weightkilograms", "weight_kg", "weight", "weightkg"],
    "handedness": ["handedness", "shoots", "shot", "stickhand"],
    # ability
    "current_ability": ["currentability", "ca", "current_ability",
                        "ability"],
    "potential_ability": ["potentialability", "pa", "potential_ability",
                          "potential"],
    # club identity
    "club_name": ["name", "clubname", "club_name", "teamname", "team_name",
                  "shortname", "fullname"],
    "club_city": ["city", "clubcity", "location"],
    "club_short": ["shortname", "short_name", "abbreviation", "abbr"],
    # nation identity
    "nation_name": ["name", "nation", "nationname", "country", "longname"],
    # affiliations
    "affil_club": ["clubid", "club_id", "club", "childclub", "affiliate"],
    "affil_parent": ["parentclubid", "parent_club", "parentclub",
                     "parentid", "parent_id", "affiliatedto"],
    "affil_type": ["type", "affiliationtype", "affiliation_type",
                   "level"],
}

# EHM positional ratings (1-20).  From the public ehm_dal logical model.
POSITION_COLUMNS: Dict[str, str] = {
    "Goaltender": "G",
    "LeftDefense": "LD",
    "RightDefense": "RD",
    "LeftWing": "LW",
    "Center": "C",
    "RightWing": "RW",
}

# EHM technical / mental / physical / goalie attributes (1-20).
EHM_ATTRIBUTES = [
    # technical
    "Checking", "Deflections", "Deking", "Faceoffs", "Fighting", "Hitting",
    "Movement", "Passing", "Pokecheck", "Positioning", "Slapshot",
    "Stickhandling", "Wristshot",
    # mental
    "Aggression", "Agitation", "Anticipation", "Bravery", "Consistency",
    "Creativity", "Decisions", "Dirtiness", "Flair", "ImportantMatches",
    "Leadership", "Morale", "PassTendency", "Teamwork", "Versatility",
    "WorkRate",
    # physical
    "Acceleration", "Agility", "Balance", "InjuryProneness",
    "NaturalFitness", "Pace", "Stamina", "Strength",
    # goalie
    "Blocker", "Glove", "OneOnOnes", "Rebounds", "Recovery", "Reflexes",
]

# EHM attribute -> Puck Dynasty Player fields.
# Each entry: (ehm attribute, [(pd field, weight), ...]).
# Weights within one EHM attribute sum to ~1 across the PD fields it feeds;
# a PD field may receive contributions from several EHM attributes (averaged).
ATTRIBUTE_MAP: Dict[str, List[Tuple[str, float]]] = {
    # -- technical --
    "Wristshot": [("wristshot", 0.6), ("shooting", 0.25),
                  ("shooting_accuracy", 0.15)],
    "Slapshot": [("slapshot", 0.6), ("shooting", 0.25),
                 ("shooting_power", 0.15)],
    "Passing": [("passing", 0.5), ("passing_accuracy", 0.3),
                ("first_pass", 0.2)],
    "Stickhandling": [("stickhandling", 0.5), ("deking", 0.3),
                      ("puck_protection", 0.2)],
    "Deking": [("deking", 0.7), ("stickhandling", 0.3)],
    "Checking": [("checking", 0.6), ("bodycheck", 0.4)],
    "Hitting": [("bodycheck", 0.5), ("aggressiveness", 0.3),
                ("hitting_tendency", 0.2)],
    "Pokecheck": [("pokecheck", 0.6), ("defensive_awareness", 0.25),
                  ("shot_blocking", 0.15)],
    "Positioning": [("positioning", 0.6), ("defensive_awareness", 0.25),
                    ("off_the_puck", 0.15)],
    "Faceoffs": [("faceoffs", 0.7), ("faceoff_wins", 0.3)],
    "Deflections": [("deflections", 0.7), ("screen_shots", 0.3)],
    "Movement": [("off_the_puck", 0.6), ("forechecking", 0.4)],
    "Fighting": [("aggressiveness", 0.6), ("strength", 0.4)],
    # -- mental --
    "Aggression": [("aggressiveness", 0.8), ("hitting_tendency", 0.2)],
    "Agitation": [("aggressiveness", 0.5), ("discipline", -0.3)],
    "Anticipation": [("anticipation", 0.6), ("hockey_iq", 0.4)],
    "Bravery": [("pressure_player", 0.4), ("composure", 0.3),
                ("shot_blocking", 0.3)],
    "Consistency": [("consistency", 1.0)],
    "Creativity": [("creativity", 0.5), ("passing_creativity", 0.3),
                   ("vision", 0.2)],
    "Decisions": [("decision_making", 0.6), ("hockey_iq", 0.4)],
    "Dirtiness": [("discipline", -0.6), ("aggressiveness", 0.4)],
    "Flair": [("flair", 0.8), ("deking", 0.2)],
    "ImportantMatches": [("important_matches", 0.7),
                         ("pressure_player", 0.3)],
    "Leadership": [("leadership", 1.0)],
    "Morale": [("morale", 1.0)],
    "PassTendency": [("shoot_pass_tendency", -0.8)],
    "Teamwork": [("teamwork", 1.0)],
    "Versatility": [("adaptability", 0.7), ("hockey_iq", 0.3)],
    "WorkRate": [("work_rate", 0.8), ("forechecking", 0.2)],
    # -- physical --
    "Acceleration": [("acceleration", 0.7), ("skating", 0.3)],
    "Agility": [("agility", 0.7), ("skating", 0.3)],
    "Balance": [("balance", 0.8), ("strength", 0.2)],
    "InjuryProneness": [("injury_proneness", 1.0)],
    "NaturalFitness": [("durability", 0.5), ("endurance", 0.5)],
    "Pace": [("speed", 0.6), ("skating", 0.4)],
    "Stamina": [("stamina", 0.6), ("endurance", 0.4)],
    "Strength": [("strength", 1.0)],
    # -- goalie --
    "Blocker": [("stick_side", 0.7), ("goaltending", 0.3)],
    "Glove": [("glove_hand", 0.7), ("goaltending", 0.3)],
    "OneOnOnes": [("breakaway_skill", 0.6), ("composure", 0.4)],
    "Rebounds": [("rebound_control", 1.0)],
    "Recovery": [("breakaway_skill", 0.4), ("agility", 0.3),
                 ("goaltending", 0.3)],
    "Reflexes": [("reflexes", 0.8), ("goaltending", 0.2)],
}

# Fields whose contribution is inverted (high EHM value -> lower PD value).
# Handled via the negative weights above; the base neutral value is 30.
_INVERT_BASE = 30.0


def ehm_to_pd_scale(ehm_value: Any) -> Optional[float]:
    """Convert an EHM 1-20 attribute to Puck Dynasty's internal ~50 scale.

    Mapping: 1 -> 12, 10 -> 30, 15 -> 40, 20 -> 50.
    Returns None for missing/invalid values.
    """
    try:
        v = float(ehm_value)
    except (TypeError, ValueError):
        return None
    v = max(1.0, min(20.0, v))
    return 10.0 + v * 2.0

# ---------------------------------------------------------------------------
# Schema probing / detection
# ---------------------------------------------------------------------------

@dataclass
class DetectedTable:
    logical: str
    physical: Optional[str]
    columns: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0..1


@dataclass
class SchemaProbe:
    """Result of probing an EHM database file."""
    path: str
    is_sqlite: bool = False
    tables: List[str] = field(default_factory=list)
    detected: Dict[str, DetectedTable] = field(default_factory=dict)
    field_map: Dict[str, Optional[str]] = field(default_factory=dict)
    attribute_columns: Dict[str, str] = field(default_factory=dict)
    position_columns: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    staff_row_count: int = 0
    club_row_count: int = 0

    @property
    def confidence(self) -> float:
        """Overall detection confidence 0..1 based on critical fields."""
        critical = ["first_name", "last_name", "club_name"]
        found = sum(1 for f in critical if self.field_map.get(f))
        score = found / len(critical)
        if self.attribute_columns:
            score = score * 0.6 + 0.4 * min(
                1.0, len(self.attribute_columns) / 10.0)
        if self.position_columns:
            score = min(1.0, score + 0.1)
        return round(score, 2)

    def report(self) -> str:
        lines = [f"Database: {os.path.basename(self.path)}"]
        lines.append(f"SQLite: {'yes' if self.is_sqlite else 'NO'}")
        lines.append(f"Tables found: {len(self.tables)}")
        for logical, det in self.detected.items():
            mark = "OK " if det.physical else "MISS"
            lines.append(
                f"  [{mark}] {logical:14s} -> "
                f"{det.physical or '(not found)'}")
        lines.append("Key fields:")
        for logical_field in ["first_name", "last_name", "dob", "nation",
                              "club_contracted", "wage", "contract_expiry",
                              "current_ability", "potential_ability",
                              "height_cm", "weight_kg", "handedness",
                              "squad_number", "club_name", "nation_name"]:
            col = self.field_map.get(logical_field)
            lines.append(f"  {'OK ' if col else 'MISS'} "
                         f"{logical_field:17s} -> {col or '(not found)'}")
        lines.append(f"EHM attributes mapped: {len(self.attribute_columns)}")
        lines.append(f"Position ratings mapped: {len(self.position_columns)}")
        lines.append(f"Staff rows: {self.staff_row_count}, "
                     f"Club rows: {self.club_row_count}")
        lines.append(f"Overall confidence: {self.confidence:.0%}")
        if self.errors:
            lines.append("Errors:")
            lines.extend(f"  - {e}" for e in self.errors)
        return "\n".join(lines)


def _find_table(tables: List[str],
                candidates: List[str]) -> Optional[str]:
    """Pick the best physical table for a logical entity."""
    norm_map = {_norm(t): t for t in tables}
    # 1. exact normalised match against candidates in priority order
    for cand in candidates:
        if _norm(cand) in norm_map:
            return norm_map[_norm(cand)]
    # 2. substring match
    for cand in candidates:
        nc = _norm(cand)
        for norm_name, physical in norm_map.items():
            if nc in norm_name or norm_name in nc:
                return physical
    return None


def _find_column(columns: List[str],
                 candidates: List[str]) -> Optional[str]:
    """Pick the best physical column for a logical field."""
    norm_map = {_norm(c): c for c in columns}
    for cand in candidates:
        if _norm(cand) in norm_map:
            return norm_map[_norm(cand)]
    for cand in candidates:
        nc = _norm(cand)
        for norm_name, physical in norm_map.items():
            if nc and (nc in norm_name or norm_name in nc):
                return physical
    return None


def _table_columns(conn: sqlite3.Connection,
                   table: str) -> List[str]:
    try:
        cur = conn.execute(
            f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")')
        return [row[1] for row in cur.fetchall()]
    except sqlite3.Error:
        return []


def probe_database(path: str) -> SchemaProbe:
    """Open an EHM database.db read-only and detect its schema."""
    probe = SchemaProbe(path=path)
    if not os.path.isfile(path):
        probe.errors.append(f"File not found: {path}")
        return probe
    # Quick magic check for SQLite
    try:
        with open(path, "rb") as fh:
            magic = fh.read(16)
        probe.is_sqlite = magic.startswith(b"SQLite format 3")
    except OSError as exc:
        probe.errors.append(f"Cannot read file: {exc}")
        return probe
    if not probe.is_sqlite:
        probe.errors.append(
            "Not a SQLite database (bad magic). Expected an EHM "
            "database.db file.")
        return probe

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        probe.errors.append(f"SQLite open failed: {exc}")
        return probe

    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'")
        probe.tables = sorted(row[0] for row in cur.fetchall())

        for logical, candidates in TABLE_CANDIDATES.items():
            physical = _find_table(probe.tables, candidates)
            det = DetectedTable(logical=logical, physical=physical)
            if physical:
                det.columns = _table_columns(conn, physical)
                det.confidence = 1.0 if _norm(physical) in (
                    _norm(c) for c in candidates) else 0.6
                try:
                    det_count = conn.execute(
                        f'SELECT COUNT(*) FROM '
                        f'"{physical.replace(chr(34), chr(34)*2)}"'
                    ).fetchone()[0]
                except sqlite3.Error:
                    det_count = 0
                if logical == "staff":
                    probe.staff_row_count = det_count
                elif logical == "clubs":
                    probe.club_row_count = det_count
            probe.detected[logical] = det

        staff_cols = probe.detected["staff"].columns

        # logical field -> physical column.  Only identity fields live on
        # the clubs/nations/affiliations tables; club_contracted and
        # club_playing are staff-table fields despite the "club_" prefix.
        for logical_field, candidates in COLUMN_SYNONYMS.items():
            if logical_field in ("club_pk", "club_name", "club_city",
                                 "club_short"):
                cols = probe.detected["clubs"].columns
            elif logical_field in ("nation_pk", "nation_name",
                                   "nation_short"):
                cols = probe.detected["nations"].columns
            elif logical_field in ("affil_club", "affil_parent",
                                   "affil_type"):
                cols = probe.detected["affiliations"].columns
            else:
                cols = staff_cols
            probe.field_map[logical_field] = _find_column(cols, candidates)

        # EHM attributes: match exact attribute names case-insensitively
        staff_norm = {_norm(c): c for c in staff_cols}
        for attr in EHM_ATTRIBUTES:
            if _norm(attr) in staff_norm:
                probe.attribute_columns[attr] = staff_norm[_norm(attr)]
        for pos_col, _pos in POSITION_COLUMNS.items():
            if _norm(pos_col) in staff_norm:
                probe.position_columns[pos_col] = staff_norm[_norm(pos_col)]
    except sqlite3.Error as exc:
        probe.errors.append(f"Schema probe failed: {exc}")
    finally:
        conn.close()
    return probe

# ---------------------------------------------------------------------------
# Row conversion helpers
# ---------------------------------------------------------------------------

def _parse_dob(value: Any) -> Optional[date]:
    """Best-effort parse of an EHM date-of-birth value."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        iv = int(value)
        # yyyymmdd integer?
        if 19000101 <= iv <= 21000101:
            try:
                return date(iv // 10000, (iv // 100) % 100, iv % 100)
            except ValueError:
                return None
        # days since unix epoch?
        if 0 < iv < 100000:
            try:
                from datetime import timedelta
                return date(1970, 1, 1) + timedelta(days=iv)
            except (OverflowError, ValueError):
                return None
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
                "%Y/%m/%d", "%d.%m.%Y", "%Y%m%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # "dmy" style: 17 9 1985
    m = re.match(r"(\d{1,2})[ .\-/](\d{1,2})[ .\-/](\d{4})$", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _parse_year(value: Any) -> Optional[int]:
    """Extract a year from a contract-expiry value (date or year int)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        iv = int(value)
        if 1900 <= iv <= 2150:
            return iv
        d = _parse_dob(iv)
        return d.year if d else None
    s = str(value).strip()
    m = re.search(r"(19|20|21)\d{2}", s)
    if m:
        return int(m.group(0))
    d = _parse_dob(s)
    return d.year if d else None


def _calc_age(dob: Optional[date], season_year: int) -> int:
    if dob is None:
        return 24
    # Age at the start of the season (Oct 1 of season_year).
    ref = date(season_year, 10, 1)
    age = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
    return max(16, min(55, age))


def _cm_to_height_str(cm: Any) -> Optional[str]:
    try:
        total_in = float(cm) / 2.54
    except (TypeError, ValueError):
        return None
    feet = int(total_in // 12)
    inches = int(round(total_in % 12))
    if inches == 12:
        feet += 1
        inches = 0
    if not (4 <= feet <= 7):
        return None
    return f"{feet}'{inches}\""


def _kg_to_lbs(kg: Any) -> Optional[int]:
    try:
        lbs = int(round(float(kg) * 2.20462))
    except (TypeError, ValueError):
        return None
    return lbs if 120 <= lbs <= 320 else None


def _map_handedness(value: Any) -> Optional[str]:
    """Best-effort mapping of EHM handedness to 'Left'/'Right'."""
    if value is None or value == "":
        return None
    s = str(value).strip().lower()
    if s.startswith("l"):
        return "Left"
    if s.startswith("r"):
        return "Right"
    if s in ("0",):
        return "Right"
    if s in ("1",):
        return "Left"
    return None


def _map_potential(pa: Any) -> int:
    """Map EHM potential ability (1-200, or negative -PA) to 1-20."""
    try:
        v = float(pa)
    except (TypeError, ValueError):
        return 12
    if v < 0:
        # Negative PA like -15 means a 150-180 range; use the midpoint.
        v = abs(v) * 10 - 5
    return max(1, min(20, int(round(v / 10))))


def _blend_attributes(row: sqlite3.Row,
                      attr_cols: Dict[str, str]) -> Dict[str, float]:
    """Blend EHM 1-20 attributes into PD internal-scale fields.

    Returns {pd_field: value}.  Fields fed by several EHM attributes are
    averaged; inverted contributions (e.g. Dirtiness -> discipline) pivot
    around a neutral base.
    """
    totals: Dict[str, float] = {}
    weights: Dict[str, float] = {}
    for ehm_attr, targets in ATTRIBUTE_MAP.items():
        col = attr_cols.get(ehm_attr)
        if not col:
            continue
        scaled = ehm_to_pd_scale(row[col])
        if scaled is None:
            continue
        for pd_field, w in targets:
            if w >= 0:
                contrib = scaled * w
                totals[pd_field] = totals.get(pd_field, 0.0) + contrib
                weights[pd_field] = weights.get(pd_field, 0.0) + w
            else:
                # Inverted: high EHM value lowers the PD field.
                contrib = (_INVERT_BASE - (scaled - _INVERT_BASE)) * (-w)
                totals[pd_field] = totals.get(pd_field, 0.0) + contrib
                weights[pd_field] = weights.get(pd_field, 0.0) + (-w)
    return {f: totals[f] / weights[f] for f in totals if weights[f] > 0}


def _primary_position(row: sqlite3.Row,
                      pos_cols: Dict[str, str]) -> str:
    """Pick primary position from EHM 1-20 positional ratings."""
    best_pos, best_val = "C", -1.0
    for ehm_col, pd_code in POSITION_COLUMNS.items():
        col = pos_cols.get(ehm_col)
        if not col:
            continue
        try:
            v = float(row[col] or 0)
        except (TypeError, ValueError):
            v = 0
        if v > best_val:
            best_val, best_pos = v, pd_code
    return best_pos


def _is_player_row(row: sqlite3.Row, probe: SchemaProbe) -> bool:
    """Heuristic: is this staff row a player (not a coach/scout/...)?"""
    # Positional ratings present and non-trivial -> player.
    for col in probe.position_columns.values():
        try:
            if float(row[col] or 0) >= 5:
                return True
        except (TypeError, ValueError):
            continue
    # Current ability set -> player.
    ca_col = probe.field_map.get("current_ability")
    if ca_col:
        try:
            if float(row[ca_col] or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    # Job title mentioning coach/scout/manager/physio -> not a player.
    job_col = probe.field_map.get("job_for_club")
    if job_col and row[job_col]:
        s = str(row[job_col]).lower()
        if any(k in s for k in ("coach", "scout", "manager", "physio",
                                "trainer", "director", "president",
                                "assistant", "consultant")):
            # "Assistant" alone is ambiguous (assistant captain exists),
            # so require a staff-ish word as well.
            if any(k in s for k in ("coach", "scout", "manager", "physio",
                                    "trainer", "director", "president")):
                return False
    return True

# ---------------------------------------------------------------------------
# League import
# ---------------------------------------------------------------------------

# Extra table candidates needed only at import time.
TABLE_CANDIDATES["game_data"] = ["game_basic_data", "basic_data",
                                 "gamebasicdata"]
TABLE_CANDIDATES["db_header"] = ["database_header", "header",
                                 "databaseheader"]

COLUMN_SYNONYMS["club_pk"] = ["clubid", "club_id", "id"]
COLUMN_SYNONYMS["nation_pk"] = ["nationid", "nation_id", "id"]
COLUMN_SYNONYMS["start_date"] = ["startdate", "start_date", "game_start",
                                 "seasonstart", "currentdate"]
COLUMN_SYNONYMS["nation_short"] = ["shortname", "short_name", "abbreviation",
                                   "code", "iso"]

# Known club renames so ECK names still match Puck Dynasty's 32 teams.
CLUB_ALIASES = {
    "utahmammoth": "utah hockey club",
    "utahhc": "utah hockey club",
    "arizonacoyotes": "utah hockey club",
}

STAFF_ROLE_KEYWORDS = [
    (("head coach", "headcoach", "manager"), "HEAD_COACH"),
    (("goaltending coach", "goalie coach", "goaltender coach"),
     "GOALIE_COACH"),
    (("assistant coach",), "ASSISTANT_COACH"),
    (("general manager", "gm"), "GENERAL_MANAGER"),
    (("head scout", "chief scout"), "HEAD_SCOUT"),
    (("scout",), "PROFESSIONAL_SCOUT"),
    (("physio", "trainer", "conditioning"), "CONDITIONING_COACH"),
    (("skills coach",), "SKILLS_COACH"),
]

# EHM non-player attribute -> PD Staff field (both 1-20, direct map).
STAFF_ATTR_MAP = {
    "CoachingForwards": "coaching_forwards",
    "CoachingDefensemen": "coaching_defensemen",
    "CoachingGoaltenders": "coaching_goalies",
    "ManHandling": "man_management",
    "Motivating": "motivating",
    "Youngsters": "working_with_youngsters",
    "JudgingPotential": "judging_player_potential",
    "Discipline": "discipline",
    "Attacking": "attacking_coaching",
}


def _norm_club(name: str) -> str:
    n = _norm(name)
    return CLUB_ALIASES.get(n, n)


def _detect_season_year(conn: sqlite3.Connection,
                        probe: SchemaProbe) -> Optional[int]:
    for logical in ("game_data", "db_header"):
        det = probe.detected.get(logical)
        if not det or not det.physical:
            # table may not have been probed (added after probe); look up
            physical = _find_table(probe.tables,
                                   TABLE_CANDIDATES[logical])
            cols = _table_columns(conn, physical) if physical else []
        else:
            physical, cols = det.physical, det.columns
        if not physical:
            continue
        col = _find_column(cols, COLUMN_SYNONYMS["start_date"])
        if not col:
            continue
        try:
            row = conn.execute(
                f'SELECT "{col.replace(chr(34), chr(34)*2)}" FROM '
                f'"{physical.replace(chr(34), chr(34)*2)}" LIMIT 1'
            ).fetchone()
        except sqlite3.Error:
            continue
        if row and row[0]:
            yr = _parse_year(row[0])
            if yr:
                return yr
    return None


def _staff_role_for(job_title: Any):
    """Map an EHM job title to a Puck Dynasty StaffRole (or None)."""
    from game_classes import StaffRole
    if not job_title:
        return None
    s = _norm(str(job_title))
    for keywords, role_name in STAFF_ROLE_KEYWORDS:
        if any(_norm(k) in s for k in keywords):
            try:
                return StaffRole[role_name]
            except KeyError:
                return None
    return None


def import_league_from_db(path: str,
                          options: Optional[Dict[str, Any]] = None,
                          progress_callback=None,
                          probe: Optional[SchemaProbe] = None):
    """Import an EHM database.db into a Puck Dynasty League.

    :param path: filesystem path to database.db.
    :param options: dict with keys:
        team_scope: "nhl_only" (default) — only NHL clubs become teams;
            everyone else becomes a free agent.  "nhl_plus_affiliates" —
            detected farm clubs feed the parent club's AHL roster.
        season_year: int, default auto-detected or current year.
        salary_multiplier: float applied to imported wages (default 1.0).
        import_staff: bool, import non-player staff (default True).
        include_free_agents: bool (default True).
        max_players: int|None — safety cap on imported players.
    :param progress_callback: called as fn(fraction 0..1, message).
    :param probe: reuse an existing SchemaProbe to skip re-probing.
    :returns: (League, stats dict).
    """
    from game_classes import (League, Player, PlayerPosition, Staff)

    options = options or {}
    team_scope = options.get("team_scope", "nhl_only")
    salary_mult = float(options.get("salary_multiplier", 1.0) or 1.0)
    import_staff = bool(options.get("import_staff", True))
    include_fa = bool(options.get("include_free_agents", True))
    max_players = options.get("max_players")

    def progress(frac, msg):
        if progress_callback:
            try:
                progress_callback(max(0.0, min(1.0, frac)), msg)
            except Exception:
                pass

    progress(0.02, "Probing database schema...")
    if probe is None:
        probe = probe_database(path)
    if probe.errors or not probe.is_sqlite:
        raise ValueError("; ".join(probe.errors) or
                         "Not a readable EHM database.")
    if not probe.field_map.get("first_name") or \
            not probe.field_map.get("last_name"):
        raise ValueError(
            "Could not identify player name columns in this database. "
            "Try the manual column mapping in the import wizard.")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        season_year = options.get("season_year") or \
            _detect_season_year(conn, probe) or date.today().year

        fm = dict(probe.field_map)  # allow caller overrides later
        staff_table = probe.detected["staff"].physical
        clubs_table = probe.detected["clubs"].physical

        # -- nations ---------------------------------------------------
        progress(0.06, "Reading nations...")
        nation_names: Dict[Any, str] = {}
        if probe.detected["nations"].physical:
            pk = fm.get("nation_pk")
            nm = fm.get("nation_name") or fm.get("nation_short")
            if pk and nm:
                for r in conn.execute(
                        f'SELECT "{pk}", "{nm}" FROM '
                        f'"{probe.detected["nations"].physical}"'):
                    if r[1]:
                        nation_names[r[0]] = str(r[1]).strip()

        # -- clubs -----------------------------------------------------
        progress(0.10, "Reading clubs...")
        clubs: Dict[Any, Dict[str, Any]] = {}
        if clubs_table:
            pk = fm.get("club_pk")
            nm = fm.get("club_name")
            city = fm.get("club_city")
            cols = [c for c in (pk, nm, city) if c]
            if pk and nm:
                q = (f'SELECT {", ".join(chr(34) + c.replace(chr(34), chr(34)*2) + chr(34) for c in cols)} '
                     f'FROM "{clubs_table}"')
                for r in conn.execute(q):
                    clubs[r[0]] = {
                        "name": str(r[1]).strip() if r[1] else "",
                        "city": str(r[2]).strip() if len(r) > 2 and r[2]
                        else "",
                    }

        # -- affiliations (farm teams -> NHL parent) --------------------
        progress(0.14, "Reading affiliations...")
        affiliate_parent: Dict[Any, Any] = {}
        aff_table = probe.detected["affiliations"].physical
        if aff_table and team_scope == "nhl_plus_affiliates":
            child_col = fm.get("affil_club")
            parent_col = fm.get("affil_parent")
            type_col = fm.get("affil_type")
            if child_col and parent_col:
                cols = [child_col, parent_col] + ([type_col]
                                                  if type_col else [])
                q = (f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} '
                     f'FROM "{aff_table}"')
                for r in conn.execute(q):
                    if type_col and r[2]:
                        t = str(r[2]).lower()
                        if not any(k in t for k in
                                   ("primary", "farm", "affiliat", "minor")):
                            continue
                    if r[0] not in affiliate_parent:
                        affiliate_parent[r[0]] = r[1]

        # -- build league & match clubs to the 32 NHL teams -------------
        progress(0.18, "Matching clubs to NHL teams...")
        league = League(f"Imported EHM Rosters")
        league.season_year = season_year
        template = {_norm_club(t.team_name): t for t in league.teams}
        club_to_team: Dict[Any, Any] = {}
        club_to_ahl_parent: Dict[Any, Any] = {}
        unmatched_clubs: List[str] = []
        for cid, info in clubs.items():
            key = _norm_club(info["name"])
            team = template.get(key)
            if team is None:
                # try city + name combos, e.g. "New York" duplicates
                for tname, t in template.items():
                    if key and (key in tname or tname in key):
                        team = t
                        break
            if team is not None:
                club_to_team[cid] = team
            else:
                parent_cid = affiliate_parent.get(cid)
                parent_team = club_to_team.get(parent_cid) if parent_cid \
                    else None
                if parent_team is not None:
                    club_to_ahl_parent[cid] = parent_team
                else:
                    unmatched_clubs.append(info["name"])

        # -- staff rows -------------------------------------------------
        progress(0.22, "Reading players...")
        col_first = fm["first_name"]
        col_last = fm["last_name"]
        # Restrict the scan to relevant clubs for speed on huge DBs.
        relevant_club_ids = set(club_to_team) | set(club_to_ahl_parent)
        where = ""
        params: List[Any] = []
        club_col = fm.get("club_contracted") or fm.get("club_playing")
        if team_scope == "nhl_only" and club_col and relevant_club_ids:
            # NHL clubs + unattached (NULL) players only.
            placeholders = ",".join("?" for _ in relevant_club_ids)
            where = (f'WHERE "{club_col}" IS NULL OR '
                     f'"{club_col}" IN ({placeholders})')
            params = list(relevant_club_ids)

        q = f'SELECT * FROM "{staff_table}" {where}'
        cur = conn.execute(q, params)

        stats = {"players": 0, "staff": 0, "free_agents": 0,
                 "skipped_no_name": 0, "skipped_bad_dob": 0,
                 "skipped_non_player": 0, "unmatched_clubs": unmatched_clubs,
                 "matched_teams": len(set(t.team_name
                                          for t in club_to_team.values()))}

        col_dob = fm.get("dob")
        col_nat = fm.get("nation")
        col_bp = fm.get("birthplace")
        col_job = fm.get("job_for_club")
        col_wage = fm.get("wage")
        col_wage_w = fm.get("wage_weekly")
        col_exp = fm.get("contract_expiry")
        col_ca = fm.get("current_ability")
        col_pa = fm.get("potential_ability")
        col_h = fm.get("height_cm")
        col_w = fm.get("weight_kg")
        col_hand = fm.get("handedness")
        col_num = fm.get("squad_number")

        # staff attribute columns (non-player), matched case-insensitively
        staff_cols_norm = {}
        if staff_table:
            all_cols = [d[0] for d in cur.description]
            staff_cols_norm = {_norm(c): c for c in all_cols}
        staff_attr_cols = {e: staff_cols_norm[_norm(e)]
                           for e in STAFF_ATTR_MAP if _norm(e)
                           in staff_cols_norm}

        league.free_agents = []
        batch_count = 0
        for row in cur:
            batch_count += 1
            if batch_count % 4000 == 0:
                progress(0.22 + 0.6 * min(1.0, batch_count /
                                          max(1, probe.staff_row_count or
                                              batch_count)),
                         f"Importing... {batch_count:,} rows")
            fn = str(row[col_first]).strip() if row[col_first] else ""
            ln = str(row[col_last]).strip() if row[col_last] else ""
            if not fn or not ln:
                stats["skipped_no_name"] += 1
                continue
            # Generated future prospects in ECK packs use negative DOBs.
            dob_raw = row[col_dob] if col_dob else None
            if isinstance(dob_raw, (int, float)) and int(dob_raw) < 0:
                stats["skipped_bad_dob"] += 1
                continue
            dob = _parse_dob(dob_raw)
            age = _calc_age(dob, season_year)

            if _is_player_row(row, probe):
                if max_players and stats["players"] >= max_players:
                    break
                pos_code = _primary_position(row, probe.position_columns)
                try:
                    pd_pos = PlayerPosition(pos_code)
                except ValueError:
                    pd_pos = PlayerPosition.CENTER
                p = Player(first_name=fn, last_name=ln, age=age,
                           primary_position=pd_pos)
                # attributes
                blended = _blend_attributes(row, probe.attribute_columns)
                for f_, v in blended.items():
                    try:
                        setattr(p, f_, int(round(max(1, min(60, v)))))
                    except (AttributeError, TypeError):
                        pass
                # morale is 1-10 on PD
                if "morale" in blended:
                    p.morale = max(1, min(10, int(
                        round(blended["morale"] / 2))))
                if col_ca and row[col_ca]:
                    try:
                        p.peak_rating = max(
                            1, min(20, int(round(float(row[col_ca]) / 10))))
                    except (TypeError, ValueError):
                        pass
                if col_pa and row[col_pa] is not None:
                    p.potential = _map_potential(row[col_pa])
                    pg = p.potential
                    p.potential_grade = ("A" if pg >= 17 else
                                         "B" if pg >= 14 else
                                         "C" if pg >= 11 else
                                         "D" if pg >= 8 else "F")
                # bio
                if col_nat and row[col_nat] is not None:
                    p.nationality = nation_names.get(row[col_nat],
                                                    p.nationality)
                if col_bp and row[col_bp]:
                    p.birthplace = str(row[col_bp]).strip()
                h = _cm_to_height_str(row[col_h]) if col_h else None
                if h:
                    p.height = h
                w = _kg_to_lbs(row[col_w]) if col_w else None
                if w:
                    p.weight = w
                hand = _map_handedness(row[col_hand]) if col_hand else None
                if hand:
                    p.handedness = hand
                if dob:
                    p.birth_date = dob.isoformat()
                if col_num and row[col_num]:
                    try:
                        num = int(row[col_num])
                        if 1 <= num <= 98:
                            p.jersey_number = num
                    except (TypeError, ValueError):
                        pass
                # contract
                salary = 750000
                if col_wage and row[col_wage]:
                    try:
                        salary = int(float(row[col_wage]) * salary_mult)
                    except (TypeError, ValueError):
                        pass
                elif col_wage_w and row[col_wage_w]:
                    try:
                        salary = int(float(row[col_wage_w]) * 52
                                     * salary_mult)
                    except (TypeError, ValueError):
                        pass
                p.contract.salary = max(0, salary)
                exp_year = _parse_year(row[col_exp]) if col_exp else None
                club_id = row[club_col] if club_col else None
                if exp_year:
                    p.contract.years_remaining = max(
                        1, exp_year - season_year)
                else:
                    p.contract.years_remaining = \
                        1 if club_id in clubs else 0
                # team assignment
                team = club_to_team.get(club_id)
                ahl_parent = club_to_ahl_parent.get(club_id)
                if team is not None:
                    team.add_player(p, "roster")
                elif ahl_parent is not None:
                    ahl_parent.add_player(p, "ahl")
                elif include_fa:
                    league.free_agents.append(p)
                    p.team_name = "Free Agent"
                    stats["free_agents"] += 1
                else:
                    continue
                stats["players"] += 1
            else:
                stats["skipped_non_player"] += 1
                if not import_staff:
                    continue
                role = _staff_role_for(row[col_job]) if col_job else None
                if role is None:
                    continue
                club_id = row[club_col] if club_col else None
                team = club_to_team.get(club_id)
                if team is None:
                    continue
                s = Staff(first_name=fn, last_name=ln, role=role,
                          age=age)
                for ehm_a, pd_f in STAFF_ATTR_MAP.items():
                    col = staff_attr_cols.get(ehm_a)
                    if col and row[col] is not None:
                        try:
                            setattr(s, pd_f, max(
                                1, min(20, int(round(float(row[col]))))))
                        except (TypeError, ValueError, AttributeError):
                            pass
                if col_nat and row[col_nat] is not None:
                    s.nationality = nation_names.get(row[col_nat],
                                                     s.nationality)
                team.staff.append(s)
                stats["staff"] += 1

        progress(0.86, "Finalising rosters...")
        # Ensure goalie coverage & squad statuses.
        for team in league.teams:
            goalies = [pl for pl in team.roster
                       if pl.primary_position == PlayerPosition.GOALIE]
            if len(goalies) < 2 and include_fa:
                need = 2 - len(goalies)
                fa_goalies = sorted(
                    (pl for pl in league.free_agents
                     if pl.primary_position == PlayerPosition.GOALIE),
                    key=lambda pl: pl.overall_rating(),
                    reverse=True)[:need]
                for g in fa_goalies:
                    league.free_agents.remove(g)
                    team.add_player(g, "roster")
            skaters = sorted(
                (pl for pl in team.roster
                 if pl.primary_position != PlayerPosition.GOALIE),
                key=lambda pl: pl.overall_rating(), reverse=True)
            for i, pl in enumerate(skaters):
                if i < 3:
                    pl.squad_status = "Star Player"
                elif i < 9:
                    pl.squad_status = "Key Player"
                elif i < 15:
                    pl.squad_status = "Regular Starter"

        league.initialize_standings()
        progress(1.0, "Done")
        stats["season_year"] = season_year
        stats["detection_confidence"] = probe.confidence
        return league, stats
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Wizard support helpers (appended)
# ---------------------------------------------------------------------------

def retarget_staff_table(probe: SchemaProbe, conn: sqlite3.Connection,
                         physical: str) -> None:
    """Point the probe at a user-chosen staff table and re-derive mappings.

    Used by the import wizard's manual-mapping fallback.  Mutates ``probe``
    in place.
    """
    det = probe.detected.get("staff")
    if det is None:
        det = DetectedTable(logical="staff", physical=physical)
        probe.detected["staff"] = det
    det.physical = physical
    det.columns = _table_columns(conn, physical)
    staff_cols = det.columns
    for logical_field, candidates in COLUMN_SYNONYMS.items():
        if logical_field in ("club_pk", "club_name", "club_city",
                             "club_short", "nation_pk", "nation_name",
                             "nation_short", "affil_club", "affil_parent",
                             "affil_type"):
            continue  # these live on other tables, not the staff table
        probe.field_map[logical_field] = _find_column(staff_cols,
                                                      candidates)
    staff_norm = {_norm(c): c for c in staff_cols}
    probe.attribute_columns = {
        a: staff_norm[_norm(a)] for a in EHM_ATTRIBUTES
        if _norm(a) in staff_norm}
    probe.position_columns = {
        p: staff_norm[_norm(p)] for p in POSITION_COLUMNS
        if _norm(p) in staff_norm}
    try:
        probe.staff_row_count = conn.execute(
            f'SELECT COUNT(*) FROM "{physical.replace(chr(34), chr(34)*2)}"'
        ).fetchone()[0]
    except sqlite3.Error:
        probe.staff_row_count = 0


def preview_players(path: str, probe: SchemaProbe,
                    limit: int = 10) -> List[Dict[str, Any]]:
    """Return a light preview of players with mapped attributes.

    Each entry: name, club, position, age, overall (display 1-100 scale),
    plus a few headline attributes.  Never raises — returns [] on failure.
    """
    try:
        from game_classes import to_100_scale
    except Exception:
        def to_100_scale(v):
            return max(1, min(100, int(round(float(v) * 2))))
    out: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return out
    try:
        staff_table = (probe.detected.get("staff") or
                       DetectedTable("staff", None)).physical
        if not staff_table or not probe.field_map.get("first_name"):
            return out
        fm = probe.field_map
        # order by current ability desc so the preview shows stars
        order = ""
        if fm.get("current_ability"):
            order = f'ORDER BY "{fm["current_ability"]}" DESC'
        rows = conn.execute(
            f'SELECT * FROM "{staff_table}" {order} LIMIT {int(limit) * 4}'
        ).fetchall()
        # club names for the preview
        club_names: Dict[Any, str] = {}
        clubs_det = probe.detected.get("clubs")
        if clubs_det and clubs_det.physical and fm.get("club_pk") and \
                fm.get("club_name"):
            try:
                for r in conn.execute(
                        f'SELECT "{fm["club_pk"]}", "{fm["club_name"]}" '
                        f'FROM "{clubs_det.physical}"'):
                    club_names[r[0]] = str(r[1])
            except sqlite3.Error:
                pass
        for row in rows:
            if len(out) >= limit:
                break
            if not _is_player_row(row, probe):
                continue
            fn = (row[fm["first_name"]] or "").strip()
            ln = (row[fm["last_name"]] or "").strip()
            if not fn or not ln:
                continue
            blended = _blend_attributes(row, probe.attribute_columns)
            # rough overall: weighted core attrs on display scale
            core = [blended.get(k, 30) for k in
                    ("skating", "shooting", "passing", "deking",
                     "offensive_awareness", "defensive_awareness",
                     "checking")]
            overall = to_100_scale(sum(core) / len(core)) if core else 50
            club_col = fm.get("club_contracted") or fm.get("club_playing")
            club = club_names.get(row[club_col]) if club_col else None
            out.append({
                "name": f"{fn} {ln}",
                "club": club or "Free Agent",
                "pos": _primary_position(row, probe.position_columns),
                "overall": overall,
                "skating": to_100_scale(blended.get("skating", 30)),
                "shooting": to_100_scale(blended.get("shooting", 30)),
                "passing": to_100_scale(blended.get("passing", 30)),
            })
        return out
    except sqlite3.Error:
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass
