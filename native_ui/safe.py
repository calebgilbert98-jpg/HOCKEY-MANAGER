"""Shared safe-call helper for native UI screens.

Replaces the copy-pasted ``_safe(fn, default)`` wrapper that used to live in
every screen module. Unlike the old version, failures are logged with a
context label so silent UI fallbacks remain diagnosable.
"""

import logging

_logger = logging.getLogger(__name__)


def safe_call(fn, default=None, *, context=""):
    """Call ``fn()`` and return its result, or ``default`` on any exception.

    A successful call that returns ``None`` also yields ``default``: UI code
    interpolates these values into labels, and a bare ``None`` would render
    as the literal text "None". Falsy-but-not-None values (0, "", [], False)
    are preserved as-is — only ``None`` maps to ``default``.

    The exception is logged at ERROR level with the given context so that
    swallowed failures can be traced back to the screen/action that hit them.
    """
    try:
        v = fn()
    except Exception:
        _logger.exception(
            "Native UI operation failed%s", f" ({context})" if context else "")
        return default
    return default if v is None else v
