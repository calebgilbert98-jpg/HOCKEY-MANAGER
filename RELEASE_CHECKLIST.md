# Release Checklist — Puck Dynasty Native

Caleb's rule: **no broken builds reach him.** Every release must pass validation
before it's announced as downloadable.

## Before pushing (pre-push checks)

Run these locally on the `native-ui` branch before `git push`:

- [ ] `python3 -c "import ast; ast.parse(open('puck_dynasty_native.spec').read())"` — spec parses
- [ ] Spec `hiddenimports` includes `collect_submodules('native_ui.screens')` and
      `collect_submodules('native_ui.widgets')` — **this is what broke v0.26.25–27**
      (PyInstaller can't see dynamic `__import__` calls; without this, the exe
      ships with zero screens and the setup wizard never appears)
- [ ] `VERSION` file bumped (e.g. `0.26.28`)
- [ ] No `git add -A` used; `ARTIFACT_TARGET.jpg`, `PORT_GAP_AUDIT_2026-10-06.md`,
      and `telemetry/games.jsonl` are NOT staged
- [ ] Quick smoke: `python3 validate_release.py --smoke-only` passes

## After the workflow completes (pre-announce validation)

The GitHub workflow builds on push. **Do NOT send Caleb the download link until
validation passes.** Run:

```bash
cd ~/workspace/hockey-manager
python3 validate_release.py native-v0.26.28
```

This checks, in order:

| # | Check | What it catches |
|---|-------|-----------------|
| 1 | Release exists, is a **full release** (not draft/prerelease) | The v0.26.19 prerelease incident |
| 2 | Zip size 50–200 MB | Truncated or bloated builds |
| 3 | Zip extracts; `PuckDynasty.exe` exists (≥5 MB); `_internal/` present | Corrupt or malformed bundles |
| 4 | ≥60 screen modules in `_internal/native_ui/screens/` | **The missing-modules bug** (v0.26.25–27 shipped 0 screens) |
| 5 | Linux source smoke test: launch, 61 screens register, setup wizard appears on fresh `GameManager`, hub/roster/standings/inbox instantiate, `run()` setup-branch fires | Logic bugs: V-A1 regressions, registry breakage, navigation failures |

Exit code 0 = safe to announce. Non-zero = do NOT send the link; fix and rebuild.

To reuse a downloaded zip (faster re-runs):

```bash
python3 validate_release.py native-v0.26.28 --skip-download
```

## Common failure modes

### Missing screen modules in the bundle (v0.26.25–27)
**Symptom:** Caleb launches the exe, sees the hub with empty tiles, no setup
wizard, and no tile clicks work.
**Cause:** `MainWindow._register_all_screens` uses dynamic `__import__` with
variable paths. PyInstaller's static analysis can't see them, so the spec's
`hiddenimports` must explicitly include them via
`collect_submodules('native_ui.screens')`.
**Caught by:** check 4 (module count) and check 5 (registry count).

### Prerelease instead of full release (v0.26.19)
**Symptom:** Release doesn't show under the repo's Releases page.
**Cause:** workflow had `prerelease: true`.
**Caught by:** check 1. (Workflow now sets `prerelease: false`.)

### Setup wizard not appearing (V-A1)
**Symptom:** Fresh launch lands on dead hub, no way to start a game.
**Cause:** `run()` only showed setup `if game is None`; the launcher always
passes a `GameManager`, so the branch never fired. Fixed: also check
`getattr(game, "user_team", None) is None`.
**Caught by:** check 5 (setup-branch condition + `show_screen("setup")` widget check).

### Silent nav failures on Windows
**Symptom:** Tile clicks do nothing, no error visible.
**Cause:** spec had `console=False`, so `print()` went nowhere.
**Mitigation:** `_nav_error()` in `main_window.py` writes to
`puck_dynasty_errors.log` next to the exe. If Caleb reports dead clicks,
ask him to attach that file.

## Who runs this

The **Release Validation Bot** (a standing subagent role) is invoked before
every release announcement. It runs `validate_release.py` against the live
GitHub release and reports pass/fail to the parent agent. A failed validation
blocks the "it's live" message to Caleb.
