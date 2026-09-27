# In-Game Popup System — merge / contributor guide

All dialogs and windows now render **inside** the main window as overlay cards
(FM-style). No more floating OS-level `Toplevel` popups (except tooltips,
toasts, and file pickers — see below).

## What changed

**New file: `popup_system.py`** (~750 lines)
- `PopupManager` — attached to the app root via `register(self)` in
  `HockeyManagerGUI.__init__`. Owns a stack of cards: dimmed backdrop +
  centered card with title bar + ✕. `close_all()` is called on every dashboard
  rebuild (navigating screens dismisses popups, FM behavior).
- `InGamePopup(tk.Frame)` — drop-in replacement for `tk.Toplevel` /
  `ctk.CTkToplevel`. `X(opener, ...)` construction **auto-routes** into a card
  via `__new__`, so call sites needed zero changes — only the base class.
  Emulates the Toplevel API windows actually use: `title()`, `geometry()`,
  `minsize()`, `grab_set()`/`grab_release()` (flips the card modal),
  `protocol("WM_DELETE_WINDOW")`, `destroy()`, `state()`, `lift()`,
  `focus_force()`, `transient()`/`resizable()`/`attributes()` (no-ops —
  meaningless for an in-game card). Card placement is deferred to `after_idle`
  so `title()`/`geometry()` set in `__init__` are picked up.
- `messagebox` / `simpledialog` facades — **identical tkinter signatures**,
  rendered as styled in-game cards, synchronous via `wait_window`. If no
  manager is registered (standalone launchers), they fall back to real
  `tkinter.messagebox`.

**Migrated**
- 445 `messagebox` calls (28 files) + 3 `simpledialog` calls → in-game cards.
- 72 named window classes: `class X(tk.Toplevel)` → `class X(InGamePopup)`.
- 63 anonymous inline `tk.Toplevel(...)` → `InGamePopup(...)` (auto-routed).
- `PBPVisualSim` → `InGamePopup` (the Watch Live visualizer is now a card).

**Deliberately NOT migrated**
- `filedialog` (10 calls) — file picking needs the OS dialog.
- Tooltips (`tooltip.py`, `ui_components.py`) and toast notifications
  (`main.py` x2) — `overrideredirect` floaters, not dialogs.

## Rules for new code

1. **Never** `tk.Toplevel(...)` / `ctk.CTkToplevel(...)` for dialogs or windows.
   Use `InGamePopup(opener)` (auto-routed) or subclass it. `messagebox` /
   `simpledialog` come from `popup_system`, not `tkinter`.
2. A window class must call `super().__init__(parent)` (any position) and must
   **not** define `__new__` — the routing lives there.
3. `grab_set()` = modal card (dims + grabs). No grab = modeless card; the main
   window stays clickable.
4. `wait_window` works on any widget, so modal result-dict patterns are
   unchanged. Escape closes the top card; ✕ honors `WM_DELETE_WINDOW`.
5. Attribute fall-through: unknown attributes on a popup resolve against the
   **app root** (that's how `self.parent.BG_COLOR`-style code keeps working).
   Dangerous Toplevel-isms (`attributes`, `transient`, `resizable`,
   `overrideredirect`, `withdraw`) are shadowed as no-ops so they can't leak
   onto the main window.
6. **Tests:** if you monkeypatch dialogs in a headless test, patch
   `popup_system.messagebox`, not `tkinter.messagebox` — the app no longer
   uses tkinter's. (Patching tkinter's silently stops working and your test
   will hang on a real in-game dialog.)

## QA performed

- `popup_system` unit tests: 15/15 (register, cards, subclass routing,
  all dialog kinds, askstring/askinteger validation, Escape, non-modal,
  WM_DELETE_WINDOW).
- 10 major windows opened via real openers, verified as cards with correct
  titles/sizes; screenshots in `~/workspace/ui-mockups/shot_ingame_cards.png`
  and `shot_ingame_dialog.png`.
- MP suite 12/12, lines smoke 36/36, pressure battery 8/8, headless Watch Live
  game completes inside a card.
