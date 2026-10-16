"""pytest configuration for the Puck Dynasty test suite (R16a).

Centralises what every test file used to do ad hoc with its own
``sys.path.insert``: the repo root (the checkout these tests live in) goes on
``sys.path`` so ``import daily_news`` etc. resolve against this tree rather
than a hardcoded home-directory path, and Qt is forced offscreen so headless
CI never tries to open a display.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
