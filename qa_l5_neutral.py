"""QA for L5: Performance neutral-point should not penalize anyone.

Muck 2026-10-02: "neutral shouldnt penalize anyone but the rest can stay the same"

Game grades (0-100) are already talent-normalized: 50 = meeting
expectation regardless of overall. The old code used a rising expected
grade (45 + (ovr-70)*0.8), double-counting talent and taxing stars for
average play. Now flat at 50.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")


class MockContract:
    def __init__(self, salary):
        self.salary = salary


class MockPlayer:
    """Minimal player stub for trade value testing."""
    def __init__(self, ovr, grades):
        self._ovr = ovr
        self.recent_game_grades = list(grades) if grades is not None else None
        self.age = 28
        self.contract = MockContract(5_000_000)
        self.contract_years = 3
        self.potential_grade = 'C'
        # Use string position to avoid PlayerPosition import issues
        self.primary_position = 'C'
        self.full_name = f"Test Player {ovr}"

    def overall_rating(self):
        return self._ovr


def get_perf_mult(player):
    """Isolate the performance multiplier via with/without grades ratio."""
    import trade_engine
    saved = player.recent_game_grades
    with_grades = trade_engine.player_trade_value(player)
    player.recent_game_grades = []
    without_grades = trade_engine.player_trade_value(player)
    player.recent_game_grades = saved
    if without_grades == 0:
        return 1.0
    return with_grades / without_grades


print("L5 neutral-point QA...")

import trade_engine

# Use overalls with positive base value: 70, 80, 90
# (OVR 60 gives base=0, can't measure ratio)

# Test 1: Average game (grade 50) is neutral for ALL overalls
print("\n1. Average grades (50) neutral across overalls:")
for ovr in (70, 80, 90):
    p = MockPlayer(ovr, [50.0] * 10)
    mult = get_perf_mult(p)
    check(f"OVR {ovr} avg-50 -> mult ~1.0 (got {mult:.3f})",
          abs(mult - 1.0) < 0.01)

# Test 2: Slump still discounts (rest stays the same)
print("\n2. Slump still discounts:")
for ovr in (70, 80, 90):
    p = MockPlayer(ovr, [30.0] * 10)
    mult = get_perf_mult(p)
    check(f"OVR {ovr} slump-30 -> mult < 1.0 (got {mult:.3f})",
          mult < 0.999)

# Test 3: Heater still earns premium (rest stays the same)
print("\n3. Heater still earns premium:")
for ovr in (70, 80, 90):
    p = MockPlayer(ovr, [70.0] * 10)
    mult = get_perf_mult(p)
    check(f"OVR {ovr} heater-70 -> mult > 1.0 (got {mult:.3f})",
          mult > 1.001)

# Test 4: Bounds respected
print("\n4. Bounds respected:")
p = MockPlayer(90, [0.0] * 10)
mult = get_perf_mult(p)
check(f"Deep slump mult >= 0.75 (got {mult:.3f})", mult >= 0.749)

p = MockPlayer(70, [100.0] * 10)
mult = get_perf_mult(p)
check(f"Massive heater mult <= 1.25 (got {mult:.3f})", mult <= 1.251)

# Test 5: No data = neutral
print("\n5. No grades = neutral:")
for ovr in (70, 90):
    p = MockPlayer(ovr, [])
    mult = get_perf_mult(p)
    check(f"OVR {ovr} no-data -> mult ~1.0 (got {mult:.3f})",
          abs(mult - 1.0) < 0.01)

# Test 6: Breakdown function also fixed (mirrors player_trade_value)
print("\n6. Breakdown function mirrors the fix:")
for ovr in (70, 80, 90):
    p = MockPlayer(ovr, [50.0] * 10)
    try:
        result = trade_engine.player_trade_value_breakdown(p)
        # Breakdown returns (value, [entries])
        entries = result[1] if isinstance(result, tuple) else result
        perf_entries = [e for e in entries
                        if isinstance(e, dict) and (
                            'slump' in str(e.get('detail', '')).lower()
                            or 'heater' in str(e.get('detail', '')).lower())]
        # With avg-50 grades, there should be NO slump/heater adjustment
        check(f"OVR {ovr} breakdown: no slump/heater at avg-50 "
              f"({len(perf_entries)} perf entries)", len(perf_entries) == 0)
    except Exception as e:
        check(f"OVR {ovr} breakdown runs ({e})", False)

# Test 7: Never raises on garbage
print("\n7. Never raises:")
try:
    p = MockPlayer(75, None)
    trade_engine.player_trade_value(p)
    check("None grades doesn't raise", True)
except Exception as e:
    check(f"None grades doesn't raise ({e})", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
