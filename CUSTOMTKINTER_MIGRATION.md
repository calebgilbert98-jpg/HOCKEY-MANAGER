# CustomTkinter Migration Guide — Puck Dynasty

CustomTkinter 6.x gives the app genuinely modern widgets (rounded buttons,
hover states, styled dropdowns/scrollbars) that ttk can never match no matter
how we recolor it. This doc records the proof-of-concept (Trade Center) and
the playbook for the rest.

## Status

| Screen | Status |
|---|---|
| Trade Center (`windows.py::TradeWindow`) | **Done** — full CTk rebuild |
| Line editor (`main.py::CleanEditLinesWindow`) | **Done** — full CTk rebuild, drag-and-drop preserved |
| Roster (`windows.py::RosterWindow`) | **Done** — CTk chrome + styled dark treeviews |
| Free Agency (`windows.py::FreeAgencyWindow`) | **Done** — CTk rebuild, dialogs modernized |
| Dashboard controls (`dashboard_home.py`, `main.py` nav pills) | **Done** — CTk dropdowns/buttons/nav pills; cards unchanged |
| Draft (`windows.py::DraftWindow`) | **Done** — CTk rebuild, styled board/ticker/shortlist, pill filters, CTk trade/grades dialogs |
| Schedule (`windows.py::ScheduleWindow`) | **Done** — CTk rebuild, tabbed my-team/league tables, month combo, win/loss/today row tags; also fixed pre-existing broken game-selection key (selection never resolved) |
| Finances (`windows.py::FinancesWindow`) | **Done** — CTk rebuild, 5 CTkTabview tabs, stat cards with color-coded money, pill cap-utilization meter, dark treeviews with contract-status tags, CTkComboBox year picker, segmented report picker |
| Inbox (`inbox_window.py::InboxWindow`) | **Done** — CTk rebuild, two-row filter pills with unread badges, dark treeview with unread/urgent/overdue row tags, dark CTkTextbox preview pane, docked toolbar |
| News (`windows.py::NewsWindow`) | **Done** — CTk rebuild, two-pane article cards + reading pane, category pill filters with keyword categorization, search, emoji stripping; also fixed pre-existing `populate_news` AttributeError (main.add_news called a method that didn't exist) |
| Everything else | Pending (priority order below) |

## Theme setup

1. `pip install customtkinter` — already in `requirements.txt`
   (`customtkinter>=5.2.0`) and in `puck_dynasty.spec` hiddenimports, so the
   .exe bundles it (CTk also ships its own PyInstaller hook).
2. Call once at startup, before any CTk window is created:
   ```python
   from ctk_theme import init_ctk_theme
   init_ctk_theme()
   ```
   This sets dark appearance mode and loads
   `assets/puck_dynasty_theme.json` (teal `#00ceb8` accents on charcoal
   `#0e0e11`/`#16161a`/`#1e1e24`). The path resolves both in the dev tree
   and in the PyInstaller bundle (`sys._MEIPASS`). If the JSON is missing it
   degrades gracefully to the built-in dark theme.
3. Prefer the `ctk_theme` factories over raw CTk widgets for consistency:
   `primary_button()` (teal), `secondary_button()` (dark), `heading()`,
   `body()`. Palette constants (`TEAL`, `BG`, `PANEL`, `CARD`, `BORDER`,
   `TEXT`, `TEXT_DIM`, `GOLD`, `GREEN`, `RED`, `BLUE`) mirror `modern_ui.py`.

## Widget mapping (ttk → CTk)

| Old | New | Notes |
|---|---|---|
| `tk.Toplevel` | `ctk.CTkToplevel` | Same geometry/title API. Accepts a plain `tk.Tk` parent — no CTk root required. |
| `ttk.Frame` | `ctk.CTkFrame` | `fg_color`, `corner_radius` instead of styles. `"transparent"` fg works for nesting. |
| `ttk.Label` | `ctk.CTkLabel` | `text_color=` instead of `foreground=`. Use `heading()`/`body()` helpers. |
| `ttk.Button` | `ctk.CTkButton` | Use `primary_button()` / `secondary_button()`. Rounded + hover built in. |
| `ttk.Combobox` | `ctk.CTkComboBox` | `values=[...]`, `command=lambda v: ...` (fires on selection), `.get()`/`.set()`. No `textvariable` needed. |
| `ttk.Entry` | `ctk.CTkEntry` | `placeholder_text=` supported natively. |
| `tk.Listbox` | `ctk_theme.CTkOfferList` | Custom selectable list (CTk has no Listbox). `.set_items([...])`, `.get_selected_index()`. |
| `ttk.Treeview` | `ctk_theme.CTkPlayerList` | Custom roster list with name/position/color-coded OVR rows. `.set_players([...])`, `.get_selected()`. For multi-column stat tables, either extend CTkPlayerList or keep a styled ttk.Treeview (see gotchas). |
| `ttk.PanedWindow` | — | No CTk equivalent. Use `CTkFrame` + `grid()` with `grid_columnconfigure(weight=...)`. |
| `ttk.Progressbar` | `ctk.CTkProgressBar` | Pill-shaped by default via theme. |
| `ttk.Notebook` | `ctk.CTkTabview` / `ctk.CTkSegmentedButton` | SegmentedButton looks far more modern; Tabview is the drop-in. |
| `tk.Canvas` (custom drawing) | keep `tk.Canvas` | Meters, rink art, custom gauges stay on tk.Canvas — CTk has no canvas and plain canvas works fine inside CTk containers. |
| `messagebox.*` | keep `tkinter.messagebox` | Works alongside CTk. (Long-term: build a CTk styled dialog.) |
| `tk.Menu` / menubar | keep `tk.Menu` | CTk has no menu widget. Style is OS-native; acceptable. |

## Gotchas hit during the Trade Center migration

1. **CTkToplevel + mock/test parents.** `tk.Toplevel.__init__` walks
   `master._root()`. A `unittest.mock.MagicMock` parent sends this into an
   infinite loop inside mock's magic-method setup. Tests must pass a real tk
   widget as parent. (Not an app bug — the real parent is always a tk widget.)
2. **Never name a test/script file after a stdlib module** (`bisect.py`,
   `random.py`, …). `customtkinter → PIL → tempfile → random → bisect` will
   import YOUR file instead and die with a confusing "partially initialized
   module" circular-import error.
3. **CTkScrollableFrame as a layout container.** Packing children directly
   into it works, and it solves overflow (the deal panel scrolls so Propose
   Trade is always reachable). Give it an explicit `height=` or it collapses.
4. **ComboBox callback signature.** `command=` receives the selected value
   (unlike `<<ComboboxSelected>>` which receives an event). `lambda v: ...`
   or a one-arg method.
5. **No `textvariable`/`foreground`/`background` kwargs.** CTk uses
   `fg_color`, `text_color`, `hover_color`. Old ttk style names
   (`'Panel.TFrame'` etc.) do nothing on CTk widgets — set colors directly.
6. **Env quirk (dev VM only):** `pip install` needed `--break-system-packages`
   (PEP 668). CI installs from requirements.txt, unaffected.
7. **Fonts.** The theme JSON sets Segoe UI as the CTk default font on
   Windows/Linux. Explicit `font=("Segoe UI", size, "bold")` still works
   per-widget for headings.
8. **Mixed tk/CTk is fine.** `tk.Canvas`, `tk.Menu`, `messagebox`, and the
   branded `SlimBanner` (tk.Frame) all live happily inside CTk containers.

## Priority order for remaining screens

1. **Line editor** (`main.py::CleanEditLinesWindow`) — most-used screen,
   already dark but still ttk; biggest visual win after Trade Center.
2. **Roster window** (`windows.py`) — heavy treeview use; needs the
   multi-column story (extend CTkPlayerList or styled ttk.Treeview).
3. **Free Agency** (`windows.py`) — similar table + offer UI to Trade Center.
4. **Dashboard home** (`dashboard_home.py`) — cards are already custom-drawn;
   convert controls/buttons to CTk for consistent hover/rounding.
5. **Draft** (`windows.py::DraftWindow`) — tables + pick cards.
6. **Dialogs** (extension negotiation, counter-offer pattern, settings) —
   small, quick wins; good candidates for a shared `CTkDialog` helper.
7. **Everything else** (Schedule, Finances, News, Staff, Scouting, …) —
   convert opportunistically when touched.

## Non-goals

- Do NOT convert the live game visualizer (`pbp_visual_sim.py`) — it's
  canvas-drawn broadcast graphics; CTk adds nothing there.
- Do NOT convert `GAME_VIEWER.py` for the same reason.
- Keep `modern_ui.py`'s `AppButton`/`AppCard` for the dashboard until the
  dashboard itself migrates; don't mix both systems on one screen.

## Preview

`docs/trade_center_ctk_preview.png` — screenshot of the rebuilt Trade Center.
