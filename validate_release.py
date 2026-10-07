#!/usr/bin/env python3
"""Release validation bot for Puck Dynasty native builds.

Caleb's requirement: no broken builds reach him. This script validates a
GitHub release BEFORE it's announced as downloadable.

Usage:
    python3 validate_release.py native-v0.26.28
    python3 validate_release.py native-v0.26.28 --skip-download  # use cached zip
    python3 validate_release.py --smoke-only  # just run the Linux source smoke test

Exit code 0 = valid, non-zero = failed (with clear error message).

Checks:
  1. Release exists on GitHub and is a full release (not prerelease/draft)
  2. Windows zip asset exists and is a sane size (50-200 MB)
  3. Zip extracts; PuckDynasty.exe exists; _internal folder exists
  4. Screen modules are bundled (the missing-modules bug that broke v0.26.25-27)
  5. Linux source smoke test: app launches, setup wizard appears, screens register,
     basic navigation works (catches logic bugs before they ship)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPO = "calebgilbert98-jpg/HOCKEY-MANAGER"
API = f"https://api.github.com/repos/{REPO}/releases/tags"
MIN_ZIP_MB = 50
MAX_ZIP_MB = 200
MIN_SCREENS_BUNDLED = 60  # we expect 63+; allow a small margin

# Repo root = directory containing this script.
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# Screens that MUST be registered for the app to function at all.
# Note: "hub" is instantiated directly (self.hub = HubPage), not via the
# lazy _screen_classes registry, so it's checked separately.
CRITICAL_SCREENS = ["setup", "roster", "inbox", "schedule", "standings"]


def fail(msg):
    print(f"VALIDATION FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg):
    print(f"  [ok] {msg}")


def github_api(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "PuckDynasty-ReleaseValidator/1.0",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        fail(f"GitHub API error for {url}: HTTP {e.code}: {body}")
    except Exception as e:
        fail(f"GitHub API request failed for {url}: {e}")


def check_release(tag):
    """Check 1: release exists, is full (not pre/draft), has the zip."""
    print(f"Check 1: release {tag} exists and is a full release...")
    d = github_api(f"{API}/{tag}")
    if d.get("draft"):
        fail(f"{tag} is a DRAFT release, not visible to Caleb")
    if d.get("prerelease"):
        fail(f"{tag} is a PRERELEASE (Caleb requires full visible releases)")
    ok(f"release '{d.get('name')}' is a full release")

    assets = d.get("assets", [])
    zips = [a for a in assets if a["name"].endswith("-Windows.zip")]
    if not zips:
        fail(f"{tag} has no -Windows.zip asset (assets: {[a['name'] for a in assets]})")
    asset = zips[0]
    size_mb = asset["size"] / 1024 / 1024
    ok(f"found asset {asset['name']} ({size_mb:.1f} MB)")
    return asset


def check_asset_size(asset):
    """Check 2: zip size is sane."""
    print("Check 2: asset size is sane...")
    size_mb = asset["size"] / 1024 / 1024
    if size_mb < MIN_ZIP_MB:
        fail(f"zip is only {size_mb:.1f} MB (min {MIN_ZIP_MB}) — build is likely incomplete")
    if size_mb > MAX_ZIP_MB:
        fail(f"zip is {size_mb:.1f} MB (max {MAX_ZIP_MB}) — build is likely bloated/broken")
    ok(f"size {size_mb:.1f} MB within [{MIN_ZIP_MB}, {MAX_ZIP_MB}]")


def download_asset(asset, dest_dir):
    """Download the zip."""
    url = asset["browser_download_url"]
    dest = os.path.join(dest_dir, asset["name"])
    if os.path.exists(dest):
        print(f"  [ok] using cached {dest}")
        return dest
    print(f"Downloading {asset['name']} ({asset['size']/1024/1024:.1f} MB)...")
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as e:
        fail(f"download failed: {e}")
    ok(f"downloaded to {dest}")
    return dest


def check_bundle_contents(zip_path, work_dir):
    """Check 3+4: extract, verify exe, _internal, and bundled screen modules."""
    print("Check 3: bundle structure...")
    extract_dir = os.path.join(work_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
    except Exception as e:
        fail(f"zip extraction failed: {e}")
    ok("zip extracts cleanly")

    # Find the exe (may be nested one level: PuckDynasty/PuckDynasty.exe)
    exe = None
    internal = None
    for root, dirs, files in os.walk(extract_dir):
        if "PuckDynasty.exe" in files:
            exe = os.path.join(root, "PuckDynasty.exe")
            if "_internal" in dirs:
                internal = os.path.join(root, "_internal")
            break
    if not exe:
        fail("PuckDynasty.exe not found anywhere in the zip")
    exe_mb = os.path.getsize(exe) / 1024 / 1024
    ok(f"PuckDynasty.exe found ({exe_mb:.1f} MB)")
    if exe_mb < 5:
        fail(f"exe is only {exe_mb:.1f} MB — build is likely broken")

    if not internal or not os.path.isdir(internal):
        fail("_internal folder missing — PyInstaller bundle is malformed")
    ok("_internal folder present")

    print("Check 4: screen modules are bundled (the v0.26.25-27 bug)...")
    # PyInstaller 6.x with a one-dir COLLECT build embeds pure-Python
    # modules in a PYZ archive *inside the exe itself* (no separate .pyz
    # file, no _internal/native_ui/ directory).  The module names appear
    # uncompressed in the PYZ table of contents, so a byte search of the
    # exe for b'native_ui.screens.<name>' is the reliable detection.
    # (Searching for .pyc files on disk misses PYZ-embedded modules.)
    bundled = 0
    try:
        with open(exe, "rb") as f:
            exe_bytes = f.read()
    except Exception as e:
        fail(f"could not read exe for module scan: {e}")
    # Build the expected module list from the repo source
    expected = set()
    repo_screens = os.path.join(REPO_DIR, "native_ui", "screens")
    repo_widgets = os.path.join(REPO_DIR, "native_ui", "widgets")
    for pkg, d in (("native_ui.screens", repo_screens),
                   ("native_ui.widgets", repo_widgets)):
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.endswith(".py") and fn != "__init__.py":
                    expected.add(f"{pkg}.{fn[:-3]}".encode())
    found = {m.decode() for m in expected if m in exe_bytes}
    bundled = len(found)
    if bundled:
        ok(f"found {bundled}/{len(expected)} screen/widget modules in exe PYZ TOC")
        missing = sorted(m.decode() for m in expected - {m.encode() for m in found})
        if missing:
            print(f"    missing: {', '.join(missing)}")
    if bundled < MIN_SCREENS_BUNDLED:
        fail(
            f"only {bundled} screen modules bundled (need >= {MIN_SCREENS_BUNDLED}). "
            "This is the missing-modules bug: check puck_dynasty_native.spec "
            "hiddenimports includes the _collect_screens() filesystem scan."
        )
    ok(f"screen module count OK ({bundled} >= {MIN_SCREENS_BUNDLED})")
    return True


def run_smoke_test(repo_dir):
    """Check 5: Linux source smoke test with offscreen Qt.

    We can't run the Windows exe on Linux, but we CAN run the same source
    the exe was built from. This catches logic bugs (setup wizard not
    appearing, screens failing to register, navigation broken).
    """
    print("Check 5: Linux source smoke test (offscreen Qt)...")
    smoke_code = '''
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, %r)

# EGL setup (same as visual bots use)
for p in ("/tmp/realegl/usr/lib/x86_64-linux-gnu",
          os.path.expanduser("~/workspace/qt_stubs")):
    if os.path.isdir(p):
        os.environ["LD_LIBRARY_PATH"] = p + ":" + os.environ.get("LD_LIBRARY_PATH", "")
        break

from PySide6.QtWidgets import QApplication
from game_manager import GameManager
from native_ui.main_window import MainWindow, run

errors = []

# 5a. Fresh GameManager has no user team
gm = GameManager()
if getattr(gm, "user_team", None) is not None:
    errors.append("fresh GameManager has user_team set (expected None)")

# 5b. MainWindow registers screens
app = QApplication([])
win = MainWindow(game=gm)
n_registered = len(getattr(win, "_screen_classes", {}))
print(f"SMOKE: {n_registered} screens registered")
if n_registered < 60:
    errors.append(f"only {n_registered} screens registered (need >= 60)")

# 5c. Critical screens present
for s in %r:
    if s not in win._screen_classes:
        errors.append(f"critical screen missing from registry: {s}")

# 5d. Setup wizard appears for fresh game (V-A1)
win.show_screen("setup")
cur = win.stack.currentWidget()
inner = cur.widget() if hasattr(cur, "widget") else cur
cls_name = type(inner).__name__
print(f"SMOKE: setup screen widget = {cls_name}")
if "Setup" not in cls_name:
    errors.append(f"show_screen('setup') did not show setup (got {cls_name})")

# 5e. Hub + roster + standings instantiate without exception
# (hub is direct, not lazy — check it exists as an attribute)
if not hasattr(win, "hub"):
    errors.append("MainWindow.hub missing (HubPage not instantiated)")
for s in ("roster", "standings", "inbox"):
    try:
        win.show_screen(s)
    except Exception as e:
        errors.append(f"show_screen({s!r}) raised: {e}")

# 5f. run() setup-branch condition (mirrors main_window.run logic)
cond = gm is None or getattr(gm, "user_team", None) is None
print(f"SMOKE: setup-branch condition = {cond}")
if not cond:
    errors.append("run() would NOT show setup wizard on fresh launch")

if errors:
    print("SMOKE ERRORS:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(2)
print("SMOKE: all checks passed")
''' % (repo_dir, CRITICAL_SCREENS)

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(smoke_code)
        smoke_path = f.name
    try:
        # Need the real EGL for Qt to import; use LD_PRELOAD-style env
        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = "offscreen"
        egl_dirs = ["/tmp/realegl/usr/lib/x86_64-linux-gnu",
                    os.path.expanduser("~/workspace/qt_stubs")]
        for d in egl_dirs:
            if os.path.isdir(d):
                env["LD_LIBRARY_PATH"] = d + ":" + env.get("LD_LIBRARY_PATH", "")
                break
        r = subprocess.run([sys.executable, smoke_path],
                           capture_output=True, text=True,
                           timeout=300, cwd=repo_dir, env=env)
        print(r.stdout)
        if r.stderr:
            # Filter noise; show real errors
            for line in r.stderr.splitlines():
                if "Error" in line or "error" in line or "Traceback" in line:
                    print(f"  [stderr] {line}")
        if r.returncode != 0:
            fail(f"smoke test exited {r.returncode} — see SMOKE ERRORS above")
    except subprocess.TimeoutExpired:
        fail("smoke test timed out after 300s (app may be hanging on launch)")
    finally:
        os.unlink(smoke_path)
    ok("smoke test passed: launch, setup wizard, screen registry, navigation")


def main():
    ap = argparse.ArgumentParser(description="Validate a Puck Dynasty native release.")
    ap.add_argument("tag", nargs="?", help="release tag, e.g. native-v0.26.28")
    ap.add_argument("--skip-download", action="store_true",
                    help="reuse already-downloaded zip in work dir")
    ap.add_argument("--smoke-only", action="store_true",
                    help="only run the Linux source smoke test")
    ap.add_argument("--work-dir", default="/tmp/release_validation",
                    help="working directory for downloads")
    ap.add_argument("--repo", default=os.path.expanduser("~/workspace/hockey-manager"),
                    help="local repo path for the smoke test")
    args = ap.parse_args()

    if args.smoke_only:
        run_smoke_test(args.repo)
        print("\nVALIDATION PASSED (smoke only)")
        return 0

    if not args.tag:
        ap.error("tag is required (e.g. native-v0.26.28)")

    os.makedirs(args.work_dir, exist_ok=True)
    tag_dir = os.path.join(args.work_dir, args.tag)
    os.makedirs(tag_dir, exist_ok=True)

    asset = check_release(args.tag)
    check_asset_size(asset)
    zip_path = download_asset(asset, tag_dir)
    check_bundle_contents(zip_path, tag_dir)
    run_smoke_test(args.repo)

    print(f"\nVALIDATION PASSED: {args.tag} is safe to announce")
    return 0


if __name__ == "__main__":
    sys.exit(main())
