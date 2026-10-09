"""QA: Position labels use standard hockey abbreviations (Muck 2026-10-02).

Verifies:
1. position_label() maps all positions to C/LW/RW/RD/LD/G (never RIGHT_WING etc.)
2. Multi-position players show as "C/LW", "LD/RD", etc.
3. position_label never raises (None, missing attrs, empty player)
4. No UI source file emits raw enum names in display paths
"""
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from game_classes import Player, PlayerPosition, position_label, POSITION_ABBREV

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")


class FakePlayer:
    def __init__(self, primary, secondaries=None):
        self.primary_position = primary
        self.secondary_positions = secondaries or []


print("== Abbreviation mapping ==")
expected = {
    PlayerPosition.CENTER: "C",
    PlayerPosition.LEFT_WING: "LW",
    PlayerPosition.RIGHT_WING: "RW",
    PlayerPosition.LEFT_DEFENSE: "LD",
    PlayerPosition.RIGHT_DEFENSE: "RD",
    PlayerPosition.DEFENSE: "D",
    PlayerPosition.GOALIE: "G",
}
for pos, abbr in expected.items():
    check(f"{pos.name} -> {abbr}", position_label(FakePlayer(pos)) == abbr)

print("== Multi-position ==")
check("C + LW -> C/LW",
      position_label(FakePlayer(PlayerPosition.CENTER, [PlayerPosition.LEFT_WING])) == "C/LW")
check("LD + RD -> LD/RD",
      position_label(FakePlayer(PlayerPosition.LEFT_DEFENSE, [PlayerPosition.RIGHT_DEFENSE])) == "LD/RD")
check("RW + LW -> RW/LW",
      position_label(FakePlayer(PlayerPosition.RIGHT_WING, [PlayerPosition.LEFT_WING])) == "RW/LW")
check("duplicate secondary not repeated",
      position_label(FakePlayer(PlayerPosition.CENTER, [PlayerPosition.CENTER])) == "C")
check("G has no secondaries -> G",
      position_label(FakePlayer(PlayerPosition.GOALIE)) == "G")

print("== Never raises ==")
check("None primary -> ?", position_label(FakePlayer(None)) == "?")
check("missing attrs -> ?", position_label(object()) == "?")
check("None player -> ?", position_label(None) == "?")
check("empty secondaries attr missing",
      position_label(type("P", (), {"primary_position": PlayerPosition.CENTER})()) == "C")

print("== POSITION_ABBREV covers all enum members ==")
for pos in PlayerPosition:
    check(f"abbrev for {pos.name}", pos.name in POSITION_ABBREV)

print("== No raw enum names in UI display paths ==")
# Display files must not use .primary_position.name for user-visible text
# (logic comparisons like == "GOALIE" are fine)
ui_files = ["main.py", "windows.py", "ctk_theme.py", "dashboard_home.py",
            "manager_hub_window.py", "modern_profile.py"]
bad = []
for fn in ui_files:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fn)
    if not os.path.exists(path):
        continue
    with open(path) as f:
        for i, line in enumerate(f, 1):
            if "primary_position.name" in line:
                # Allow: logic comparisons, _pos_short helper internals, grouping
                stripped = line.strip()
                if any(k in line for k in ["==", "!=", " in ", "mapping.get",
                                           "mapping[", ".get(player.primary_position.name",
                                           "fam(", "def _pos_group", "def _wing_side",
                                           "_slot_expected_pos", "is_position_compatible",
                                           "def _player_group", "def _pos_short",
                                           "def _is_off_position",
                                           "player.primary_position.name[:2]"]):
                    continue
                # Allow position_label-adjacent lines (already fixed)
                if "position_label" in line:
                    continue
                # Logic, not display: _player_group body, _is_off_position body
                if stripped in ("pos = player.primary_position.name",
                                "actual = player.primary_position.name",
                                "player_pos = player.primary_position.name"):
                    continue
                bad.append(f"{fn}:{i}: {stripped[:80]}")
check("no raw .name in display paths", not bad)
for b in bad:
    print(f"    LEFTOVER: {b}")

print("== position_label used in key UI files ==")
for fn in ["main.py", "windows.py", "modern_profile.py"]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fn)
    with open(path) as f:
        content = f.read()
    check(f"{fn} uses position_label",
          "position_label(" in content or "position_label as _pl" in content)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
