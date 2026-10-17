# Web UI Screen Worker Spec

Each screen is a self-contained Flask Blueprint in `web_ui/screens/<name>.py`.
Workers create NEW files only — never edit `bridge.py` (the coordinator's
parent owns it) or another worker's files.

## Blueprint pattern

```python
# web_ui/screens/lines.py
"""Lines screen: view/edit line combinations."""
from flask import Blueprint, jsonify, render_template, request
from web_ui.bridge import _web_app_ref, _safe, to_web_player, enqueue_command

bp = Blueprint("lines", __name__)

def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref

@bp.route("/lines")
def lines_page():
    return render_template("lines.html")

@bp.route("/api/lines")
def api_lines():
    live = _live()
    if live is None:
        return jsonify({"lines": []})
    # ... serialize from live game objects, all access via _safe() ...
    return jsonify({"lines": [...]})
```

Rules:
- Every game-object access wrapped in `_safe(lambda: ..., default)` or
  try/except. A screen must NEVER crash the server on weird save data.
- Never touch a Tk widget. Reads only; writes go via
  `enqueue_command(op, **kwargs)` from `web_ui.bridge`.
- Templates go in `web_ui/templates/<name>.html`, JS in
  `web_ui/static/js/<name>.js`, CSS in `web_ui/static/css/<name>.css`.
- Follow the visual language in `hub.css`: `--bg #0a0e14`, `--card`,
  `--accent #3B82F6`, tile/card hover lifts, same topbar with ← Hub back link.
- Test with `python3 -c` mocks like the parent does (see bridge.py tests):
  Flask test_client, assert 200 on page + API routes.

## Screen list (assign one per worker)

CORE GM:
- lines — line combinations (team.lineup dict; read-only v1 + web edit later)
- waivers — waiver wire (app.waiver_list)
- captains — set C/A (team.roster captaincy; command: set_captains)
- trades — trade center (league teams, trade block)
- trade_block — players on the block

PERSONNEL:
- free_agents — UFA/RFA list
- staff — coaches & management (team.staff)
- development — player development (training programs)
- camp — training camp results
- morale — dressing room / morale (team morale data)

LEAGUE:
- standings — league standings (league.standings)
- stats — league leaders (league player stats)
- playoffs — playoff bracket
- calendar — month calendar view
- news — league news (app.news_log)
- history — league history / records

FRONT OFFICE:
- finances — cap, payroll, budgets (salary_cap_system)
- contracts — extensions & offer sheets
- scouting — assignments + reports
- draft — entry draft board

SYSTEM:
- settings — game settings (read-only v1)
- save — save/load (command: save_game / load_game)

Each worker: build the blueprint + template + JS + CSS, test with mocks,
report the files created and test results. Keep each screen focused;
read-only v1 is fine where writes are complex — note what needs a command.
