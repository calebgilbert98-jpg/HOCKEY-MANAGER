"""Static screen registry for native_ui_v2.

CRITICAL: All screen imports are at module top level (not inside a
function, not via __import__/importlib). PyInstaller's AST analysis
sees these unconditionally, so screens cannot be silently dropped
from the bundle.

To add a screen:
  1. Create native_ui_v2/screens/<name>.py with a class
     subclassing BaseScreen and setting screen_key.
  2. Import it below.
  3. Add it to SCREEN_REGISTRY.
  4. Add the module to puck_dynasty_v2.spec hiddenimports.
"""
from .base import BaseScreen, resolve_gm, safe
from .dashboard import DashboardScreen
from .roster import RosterScreen
from .standings import StandingsScreen

# Static registry: screen key -> screen class.
# No dynamic imports anywhere in v2.
SCREEN_REGISTRY = {
    DashboardScreen.screen_key: DashboardScreen,
    RosterScreen.screen_key: RosterScreen,
    StandingsScreen.screen_key: StandingsScreen,
}

# Order for the navigation sidebar.
NAV_ORDER = ["dashboard", "roster", "standings"]

__all__ = [
    "BaseScreen", "resolve_gm", "safe",
    "DashboardScreen", "RosterScreen", "StandingsScreen",
    "SCREEN_REGISTRY", "NAV_ORDER",
]
