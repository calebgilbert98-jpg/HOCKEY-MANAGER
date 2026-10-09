"""Shared safe-call helper for native UI screens.

Replaces the copy-pasted ``_safe(fn, default)`` wrapper that used to live in
every screen module. Unlike the old version, failures are logged with a
context label so silent UI fallbacks remain diagnosable.
"""

import logging

_logger = logging.getLogger(__name__)


def safe_call(fn, default=None, *, context=""):
    """Call ``fn()`` and return its result, or ``default`` on any exception.

    The exception is logged at ERROR level with the given context so that
    swallowed failures can be traced back to the screen/action that hit them.
    """
    try:
        return fn()
    except Exception:
        _logger.exception(
            "Native UI operation failed%s", f" ({context})" if context else "")
        return default
