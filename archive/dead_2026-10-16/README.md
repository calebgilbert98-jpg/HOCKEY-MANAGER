# dead_2026-10-16 — removed by roadmap item R17 ("Remove dead code")

- `native_ui_v2/` — orphaned second native-UI attempt (108K). Only referenced
  by the non-entry `puck_dynasty_v2.py` and its own docstrings; nothing live
  imported it.
- `puck_dynasty_v2.py` / `puck_dynasty_v2.spec` — launcher + PyInstaller spec
  for the orphaned native_ui_v2 tree.
- `sim_integrity.py` — standalone script; nothing in the repo imports it.
- `web_ui/` — the Flask tile frontend (14M). All native_ui screens were
  already ported to call the game object directly; the only live residue was
  three helpers (`to_web_team`, `TEAM_ABBR`, `_clean_position` from
  `bridge.py`), extracted verbatim into `native_ui/utils.py` (R17). The
  legacy Tkinter entry `main.py` still contains guarded `web_ui` imports
  (try/except ImportError -> `_direct_launch()` fallback), so it degrades
  gracefully without the web UI — no native_ui module imports web_ui.
  The 20 player portraits from `web_ui/static/img/portraits/` were live assets
  used by `native_ui/screens/player_profile.py` and were relocated to
  `assets/web_portraits/` instead of being archived. Everything else in
  web_ui/ (Flask server, templates, static JS/CSS, bridge command queue)
  had no live importers.
