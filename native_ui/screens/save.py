"""Save / Load screen: real in-page save management -- web parity.

Replicates web_ui/screens/save.py:
- Save button with a name input (Enter in the field = save)
- Save slots list with Load / Delete / Rename / Properties per row;
  double-clicking a row loads it immediately (no confirm)
- Quick-save slots 1-6 (desktop _quick_save_to_slot parity)
- Autosave frequency dropdown (enabled is hard-coded on, exactly like the
  web page -- there is no disable toggle)
- Export: copy a .hm file out via a save dialog
- Import: copy a .hm file in via an open dialog
- Ctrl+S = quick-save (shortcut scoped to this screen; uses the newest
  occupied slot, else the first empty one)
- Properties dialog per save

Calls GameSaveManager directly on the game object (no HTTP, no queue).
Long ops run synchronously with a busy cursor and status feedback, exactly
like the web's poll-until-done flow but without the round trip.
"""
import contextlib
import os
import re
import shutil

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QFrame, QScrollArea, QComboBox, QLineEdit, QDialog,
    QFormLayout, QDialogButtonBox, QFileDialog, QMessageBox, QInputDialog,
    QHeaderView, QAbstractItemView, QGridLayout, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from .base import BaseScreen


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _save_manager(game):
    """GameSaveManager behind the live app (app or game_manager). Web parity
    with bridge._web_save_manager."""
    for fn in (lambda: getattr(game, "save_manager", None),
               lambda: getattr(getattr(game, "game_manager", None),
                               "save_manager", None)):
        sm = _safe(fn)
        if sm is not None:
            return sm
    return None


def _saves_dir(sm):
    """Real saves directory. Web parity with bridge._web_saves_dir."""
    d = getattr(sm, "save_directory", "saves") or "saves"
    return os.path.realpath(d)


def _gm(game):
    """Game manager behind the app, for team/date reads."""
    return getattr(game, "game_manager", None) or game


def _sanitize_name(name):
    """User save name -> 'name.hm'; empty -> None (engine default).
    Web parity with bridge._web_save_filename."""
    name = re.sub(r"[^\w\s\-]", "", str(name or "")).strip()
    name = re.sub(r"\s+", "_", name).strip("_")[:48]
    if not name:
        return None
    if not name.lower().endswith(".hm"):
        name += ".hm"
    return name


def _resolve_save_id(sm, save_id):
    """save_id is a saves-dir-relative path. Returns the real path, or None
    when it escapes the saves directory or isn't a file. Web parity."""
    if sm is None:
        return None
    base = _saves_dir(sm)
    cand = os.path.realpath(os.path.join(base, str(save_id or "")))
    if cand == base or not cand.startswith(base + os.sep):
        return None
    if not os.path.isfile(cand):
        return None
    return cand


@contextlib.contextmanager
def _suppress_tk_popups():
    """Silence tkinter.messagebox during save/load (web parity with
    bridge._web_suppress_tk_popups): failures report in-page, never as
    hidden Tk popups in the Qt process."""
    try:
        import tkinter.messagebox as _mb
    except Exception:
        yield
        return
    _o = (_mb.showerror, _mb.showinfo, _mb.showwarning)
    _mb.showerror = lambda *a, **k: None
    _mb.showinfo = lambda *a, **k: None
    _mb.showwarning = lambda *a, **k: None
    try:
        yield
    finally:
        _mb.showerror, _mb.showinfo, _mb.showwarning = _o


def _fmt_size(size_kb):
    try:
        kb = int(size_kb or 0)
    except Exception:
        return "—"
    if kb >= 1024:
        return f"{kb / 1024:.1f} MB"
    return f"{kb} KB"


_AUTOSAVE_FREQS = [
    ("Every day", 1),
    ("Every 7 days", 7),
    ("Every 14 days", 14),
    ("Every 30 days", 30),
]


class SaveScreen(BaseScreen):
    title = "Save"

    def _build_body(self):
        self._sm = None
        self._rows = []          # list of save dicts backing the table
        self._quick_slots = []   # slot dicts backing the grid

        # --- current game header (web /api/save parity) ---
        info = QFrame()
        info.setObjectName("tile")
        il = QHBoxLayout(info)
        self._info_team = QLabel("")
        self._info_team.setObjectName("tile-title")
        self._info_date = QLabel("")
        self._info_date.setStyleSheet("color: #9aa4b8;")
        il.addWidget(self._info_team, 1)
        il.addWidget(self._info_date)
        self._layout.addWidget(info)

        # --- save row: name input + Save button (Enter = save) ---
        save_row = QFrame()
        save_row.setObjectName("tile")
        sl = QVBoxLayout(save_row)
        sl.addWidget(self._section("SAVE GAME"))
        name_row = QHBoxLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(
            "Save name (optional -- blank uses the default name)")
        self._name_edit.returnPressed.connect(self.do_save)
        name_row.addWidget(self._name_edit, 1)
        self._save_btn = QPushButton("Save Game")
        self._save_btn.setObjectName("primary-btn")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self.do_save)
        name_row.addWidget(self._save_btn)
        sl.addLayout(name_row)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #8a94a8; font-size: 12px;")
        sl.addWidget(self._status)
        self._layout.addWidget(save_row)

        # --- save slots table ---
        list_card = QFrame()
        list_card.setObjectName("tile")
        ll = QVBoxLayout(list_card)
        hdr = QHBoxLayout()
        hdr.addWidget(self._section("SAVED GAMES"))
        hdr.addStretch()
        self._save_count = QLabel("")
        self._save_count.setStyleSheet("color: #8a94a8;")
        hdr.addWidget(self._save_count)
        ll.addLayout(hdr)
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["File", "Team", "Game date", "Modified", "Size", "Type",
             "Actions"])
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        # double-click a row = immediate load, no confirm
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        ll.addWidget(self._table)
        self._auto_line = QLabel("")
        self._auto_line.setStyleSheet("color: #8a94a8; font-size: 12px;")
        ll.addWidget(self._auto_line)
        self._layout.addWidget(list_card, 1)

        # --- quick-save slots ---
        qs_card = QFrame()
        qs_card.setObjectName("tile")
        ql = QVBoxLayout(qs_card)
        ql.addWidget(self._section("QUICK SAVES"))
        self._qs_grid = QGridLayout()
        self._qs_grid.setSpacing(10)
        ql.addLayout(self._qs_grid)
        self._layout.addWidget(qs_card)

        # --- autosave + import ---
        bottom = QHBoxLayout()
        auto_card = QFrame()
        auto_card.setObjectName("tile")
        al = QVBoxLayout(auto_card)
        al.addWidget(self._section("AUTOSAVE"))
        self._auto_status = QLabel("")
        self._auto_status.setStyleSheet("color: #8a94a8; font-size: 12px;")
        al.addWidget(self._auto_status)
        af_row = QHBoxLayout()
        self._auto_freq = QComboBox()
        for label, days in _AUTOSAVE_FREQS:
            self._auto_freq.addItem(label, days)
        af_row.addWidget(self._auto_freq, 1)
        self._auto_btn = QPushButton("Save autosave settings")
        self._auto_btn.setCursor(Qt.PointingHandCursor)
        self._auto_btn.clicked.connect(self.do_autosave_config)
        af_row.addWidget(self._auto_btn)
        al.addLayout(af_row)
        self._auto_note = QLabel("")
        self._auto_note.setStyleSheet("color: #8a94a8; font-size: 12px;")
        al.addWidget(self._auto_note)
        bottom.addWidget(auto_card, 1)

        imp_card = QFrame()
        imp_card.setObjectName("tile")
        il2 = QVBoxLayout(imp_card)
        il2.addWidget(self._section("IMPORT SAVE"))
        il2.addWidget(QLabel("Import copies a .hm file from your computer "
                             "into the saves folder."),
                      )
        imp_row = QHBoxLayout()
        self._imp_btn = QPushButton("Choose .hm file…")
        self._imp_btn.setCursor(Qt.PointingHandCursor)
        self._imp_btn.clicked.connect(self.do_import)
        imp_row.addWidget(self._imp_btn)
        imp_row.addStretch()
        il2.addLayout(imp_row)
        self._imp_note = QLabel("")
        self._imp_note.setStyleSheet("color: #8a94a8; font-size: 12px;")
        il2.addWidget(self._imp_note)
        bottom.addWidget(imp_card, 1)
        self._layout.addLayout(bottom)

        # --- Ctrl+S = quick-save (scoped to this screen) ---
        self._qs_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self._qs_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._qs_shortcut.activated.connect(self.do_ctrl_s_quicksave)

        self.refresh()

    @staticmethod
    def _section(text):
        lab = QLabel(text)
        lab.setObjectName("section-header")
        return lab

    # ------------------------------------------------------------------
    # data loading
    # ------------------------------------------------------------------
    def refresh(self):
        self._sm = _save_manager(self.game)
        self._load_header()
        self._load_saves()
        self._load_quick_slots()
        self._load_autosave()

    def _load_header(self):
        gm = _gm(self.game)
        cur = _safe(lambda: getattr(gm, "current_date", None))
        date_str = _safe(lambda: cur.strftime("%B %d, %Y")) if cur else None
        team = _safe(lambda: getattr(getattr(self.game, "user_team", None),
                                     "team_name", None))
        self._info_team.setText(team or "No team")
        self._info_date.setText(date_str or "")

    def _load_saves(self):
        """Rebuild the save table (web /api/save/list parity)."""
        self._rows = []
        sm = self._sm
        if sm is not None:
            try:
                base = _saves_dir(sm)
                files = _safe(lambda: sm.get_save_files(), []) or []
                for f in files:
                    try:
                        if not isinstance(f, dict):
                            continue
                        fp = f.get("filepath", "") or ""
                        rel = os.path.relpath(fp, base) if fp else ""
                        mod = f.get("modified")
                        mod_s = (mod.strftime("%Y-%m-%d %H:%M")
                                 if hasattr(mod, "strftime")
                                 else str(mod or ""))
                        self._rows.append({
                            "id": rel,
                            "filename": str(f.get("filename", "")),
                            "team": str(f.get("team", "Unknown") or "Unknown"),
                            "game_date": str(f.get("game_date", "Unknown")
                                             or "Unknown"),
                            "modified": mod_s,
                            "size_kb": int((f.get("size") or 0) // 1024),
                            "is_autosave": bool(f.get("is_autosave")),
                            "category": str(f.get("category", "General")
                                            or "General"),
                            "description": str(f.get("description", "") or ""),
                        })
                    except Exception:
                        continue
            except Exception:
                pass
        self._rows.sort(key=lambda r: r["modified"], reverse=True)

        t = self._table
        t.setRowCount(0)
        t.setRowCount(len(self._rows))
        for i, s in enumerate(self._rows):
            t.setItem(i, 0, QTableWidgetItem(s["filename"]))
            t.setItem(i, 1, QTableWidgetItem(s["team"]))
            t.setItem(i, 2, QTableWidgetItem(s["game_date"]))
            t.setItem(i, 3, QTableWidgetItem(s["modified"]))
            t.setItem(i, 4, QTableWidgetItem(_fmt_size(s["size_kb"])))
            badge = QLabel("AUTO" if s["is_autosave"] else "MANUAL")
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                "font-size: 11px; font-weight: 800; padding: 3px 8px; "
                "border-radius: 4px; background-color: %s; color: #0b0f1a;"
                % ("#ffc857" if s["is_autosave"] else "#3B82F6"))
            t.setCellWidget(i, 5, badge)
            t.setCellWidget(i, 6, self._action_buttons(i))
        self._save_count.setText(
            f"({len(self._rows)})" if self._rows else "")

        auto = self._autosave_info()
        self._auto_line.setText(
            ("Autosave: On (every %s days)%s" % (
                auto.get("frequency_days") or "?",
                (" · last " + auto["last"]) if auto.get("last") else ""))
            if auto.get("enabled") else "Autosave: Off")

    def _autosave_info(self):
        sm = self._sm
        if sm is None:
            return {"enabled": False}
        last_auto = _safe(lambda: sm.last_autosave)
        return {
            "enabled": bool(_safe(lambda: sm.autosave_enabled, False)),
            "frequency_days": int(_safe(lambda: sm.autosave_frequency, 0)
                                  or 0),
            "last": (last_auto.strftime("%Y-%m-%d %H:%M")
                     if hasattr(last_auto, "strftime") else None),
        }

    def _load_quick_slots(self):
        """6 quick-save slots (web /api/save/quick_slots parity)."""
        self._quick_slots = []
        sm = self._sm
        if sm is not None:
            try:
                import datetime as _dt
                qdir = os.path.join(_saves_dir(sm), "QuickSaves")
                for i in range(1, 7):
                    fp = os.path.join(qdir, f"QuickSave_Slot_{i}.hm")
                    slot = {"slot": i, "name": f"Quick Save {i}",
                            "occupied": False, "modified": None,
                            "team": None, "game_date": None}
                    if os.path.exists(fp):
                        try:
                            st = os.stat(fp)
                            mod = _dt.datetime.fromtimestamp(st.st_mtime)
                            meta = _safe(
                                lambda: sm._load_save_metadata(fp), {}) or {}
                            slot.update(
                                occupied=True,
                                modified=mod.strftime("%Y-%m-%d %H:%M"),
                                team=str(meta.get("user_team", "Unknown")
                                         or "Unknown"),
                                game_date=str(meta.get("game_date", "") or ""),
                                size_kb=int(st.st_size // 1024),
                            )
                        except Exception:
                            slot["occupied"] = True
                    self._quick_slots.append(slot)
            except Exception:
                pass
        while self._qs_grid.count():
            w = self._qs_grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for col, s in enumerate(self._quick_slots):
            card = QFrame()
            card.setObjectName("tile")
            cl = QVBoxLayout(card)
            head = QLabel(f"Slot {s['slot']}")
            head.setObjectName("tile-title")
            cl.addWidget(head)
            if s["occupied"]:
                meta = QLabel(
                    f"{s.get('game_date') or ''}\n"
                    f"{s.get('modified') or ''}".strip())
            else:
                meta = QLabel("Empty")
            meta.setStyleSheet("color: #8a94a8; font-size: 12px;")
            cl.addWidget(meta)
            btn = QPushButton(
                "Overwrite quick-save" if s["occupied"]
                else "Quick-save here")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, slot=s["slot"]: self.do_quicksave(slot))
            cl.addWidget(btn)
            self._qs_grid.addWidget(card, 0, col)

    def _load_autosave(self):
        auto = self._autosave_info()
        freq = auto.get("frequency_days") or 7
        idx = self._auto_freq.findData(freq)
        self._auto_freq.setCurrentIndex(idx if idx >= 0 else 1)
        self._auto_status.setText(
            "Currently: %s" % ("On (every %s days)" % freq
                               if auto.get("enabled") else "Off"))

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _action_buttons(self, row):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)
        for label, handler in (
                ("Load", lambda r=row: self.do_load_confirm(r)),
                ("Rename", lambda r=row: self.do_rename(r)),
                ("Properties", lambda r=row: self.do_properties(r)),
                ("Export", lambda r=row: self.do_export(r)),
                ("Delete", lambda r=row: self.do_delete(r))):
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            if label == "Delete":
                b.setStyleSheet("color: #ff6b6b;")
            b.clicked.connect(handler)
            lay.addWidget(b)
        return w

    def _busy(self, fn):
        """Run a save-system op with busy cursor + exception guard."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return fn()
        finally:
            QApplication.restoreOverrideCursor()

    def _note(self, msg):
        self._status.setText(msg)

    def do_save(self):
        """Save button / Enter in the name field (web doSave parity)."""
        sm = self._sm
        if sm is None:
            self._note("Save system unavailable.")
            return
        fname = _sanitize_name(self._name_edit.text())
        self._save_btn.setEnabled(False)
        self._note("Saving…")
        try:
            def _op():
                with _suppress_tk_popups():
                    return bool(sm.save_game(fname))
            ok = self._busy(_op)
            self._note("Game saved." if ok else
                       "Save failed — details in save_crash_log.txt inside "
                       "the saves folder.")
            if ok:
                self._name_edit.clear()
                self.refresh()
        except Exception as e:
            self._note(f"Save failed: {e}")
        finally:
            self._save_btn.setEnabled(True)

    def do_load_confirm(self, row):
        """Load button: confirm first (web doLoad parity)."""
        if not (0 <= row < len(self._rows)):
            return
        s = self._rows[row]
        ans = QMessageBox.question(
            self, "Load game",
            f'Load "{s["filename"]}"? Any unsaved progress will be lost.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        self._do_load(s)

    def _on_row_double_clicked(self, row, _col):
        """Double-click a row = immediate load, no confirm."""
        if 0 <= row < len(self._rows):
            self._do_load(self._rows[row])

    def _do_load(self, s):
        sm = self._sm
        if sm is None:
            self._note("Save system unavailable.")
            return
        path = _resolve_save_id(sm, s["id"])
        if not path:
            self._note("Unknown save file.")
            return
        self._note(f'Loading "{s["filename"]}"…')

        def _op():
            with _suppress_tk_popups():
                ok = bool(sm.load_game(path))
            if ok:
                hook = getattr(_gm(self.game), "on_game_loaded", None)
                if hook is None:
                    hook = getattr(self.game, "on_game_loaded", None)
                if callable(hook):
                    try:
                        hook()
                    except Exception as he:
                        print(f"[save] load post-hook: {he}")
            return ok

        try:
            ok = self._busy(_op)
        except Exception as e:
            self._note(f"Load failed: {e}")
            return
        self._note("Game loaded." if ok else
                   "Load failed — the save may be from an incompatible "
                   "version.")
        if ok:
            self.refresh()
            try:
                self.main_window.refresh()
            except Exception:
                pass

    def do_delete(self, row):
        if not (0 <= row < len(self._rows)):
            return
        s = self._rows[row]
        ans = QMessageBox.question(
            self, "Delete save",
            f'Delete "{s["filename"]}" permanently?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        sm = self._sm
        path = _resolve_save_id(sm, s["id"]) if sm else None
        if not path:
            self._note("Unknown save file.")
            return
        self._note(f'Deleting "{s["filename"]}"…')
        try:
            os.remove(path)
            self._note("Save deleted.")
            self._load_saves()
        except Exception as e:
            self._note(f"Delete failed: {e}")

    def do_rename(self, row):
        if not (0 <= row < len(self._rows)):
            return
        s = self._rows[row]
        sm = self._sm
        path = _resolve_save_id(sm, s["id"]) if sm else None
        if not path:
            self._note("Unknown save file.")
            return
        base_name = s["filename"]
        if base_name.lower().endswith(".hm"):
            base_name = base_name[:-3]
        name, ok = QInputDialog.getText(
            self, "Rename save", f'Rename "{s["filename"]}":',
            QLineEdit.Normal, base_name)
        if not ok or not name.strip():
            return
        new = _sanitize_name(name)
        if not new:
            self._note("Invalid name.")
            return
        dest = os.path.join(os.path.dirname(path), new)
        if not dest.startswith(_saves_dir(sm) + os.sep):
            self._note("Invalid name.")
            return
        if os.path.exists(dest):
            self._note(f"{new} already exists.")
            return
        try:
            os.rename(path, dest)
            self._note(f"Renamed to {new}.")
            self._load_saves()
        except Exception as e:
            self._note(f"Rename failed: {e}")

    def do_properties(self, row):
        if not (0 <= row < len(self._rows)):
            return
        s = self._rows[row]
        sm = self._sm
        path = _resolve_save_id(sm, s["id"]) if sm else None
        props = dict(s)
        if sm is not None and path:
            try:
                import datetime as _dt
                meta = _safe(lambda: sm._load_save_metadata(path),
                             {}) or {}
                st = os.stat(path)
                props.update(
                    filename=os.path.basename(path),
                    team=str(meta.get("user_team", "Unknown") or "Unknown"),
                    game_date=str(meta.get("game_date", "") or ""),
                    modified=_dt.datetime.fromtimestamp(
                        st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    size_kb=int(st.st_size // 1024),
                    category=str(meta.get("category", "General")
                                 or "General"),
                    description=str(meta.get("description", "") or ""),
                    is_autosave=bool(meta.get("is_autosave")),
                )
            except Exception:
                pass
        dlg = QDialog(self)
        dlg.setWindowTitle("Save properties")
        dlg.setMinimumWidth(420)
        form = QFormLayout(dlg)
        title = QLabel("Save properties")
        title.setObjectName("dialog-title")
        form.addRow(title)
        rows = [
            ("Filename", props.get("filename", "")),
            ("Team", props.get("team") or "—"),
            ("Game date", props.get("game_date") or "—"),
            ("Modified", props.get("modified") or "—"),
            ("Size", _fmt_size(props.get("size_kb"))),
            ("Type", "Autosave" if props.get("is_autosave") else "Manual"),
            ("Category", props.get("category") or "General"),
        ]
        if props.get("description"):
            rows.append(("Description", props["description"]))
        for k, v in rows:
            form.addRow(k + ":", QLabel(str(v)))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dlg.accept)
        form.addRow(buttons)
        dlg.exec()

    def do_export(self, row):
        """Copy the .hm out via a save dialog (web /api/save/export parity)."""
        if not (0 <= row < len(self._rows)):
            return
        s = self._rows[row]
        sm = self._sm
        path = _resolve_save_id(sm, s["id"]) if sm else None
        if not path:
            self._note("Unknown save file.")
            return
        dest, _flt = QFileDialog.getSaveFileName(
            self, "Export save", s["filename"],
            "Puck Dynasty saves (*.hm)")
        if not dest:
            return
        try:
            shutil.copy(path, dest)
            self._note(f'Exported to {os.path.basename(dest)}.')
        except Exception as e:
            self._note(f"Export failed: {e}")

    def do_import(self):
        """Copy a .hm file in via an open dialog (web /api/save/import)."""
        sm = self._sm
        if sm is None:
            self._imp_note.setText("Save system unavailable.")
            return
        src, _flt = QFileDialog.getOpenFileName(
            self, "Import save", "", "Puck Dynasty saves (*.hm)")
        if not src:
            return
        fname = os.path.basename(src)
        if not fname.lower().endswith(".hm"):
            self._imp_note.setText("Only .hm save files can be imported.")
            return
        safe = "".join(
            c for c in fname if c.isalnum() or c in "._- ")[:80]
        if not safe:
            self._imp_note.setText("Bad filename.")
            return
        dest = os.path.join(_saves_dir(sm), safe)
        if os.path.exists(dest):
            self._imp_note.setText(f"{safe} already exists.")
            return
        self._imp_note.setText("Importing…")
        try:
            shutil.copy(src, dest)
            self._imp_note.setText("Imported.")
            self._load_saves()
        except Exception as e:
            self._imp_note.setText(f"Import failed: {e}")

    def do_quicksave(self, slot):
        """Quick-save into slot 1-6 (desktop _quick_save_to_slot parity)."""
        sm = self._sm
        if sm is None:
            self._note("Save system unavailable.")
            return
        slot = max(1, min(6, int(slot or 1)))
        self._note(f"Quick-saving to slot {slot}…")
        qdir = os.path.join(_saves_dir(sm), "QuickSaves")
        try:
            os.makedirs(qdir, exist_ok=True)
            slot_name = f"QuickSave_Slot_{slot}"
            fp = os.path.join(qdir, slot_name + ".hm")

            def _op():
                with _suppress_tk_popups():
                    return bool(sm.save_enhanced_game(
                        slot_name + ".hm", True,
                        {"description": f"Quick Save Slot {slot}",
                         "category": "QuickSaves",
                         "include_stats": True,
                         "screenshot": False,
                         "slot_number": slot},
                        fp))
            ok = self._busy(_op)
        except Exception as e:
            self._note(f"Quick-save failed: {e}")
            return
        self._note(f"Quick-saved to slot {slot}." if ok
                   else "Quick-save failed.")
        if ok:
            self._load_quick_slots()
            self._load_saves()
            self._load_header()

    def do_ctrl_s_quicksave(self):
        """Ctrl+S: newest occupied slot, else the first empty one
        (web keydown-handler parity)."""
        occupied = [s for s in self._quick_slots if s.get("occupied")]
        if occupied:
            occupied.sort(key=lambda s: s.get("modified") or "",
                          reverse=True)
            self.do_quicksave(occupied[0]["slot"])
            return
        empty = [s for s in self._quick_slots if not s.get("occupied")]
        if empty:
            self.do_quicksave(empty[0]["slot"])
        else:
            self._note("No quick-save slots available.")

    def do_autosave_config(self):
        """Set autosave frequency. Enabled is hard-coded True (web parity:
        the web page always posts enabled=true and offers no disable)."""
        sm = self._sm
        if sm is None:
            self._auto_note.setText("Save system unavailable.")
            return
        freq = int(self._auto_freq.currentData() or 7)
        if not 0 <= freq <= 365:
            self._auto_note.setText("Frequency must be 0-365 days.")
            return
        self._auto_note.setText("Saving…")
        try:
            sm.autosave_enabled = True
        except Exception:
            pass
        try:
            sm.autosave_frequency = max(0, freq)
        except Exception:
            pass
        self._auto_note.setText("Autosave settings updated.")
        self._load_saves()
        self._load_autosave()
