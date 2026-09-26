"""Crash-safe checkpoint system for Puck Dynasty.

The problem it solves: a crash mid fantasy-draft (or mid-season) used
to mean starting over. Checkpoints are lightweight, automatic,
rotating snapshots written at the moments that matter most:

    * game start                    -> "Game started"
    * after every Continue (day)    -> "Day <date>"
    * before the fantasy draft      -> "Before Fantasy Draft"
    * every fantasy draft round     -> "Fantasy Draft - Round <n>"
    * trade deadline day            -> "Trade Deadline"

Bounded by design (the "don't overload the save folder" requirement):

    * checkpoints live in ``saves/checkpoints/``, never in ``saves/``
      alongside the player's manual saves;
    * a fixed ring of ``slots`` files (default 5) -- the oldest is
      overwritten, the folder can never grow past
      ``slots`` files + one small ``manifest.json``;
    * writes are atomic (temp file + os.replace) so a crash *during*
      a checkpoint can't corrupt the previous one;
    * the player's manual ``saves/*.hm`` files are never touched.

Crash detection: ``mark_session_start()`` writes ``saves/session.flag``
at launch; ``mark_clean_shutdown()`` removes it on tidy exit. If the
flag is still there at the next launch, the previous session died
uncleanly and the launcher offers one-click recovery from the newest
checkpoint.

Threading: :meth:`CheckpointManager.checkpoint` reads live game objects
via ``create_save_data`` and performs no widget I/O, so it is safe to
call from the Continue handler and draft UI callbacks directly. It may
also run on the multiplayer snapshot worker thread: the host
guarantees (via ``snapshot_busy``) that no other thread mutates game
objects while a snapshot/checkpoint is in flight. Writes are atomic
(temp file + os.replace) either way.

Multiplayer: the host owns checkpointing. Clients are told via
CHECKPOINT_NOTICE so their UI can toast "Host checkpointed".
"""

from __future__ import annotations

import gzip
import json
import os
import pickle
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

CHECKPOINT_DIR = os.path.join("saves", "checkpoints")
MANIFEST_NAME = "manifest.json"
SESSION_FLAG = os.path.join("saves", "session.flag")
DEFAULT_SLOTS = 5


def _utcnow_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


class CheckpointManager:
    """Rotating crash-recovery snapshots. UI-agnostic."""

    def __init__(self,
                 save_manager,
                 slots: int = DEFAULT_SLOTS,
                 checkpoint_dir: str = CHECKPOINT_DIR,
                 game_date_fn: Optional[Callable[[], str]] = None):
        """
        :param save_manager: GameSaveManager -- uses ``create_save_data()``
            for snapshots and ``load_game(path)`` for recovery.
        :param slots: ring size; the folder never holds more than this
            many checkpoint files.
        :param game_date_fn: () -> display string for the manifest
            (e.g. ``lambda: str(gui.current_date)``).
        """
        self._save_manager = save_manager
        self._slots = max(1, int(slots))
        self._dir = checkpoint_dir
        self._game_date_fn = game_date_fn
        os.makedirs(self._dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def checkpoint(self, label: str) -> Optional[str]:
        """Write a checkpoint snapshot. Returns the file path, or None."""
        try:
            data = self._save_manager.create_save_data()
        except Exception:
            return None
        try:
            blob = gzip.compress(
                pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            return None

        manifest = self._read_manifest()
        slot = int(manifest.get("next_slot", 0)) % self._slots
        filename = f"checkpoint_{slot:02d}.hm"
        path = os.path.join(self._dir, filename)

        game_date = ""
        if self._game_date_fn is not None:
            try:
                game_date = str(self._game_date_fn())
            except Exception:
                game_date = ""

        entry = {
            "slot": slot,
            "filename": filename,
            "label": label,
            "game_date": game_date,
            "timestamp": _utcnow_iso(),
            "bytes": len(blob),
            # Monotonic write order: timestamps alone can tie when
            # checkpoints are written within the same second.
            "seq": int(manifest.get("seq", 0)),
        }
        try:
            tmp = path + ".tmp"
            with open(tmp, "wb") as fh:
                fh.write(blob)
            os.replace(tmp, path)  # atomic: crash here keeps old file
        except OSError:
            return None

        entries = [e for e in manifest.get("entries", [])
                   if e.get("slot") != slot]
        entries.append(entry)
        # Enforce the ring even if slots was shrunk between runs.
        entries = sorted(entries,
                         key=lambda e: (e["timestamp"], e.get("seq", 0))
                         )[-self._slots:]
        for stale in self._prune_stale_files({e["filename"] for e in entries}):
            pass
        manifest["entries"] = entries
        manifest["next_slot"] = (slot + 1) % self._slots
        manifest["seq"] = entry["seq"] + 1
        self._write_manifest(manifest)
        return path

    # ------------------------------------------------------------------
    # Reading / recovery
    # ------------------------------------------------------------------

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """Newest-first list of checkpoint entries."""
        manifest = self._read_manifest()
        entries = [e for e in manifest.get("entries", [])
                   if os.path.exists(os.path.join(self._dir, e["filename"]))]
        return sorted(entries,
                      key=lambda e: (e["timestamp"], e.get("seq", 0)),
                      reverse=True)

    def latest(self) -> Optional[Dict[str, Any]]:
        entries = self.list_checkpoints()
        return entries[0] if entries else None

    def recover_latest(self) -> Optional[Dict[str, Any]]:
        """Load the newest checkpoint into the game. Returns its entry."""
        entry = self.latest()
        if entry is None:
            return None
        path = os.path.join(self._dir, entry["filename"])
        try:
            ok = self._save_manager.load_game(path)
        except Exception:
            return None
        return entry if ok else None

    def clear(self) -> None:
        """Delete every checkpoint and reset the manifest."""
        for entry in self._read_manifest().get("entries", []):
            try:
                os.remove(os.path.join(self._dir, entry["filename"]))
            except OSError:
                pass
        self._write_manifest({"entries": [], "next_slot": 0})

    # ------------------------------------------------------------------
    # Manifest helpers (atomic JSON)
    # ------------------------------------------------------------------

    def _manifest_path(self) -> str:
        return os.path.join(self._dir, MANIFEST_NAME)

    def _read_manifest(self) -> Dict[str, Any]:
        try:
            with open(self._manifest_path(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                data.setdefault("entries", [])
                data.setdefault("next_slot", 0)
                return data
        except (OSError, ValueError):
            pass
        return {"entries": [], "next_slot": 0}

    def _write_manifest(self, manifest: Dict[str, Any]) -> None:
        try:
            tmp = self._manifest_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=1)
            os.replace(tmp, self._manifest_path())
        except OSError:
            pass

    def _prune_stale_files(self, live: set) -> List[str]:
        removed = []
        try:
            names = os.listdir(self._dir)
        except OSError:
            return removed
        for name in names:
            if (name.startswith("checkpoint_") and name.endswith(".hm")
                    and name not in live):
                try:
                    os.remove(os.path.join(self._dir, name))
                    removed.append(name)
                except OSError:
                    pass
        return removed


# ----------------------------------------------------------------------
# Session flag: did the last run exit cleanly?
# ----------------------------------------------------------------------

def mark_session_start(flag_path: str = SESSION_FLAG) -> None:
    """Call once at launch. A leftover flag next launch means a crash."""
    try:
        os.makedirs(os.path.dirname(flag_path), exist_ok=True)
        with open(flag_path, "w", encoding="utf-8") as fh:
            json.dump({"pid": os.getpid(), "started_at": _utcnow_iso(),
                       "note": "removed on clean shutdown"}, fh)
    except OSError:
        pass


def mark_clean_shutdown(flag_path: str = SESSION_FLAG) -> None:
    """Call on tidy exit (launcher close / game exit)."""
    try:
        os.remove(flag_path)
    except OSError:
        pass


def previous_session_crashed(flag_path: str = SESSION_FLAG) -> bool:
    """True if the last session did not shut down cleanly."""
    return os.path.exists(flag_path)


def checkpoint_summary(entry: Optional[Dict[str, Any]]) -> str:
    """One-line human description for dialogs and toasts."""
    if entry is None:
        return "no checkpoints available"
    when = entry.get("game_date") or entry.get("timestamp", "?")
    return f"{entry.get('label', 'Checkpoint')} ({when})"
