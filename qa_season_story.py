# qa_season_story.py -- Season Story view (Muck 2026-10-02)
#
# Verifies the inbox Season Story surface builds without errors on empty
# data, garbage data, and representative sample data. The GUI layer
# (customtkinter) is stubbed -- the data-collection logic is real.
import sys
import types
from datetime import date

sys.path.insert(0, '.')

# --- stub customtkinter -------------------------------------------------
_created = []


class _StubWidget:
    def __init__(self, *a, **k):
        self.args = a
        self.kwargs = k
        self.children = []
        self.packed = []
        self.gridded = []
        self.configured = {}
        self.progress = None
        _created.append(self)

    def pack(self, *a, **k):
        self.packed.append((a, k))
        return self

    def grid(self, *a, **k):
        self.gridded.append((a, k))
        return self

    def grid_remove(self):
        return self

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        pass

    def configure(self, *a, **k):
        self.configured.update(k)
        return self

    def set(self, v):
        self.progress = v
        return self


_ctk = types.ModuleType('customtkinter')
for _name in ('CTkFrame', 'CTkButton', 'CTkLabel', 'CTkScrollableFrame',
              'CTkProgressBar', 'CTkToplevel', 'CTkEntry', 'CTkTextbox',
              'CTkComboBox', 'CTkCheckBox'):
    setattr(_ctk, _name, type(_name, (_StubWidget,), {}))
_ctk.set_appearance_mode = lambda *a, **k: None
_ctk.set_default_color_theme = lambda *a, **k: None
sys.modules['customtkinter'] = _ctk

import inbox_window  # noqa: E402
from game_classes import EmailMessage  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


# --- fakes ---------------------------------------------------------------
class FakeLeague:
    def __init__(self):
        self.season_year = 2027
        self.media_narratives = []
        self.rivalries = []


class FakeMediaSystem:
    def __init__(self):
        self.storylines = []


class FakeGM:
    def __init__(self, league):
        self.league = league
        self.current_date = date(2027, 3, 15)
        self.media_system = FakeMediaSystem()


class FakeHistory:
    def __init__(self, seasons):
        self.seasons = seasons


class FakeTeam:
    def __init__(self, name='Testers'):
        self.team_name = name


class FakeInbox:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.unread_count = 0

    def get_unread_messages(self):
        return []

    def get_urgent_messages(self):
        return []

    def get_overdue_messages(self):
        return []


class FakeApp:
    def __init__(self, league, inbox, history=None):
        self.game_manager = FakeGM(league)
        self.game_manager.league_history = history
        self.user_team = FakeTeam()
        self.inbox = inbox


def make_view(app):
    """Unbound InboxView with stubbed widgets."""
    v = object.__new__(inbox_window.InboxView)
    v.app = app
    v.inbox = app.inbox
    v._ct = dict(TEAL='#2dd4bf', TEAL_HOVER='#14b8a6', BG='#0b0f14',
                 PANEL='#111827', CARD='#1a2230', BORDER='#2a3444',
                 TEXT='#f3f4f6', TEXT_DIM='#9ca3af', TEXT_FAINT='#6b7280',
                 GOLD='#fbbf24', GREEN='#34d399', RED='#f87171',
                 BLUE='#60a5fa', ROW_HOVER='#223', ROW_SELECTED='#334')
    from ctk_theme import heading, body
    v._heading = heading
    v._body = body
    v.stats_label = _StubWidget()
    v._story_frame = _ctk.CTkScrollableFrame()
    v._list_frame = _StubWidget()
    v._preview_frame = _StubWidget()
    v._filter_buttons = {}
    v._current_filter = 'all'
    return v


class FakeNarrative:
    def __init__(self, kind, team_name, title, heat):
        self.kind = kind
        self.team_name = team_name
        self.title = title
        self.heat = heat


class FakeStoryline:
    def __init__(self, title, intensity, active=True):
        self.title = title
        self.intensity = intensity
        self._active = active
        self.type = types.SimpleNamespace(value='breakout')

    def is_active(self, now):
        return self._active


# --- 1. filter wiring ----------------------------------------------------
check("story pill in _FILTERS",
      ("📖 Story", "story") in inbox_window.InboxView._FILTERS)
check("_show_story_view exists", hasattr(inbox_window.InboxView, '_show_story_view'))
check("_populate_season_story exists",
      hasattr(inbox_window.InboxView, '_populate_season_story'))

# --- 2. empty data: never raises, empty sections --------------------------
league = FakeLeague()
app = FakeApp(league, FakeInbox())
v = make_view(app)
dev = v._collect_developing()
check("empty developing -> []", dev == [])
feed = v._collect_story_feed()
check("empty feed -> []", feed == [])
hist = v._collect_history_lines()
check("empty history -> []", hist == [])
title, hook = v._story_hook()
check("empty hook defaults", "Season Story" in title and len(hook) > 0)
try:
    v._populate_season_story()
    check("populate on empty data: no raise", True)
except Exception as e:
    check(f"populate on empty data: no raise ({e})", False)
check("stats label updated on empty",
      "Season Story" in str(v.stats_label.configured.get('text', '')))

# --- 3. sample data --------------------------------------------------------
league2 = FakeLeague()
league2.media_narratives = [
    FakeNarrative('cup_window', 'Testers', 'The window is open in Testers', 82),
    FakeNarrative('legacy_chase', 'Testers', 'Veteran running out of chances', 64),
]
league2.rivalries = [
    {'kind': 'team_team', 'a': 't1', 'b': 't2', 'a_name': 'Testers',
     'b_name': 'Rivals', 'intensity': 72, 'origin': 'playoff war'},
    {'kind': 'team_team', 'a': 't1', 'b': 't3', 'a_name': 'Testers',
     'b_name': 'Mildfoes', 'intensity': 20, 'origin': 'regional'},
    {'kind': 'gm_respect', 'a': 't1', 'b': 't2', 'intensity': 90},  # not team_team
    "garbage entry",
]
app2 = FakeApp(league2, FakeInbox(), FakeHistory([
    {'year': 2025, 'champion': 'Others', 'runner_up': 'Testers'},
    {'year': 2026, 'champion': 'Testers', 'runner_up': 'Rivals'},
]))
app2.game_manager.media_system.storylines = [
    FakeStoryline('Prospect turning heads', 8, active=True),
    FakeStoryline('Old news', 3, active=False),
]
msgs = [
    EmailMessage(sender='League', subject='⭐ Star reaches 1000 points',
                 content='A historic night for the veteran...', category='Media',
                 date_sent=date(2027, 3, 14), game_date_sent=date(2027, 3, 14),
                 is_milestone=True),
    EmailMessage(sender='League', subject='Around the league tonight:',
                 content='Scores from around...', category='League',
                 date_sent=date(2027, 3, 14), game_date_sent=date(2027, 3, 14)),
    EmailMessage(sender='Media', subject='Bad blood brewing in Testers-Rivals',
                 content='The rivalry intensifies...', category='Media',
                 date_sent=date(2027, 3, 10), game_date_sent=date(2027, 3, 10)),
    EmailMessage(sender='Scout', subject='Not a story', content='x',
                 category='Scouting', date_sent=date(2027, 3, 12)),
]
app2.inbox = FakeInbox(msgs)
v2 = make_view(app2)

dev2 = v2._collect_developing()
check("developing collects 4 (2 narr + 1 storyline + 1 rivalry)",
      len(dev2) == 4)
check("developing sorted by heat desc",
      [d['heat'] for d in dev2] == sorted([d['heat'] for d in dev2], reverse=True))
check("rivalry icon is fire", any(d['icon'] == '🔥' for d in dev2))
check("cup_window icon is trophy",
      any(d['icon'] == '🏆' and 'window' in d['title'].lower() for d in dev2))
check("low-heat rivalry excluded",
      not any('Mildfoes' in d['title'] for d in dev2))
check("expired storyline excluded",
      not any('Old news' in d['title'] for d in dev2))

feed2 = v2._collect_story_feed()
check("feed has 3 (Media/League only)", len(feed2) == 3)
check("feed newest first", feed2[0]['date'] >= feed2[-1]['date'])
icons = [f['icon'] for f in feed2]
check("milestone gets star", '⭐' in icons)
check("digest gets globe", '🌐' in icons)
check("rivalry gets fire", '🔥' in icons)

title2, hook2 = v2._story_hook()
check("defending champ hook", "Defending the crown" in hook2)
hist2 = v2._collect_history_lines()
check("history has 2 lines", len(hist2) == 2)
check("own Cup flagged mine", any(h['mine'] for h in hist2))

try:
    v2._populate_season_story()
    check("populate on sample data: no raise", True)
except Exception as e:
    check(f"populate on sample data: no raise ({e})", False)
check("stats label counts",
      "4 developing" in str(v2.stats_label.configured.get('text', ''))
      and "3 moments" in str(v2.stats_label.configured.get('text', '')))
check("story badge count == 4", v2._story_badge_count() == 4)

# --- 4. garbage data: never raises ------------------------------------------
league3 = FakeLeague()
league3.media_narratives = [None, "junk", types.SimpleNamespace()]
league3.rivalries = [None, 42, {'kind': 'team_team'}]
app3 = FakeApp(league3, FakeInbox())
v3 = make_view(app3)
for fn in (v3._collect_developing, v3._collect_story_feed,
           v3._collect_history_lines, v3._story_hook, v3._story_badge_count):
    try:
        fn()
        check(f"garbage: {fn.__name__} no raise", True)
    except Exception as e:
        check(f"garbage: {fn.__name__} no raise ({e})", False)
try:
    v3._populate_season_story()
    check("garbage: populate no raise", True)
except Exception as e:
    check(f"garbage: populate no raise ({e})", False)

# --- 5. filter switching -----------------------------------------------------
v4 = make_view(app2)
v4.email_tree = _StubWidget()
v4.email_tree.get_children = lambda: []
v4._paint_filter_pills = lambda: None
v4._add_message_to_tree = lambda m: None
v4._select_first_message = lambda: None
v4._update_stats = lambda: None
for label, ft in inbox_window.InboxView._FILTERS:
    v4._filter_buttons[ft] = _StubWidget()
try:
    v4._apply_filter('story')
    check("apply story filter: no raise", True)
    check("story filter sets current", v4._current_filter == 'story')
except Exception as e:
    check(f"apply story filter: no raise ({e})", False)
try:
    v4._apply_filter('all')
    check("back to all: no raise", True)
    check("email view restored", v4._current_filter == 'all')
except Exception as e:
    check(f"back to all: no raise ({e})", False)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
