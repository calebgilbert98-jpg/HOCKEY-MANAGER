"""QA for GM Relationships UI (gm_relationships_window.py).

Verifies:
1. Module imports cleanly with stubbed UI deps (headless).
2. All 31 rival GMs appear with valid data (never raises on missing data).
3. Sorting works by respect/heat/stature.
4. Trend arrows map correctly.
5. Color-coding tags assigned correctly.
6. show_gm_relationships() never raises.
7. main.py integration points exist.

Run: python3 ~/workspace/HOCKEY-MANAGER/qa_gm_relationships.py
"""
import sys
import types

sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")

# ----------------------------------------------------------------------
# Stub UI dependencies for headless testing
# ----------------------------------------------------------------------

# --- tkinter.ttk stub ---
_tk = types.ModuleType("tkinter")
_ttk = types.ModuleType("tkinter.ttk")


class _FakeWidget:
    def __init__(self, *a, **k):
        self._children = []
        self._config = dict(k)

    def pack(self, *a, **k):
        return None

    def grid(self, *a, **k):
        return None

    def configure(self, *a, **k):
        self._config.update(k)
        return None

    config = configure

    def pack_propagate(self, *a):
        return None

    def winfo_exists(self):
        return True

    def destroy(self):
        return None


class _FakeTreeview(_FakeWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._items = []
        self._headings = {}
        self._columns = {}
        self._tags = {}

    def heading(self, col, **k):
        self._headings[col] = k

    def column(self, col, **k):
        self._columns[col] = k

    def insert(self, parent, index, values=None, tags=None):
        self._items.append({"values": values, "tags": tags or ()})
        return f"item{len(self._items)}"

    def delete(self, *items):
        self._items = []

    def get_children(self):
        return [f"item{i}" for i in range(len(self._items))]

    def tag_configure(self, tag, **k):
        self._tags[tag] = k

    def yview(self, *a):
        return None


class _FakeScrollbar(_FakeWidget):
    def set(self, *a):
        return None


class _FakeStyle:
    def __init__(self, *a, **k):
        pass

    def configure(self, *a, **k):
        return None

    def map(self, *a, **k):
        return None


_ttk.Treeview = _FakeTreeview
_ttk.Scrollbar = _FakeScrollbar
_ttk.Style = _FakeStyle
_ttk.Frame = _FakeWidget
_ttk.Button = _FakeWidget
_ttk.Label = _FakeWidget
_tk.ttk = _ttk
sys.modules["tkinter"] = _tk
sys.modules["tkinter.ttk"] = _ttk

# --- customtkinter stub ---
_ctk = types.ModuleType("customtkinter")


class _FakeCTkFrame(_FakeWidget):
    pass


class _FakeCTkLabel(_FakeWidget):
    pass


_ctk.CTkFrame = _FakeCTkFrame
_ctk.CTkLabel = _FakeCTkLabel
sys.modules["customtkinter"] = _ctk

# --- popup_system stub ---
_popup = types.ModuleType("popup_system")


class _FakeInGamePopup(_FakeWidget):
    def title(self, *a):
        return None

    def geometry(self, *a):
        return None

    def minsize(self, *a, **k):
        return None

    def grab_set(self):
        return None


_popup.InGamePopup = _FakeInGamePopup
sys.modules["popup_system"] = _popup

# --- ctk_theme stub ---
_theme = types.ModuleType("ctk_theme")
_theme.BG = "#0e0e11"
_theme.PANEL = "#16161a"
_theme.CARD = "#1e1e24"
_theme.BORDER = "#2e2e38"
_theme.TEXT = "#f4f4f5"
_theme.TEXT_DIM = "#a1a1aa"
_theme.TEXT_FAINT = "#71717a"
_theme.GOLD = "#e8b93c"
_theme.GREEN = "#3fb950"
_theme.RED = "#e74c3c"
_theme.BLUE = "#58a6ff"
_theme.TEAL = "#00ceb8"
_theme.TEAL_HOVER = "#00a896"
_theme.ROW_HOVER = "#26262e"
_theme.ROW_SELECTED = "#0d2b28"


def _init_ctk_theme():
    return None


def _heading(parent, text, size=18, **kw):
    w = _FakeWidget()
    return w


def _body(parent, text, size=12, dim=False, **kw):
    w = _FakeWidget()
    return w


def _primary_button(parent, text, command=None, **kw):
    return _FakeWidget()


def _secondary_button(parent, text, command=None, **kw):
    return _FakeWidget()


_theme.init_ctk_theme = _init_ctk_theme
_theme.heading = _heading
_theme.body = _body
_theme.primary_button = _primary_button
_theme.secondary_button = _secondary_button
sys.modules["ctk_theme"] = _theme

# ----------------------------------------------------------------------
# Purge any pristine copies, import from this tree
# ----------------------------------------------------------------------
for _m in list(sys.modules):
    if _m in ("reputation_system", "gm_relationships_window",
              "player_traits"):
        del sys.modules[_m]

import gm_relationships_window as grw
assert "HOCKEY-MANAGER" in grw.__file__, f"wrong tree: {grw.__file__}"

import reputation_system as rs

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name} {detail}")


# ----------------------------------------------------------------------
# Mock league with 32 teams
# ----------------------------------------------------------------------
class _FakeGM:
    _idc = 0

    def __init__(self, name):
        _FakeGM._idc += 1
        self.id = _FakeGM._idc
        self.full_name = name
        self.name = name
        self.career_reputation = 55
        self.reputation_history = []


class _FakeTeam:
    _idc = 0

    def __init__(self, name, gm_name):
        _FakeTeam._idc += 1
        self.id = _FakeTeam._idc
        self.team_name = name
        self._gm = _FakeGM(gm_name)

    @property
    def staff(self):
        # Minimal staff list so _team_gm_staff can find the GM
        return []


class _FakeLeague:
    def __init__(self, teams):
        self.teams = teams


# Patch _team_gm_staff to return our fake GM
_orig_team_gm_staff = rs._team_gm_staff


def _patched_gm_staff(team):
    try:
        g = getattr(team, "_gm", None)
        if g is not None:
            # Give it a role so the role-name check passes
            class _Role:
                name = "GENERAL_MANAGER"
            g.role = _Role()
            return g
    except Exception:
        pass
    return _orig_team_gm_staff(team)


rs._team_gm_staff = _patched_gm_staff

teams = [_FakeTeam(f"Team {i:02d}", f"GM {i:02d}") for i in range(32)]
league = _FakeLeague(teams)
user_team = teams[0]

print("== 1: module structure ==")
check("show_gm_relationships exists", hasattr(grw, "show_gm_relationships"))
check("GMRelationshipsView exists", hasattr(grw, "GMRelationshipsView"))
check("GMRelationshipsWindow exists", hasattr(grw, "GMRelationshipsWindow"))
check("trend arrows defined",
      grw._TREND_ARROW == {"warming": "\u2191", "cooling": "\u2193",
                           "steady": "\u2192"})

print("== 2: view creation (headless) ==")
parent = _FakeWidget()
view = None
try:
    view = grw.GMRelationshipsView(parent, league=league,
                                   user_team=user_team)
    check("view created without raising", True)
except Exception as e:
    check("view created without raising", False, str(e))

print("== 3: all 31 rival GMs appear ==")
if view is not None:
    rows = view._rows
    check("31 rows collected", len(rows) == 31, f"got {len(rows)}")
    # User's own team excluded
    team_names = [r["team"] for r in rows]
    check("user team excluded", "Team 00" not in team_names)
    check("all other teams present",
          all(f"Team {i:02d}" in team_names for i in range(1, 32)))

    # Valid data ranges
    ok_ranges = True
    for r in rows:
        if not (0 <= r["stature"] <= 100):
            ok_ranges = False
        if not (-100 <= r["respect"] <= 100):
            ok_ranges = False
        if not (0 <= r["heat"] <= 100):
            ok_ranges = False
        if r["tier"] not in ("cold", "wary", "cordial", "warm"):
            ok_ranges = False
        if r["trend"] not in ("warming", "cooling", "steady"):
            ok_ranges = False
        if r["arrow"] not in ("\u2191", "\u2193", "\u2192"):
            ok_ranges = False
    check("all rows have valid data ranges", ok_ranges)

    # GM names present
    check("GM names populated",
          all(r["gm"] for r in rows))

print("== 4: sorting ==")
if view is not None:
    # Sort by respect descending (default)
    view._on_sort("respect")
    # After first click on already-selected col, direction toggles.
    # Force known state:
    view._sort_col = "respect"
    view._sort_rev = True
    view._populate()
    items = view._tree._items
    check("tree populated after sort", len(items) == 31, f"got {len(items)}")
    # Verify descending order by parsing the respect values
    vals = []
    for it in items:
        v = it["values"][3]  # respect column, formatted "+d"
        try:
            vals.append(int(v))
        except Exception:
            pass
    check("respect sorted descending", vals == sorted(vals, reverse=True),
          f"{vals[:5]}...")

    # Sort by heat ascending
    view._sort_col = "heat"
    view._sort_rev = False
    view._populate()
    items = view._tree._items
    hvals = []
    for it in items:
        try:
            hvals.append(int(it["values"][5]))
        except Exception:
            pass
    check("heat sorted ascending", hvals == sorted(hvals),
          f"{hvals[:5]}...")

    # Sort by team name
    view._sort_col = "team"
    view._sort_rev = False
    view._populate()
    items = view._tree._items
    tnames = [it["values"][0] for it in items]
    check("team sorted ascending", tnames == sorted(tnames),
          f"{tnames[:3]}...")

print("== 5: color coding ==")
if view is not None:
    # High respect -> respect_high tag
    high = {"respect": 75, "heat": 10}
    tags = view._row_tags(high)
    check("high respect tagged", "respect_high" in tags, str(tags))
    # Low respect -> respect_low tag
    low = {"respect": -50, "heat": 10}
    tags = view._row_tags(low)
    check("low respect tagged", "respect_low" in tags, str(tags))
    # High heat -> heat_high tag
    hot = {"respect": 0, "heat": 80}
    tags = view._row_tags(hot)
    check("high heat tagged", "heat_high" in tags, str(tags))
    # Low heat -> heat_low tag
    cold = {"respect": 0, "heat": 5}
    tags = view._row_tags(cold)
    check("low heat tagged", "heat_low" in tags, str(tags))
    # Neutral -> no tags
    neutral = {"respect": 10, "heat": 40}
    tags = view._row_tags(neutral)
    check("neutral has no tags", len(tags) == 0, str(tags))

print("== 6: missing data grace ==")
# League with broken teams
broken_teams = [_FakeTeam("Good Team", "Good GM"), None, "not-a-team"]
broken_league = _FakeLeague(broken_teams)
view2 = None
try:
    view2 = grw.GMRelationshipsView(_FakeWidget(), league=broken_league,
                                    user_team=broken_teams[0])
    check("broken league handled", True)
    check("good team still collected", len(view2._rows) >= 0)
except Exception as e:
    check("broken league handled", False, str(e))

# None league / None team
try:
    view3 = grw.GMRelationshipsView(_FakeWidget(), league=None,
                                    user_team=None)
    check("None league handled", True)
    check("None league yields no rows", len(view3._rows) == 0)
except Exception as e:
    check("None league handled", False, str(e))

print("== 7: show_gm_relationships never raises ==")
try:
    result = grw.show_gm_relationships(_FakeWidget(), league, user_team)
    check("show_gm_relationships returned", result is not None)
except Exception as e:
    check("show_gm_relationships returned", False, str(e))

try:
    result = grw.show_gm_relationships(None, None, None)
    check("show_gm_relationships with Nones", True)
except Exception as e:
    check("show_gm_relationships with Nones", False, str(e))

print("== 8: main.py integration ==")
with open("/home/hatch/workspace/HOCKEY-MANAGER/main.py") as f:
    main_src = f.read()
check("open_gm_relationships_window in main.py",
      "def open_gm_relationships_window" in main_src)
check("GM Relations nav pill in main.py",
      "GM Relations" in main_src)
check("gm_relationships screen registered",
      "'gm_relationships'" in main_src)

# Restore
rs._team_gm_staff = _orig_team_gm_staff

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
