"""Centralized modal dialogs with automation bypass.

Root-cause fix for automation hard-blocks: every QMessageBox / QDialog.exec()
/ QInputDialog call in native_ui goes through these helpers, so a single choke
point honors ``PUCK_DYNASTY_NO_MODAL=1``. Visual test bots and scripted UI
drivers set that env var; real users are unaffected (helpers delegate to the
real Qt calls with identical signatures).

API mirrors the Qt statics so migration is mechanical:
    QMessageBox.information(p, t, m)  ->  modal.information(p, t, m)
    QMessageBox.question(p, t, m)     ->  modal.question(p, t, m)
    dlg.exec()                        ->  modal.exec_dialog(dlg)
    QInputDialog.getText(...)         ->  modal.get_text(...)

Automation behavior (env var set):
  - information / warning / critical: log + return QMessageBox.Ok (no block)
  - question: log + return QMessageBox.No (safe default: do NOT perform the
    action being confirmed; destructive confirms must never auto-accept)
  - exec_dialog: log + return QDialog.Rejected (dialog treated as dismissed)
  - get_text / get_item / get_int: log + return ("", False) / (0, False) so
    the caller takes its cancel path

All wrappers are pass-through (*args/**kwargs), so they accept any signature
the underlying Qt static accepts.
"""
import os

from PySide6.QtWidgets import QDialog, QMessageBox


def automation_bypass():
    """True when scripted UI drivers should skip modal dialogs."""
    return os.environ.get("PUCK_DYNASTY_NO_MODAL") == "1"


def _short(text, n=140):
    try:
        s = str(text).replace("\n", " ")
    except Exception:
        s = "?"
    return s[:n]


def information(parent, title, text, *args, **kwargs):
    if automation_bypass():
        print(f"[modal:auto-skip] info '{title}': {_short(text)}")
        return QMessageBox.Ok
    return QMessageBox.information(parent, title, text, *args, **kwargs)


def warning(parent, title, text, *args, **kwargs):
    if automation_bypass():
        print(f"[modal:auto-skip] warning '{title}': {_short(text)}")
        return QMessageBox.Ok
    return QMessageBox.warning(parent, title, text, *args, **kwargs)


def critical(parent, title, text, *args, **kwargs):
    if automation_bypass():
        print(f"[modal:auto-skip] critical '{title}': {_short(text)}")
        return QMessageBox.Ok
    return QMessageBox.critical(parent, title, text, *args, **kwargs)


def question(parent, title, text, *args, **kwargs):
    """Yes/No confirmation. Under automation returns No (safe default)."""
    if automation_bypass():
        print(f"[modal:auto-skip] question '{title}': {_short(text)} -> No")
        return QMessageBox.No
    return QMessageBox.question(parent, title, text, *args, **kwargs)


def exec_dialog(dlg, name=None):
    """Run a QDialog modally, bypassed under automation.

    Returns the dialog result code. Under automation the dialog is treated
    as dismissed (Rejected) without ever blocking.
    """
    try:
        label = name or _short(dlg.windowTitle())
    except Exception:
        label = "dialog"
    if automation_bypass():
        print(f"[modal:auto-skip] dialog '{label}' not exec'd -> Rejected")
        return QDialog.Rejected
    return dlg.exec()


def get_text(parent, title, label, *args, **kwargs):
    """QInputDialog.getText wrapper. Under automation: cancelled."""
    if automation_bypass():
        print(f"[modal:auto-skip] getText '{title}' -> cancelled")
        return "", False
    from PySide6.QtWidgets import QInputDialog
    return QInputDialog.getText(parent, title, label, *args, **kwargs)


def get_item(parent, title, label, items, *args, **kwargs):
    """QInputDialog.getItem wrapper. Under automation: cancelled."""
    if automation_bypass():
        print(f"[modal:auto-skip] getItem '{title}' -> cancelled")
        return "", False
    from PySide6.QtWidgets import QInputDialog
    return QInputDialog.getItem(parent, title, label, items, *args, **kwargs)


def get_int(parent, title, label, *args, **kwargs):
    """QInputDialog.getInt wrapper. Under automation: cancelled."""
    if automation_bypass():
        print(f"[modal:auto-skip] getInt '{title}' -> cancelled")
        return 0, False
    from PySide6.QtWidgets import QInputDialog
    return QInputDialog.getInt(parent, title, label, *args, **kwargs)


def confirm(parent, title, text):
    """Convenience Yes/No confirm. Returns True if user said Yes."""
    return question(parent, title, text,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No) == QMessageBox.Yes
