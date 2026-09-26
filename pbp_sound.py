"""Procedural crowd/arena sounds for the Puck Dynasty visual simulator.

Everything here is best-effort and silent-safe: if no audio backend is
available (headless server, missing player), all calls are no-ops and
never raise. Sounds are synthesized once with the stdlib `wave` module
(no numpy needed) and played through the first working backend:

  simpleaudio -> pygame.mixer -> aplay (Linux) -> afplay (macOS) ->
  winsound (Windows) -> silent

Usage:
    from pbp_sound import SoundEngine
    sfx = SoundEngine(enabled=True)
    sfx.goal_horn()   # non-blocking
"""

import io
import math
import os
import struct
import subprocess
import sys
import tempfile
import threading
import wave

_RATE = 44100


def _envelope(n, attack=0.05, release=0.25):
    a = max(1, int(n * attack))
    r = max(1, int(n * release))
    env = [1.0] * n
    for i in range(a):
        env[i] = i / a
    for i in range(r):
        env[n - 1 - i] *= i / r
    return env


def _horn_wav():
    """2s arena goal horn: stacked low brass-ish tones with vibrato."""
    dur, n = 2.0, int(_RATE * 2.0)
    env = _envelope(n, attack=0.03, release=0.35)
    freqs = (174.0, 220.0, 261.6)  # F3 A3 C4-ish power chord
    out = bytearray()
    for i in range(n):
        t = i / _RATE
        vib = 1.0 + 0.006 * math.sin(2 * math.pi * 5.5 * t)
        s = 0.0
        for j, f in enumerate(freqs):
            s += math.sin(2 * math.pi * f * vib * t) / (j + 1)
            s += 0.35 * math.sin(2 * math.pi * 2 * f * vib * t) / (j + 1)
        s = s / 2.2 * env[i] * 0.85
        out += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
    return _to_wav_bytes(bytes(out))


def _crowd_wav(swell=True):
    """2.5s crowd: filtered noise that swells then settles."""
    dur, n = 2.5, int(_RATE * 2.5)
    env = _envelope(n, attack=0.12 if swell else 0.03, release=0.45)
    out = bytearray()
    # cheap low-pass via moving average of pseudo-random noise
    import random
    rnd = random.Random(7)
    prev = 0.0
    for i in range(n):
        raw = rnd.uniform(-1.0, 1.0)
        prev = prev * 0.94 + raw * 0.06  # muffled roar
        # whistle-ish shimmer on top
        t = i / _RATE
        shimmer = 0.06 * math.sin(2 * math.pi * 1180 * t) * env[i]
        s = (prev * 2.4 + shimmer) * env[i] * 0.5
        out += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
    return _to_wav_bytes(bytes(out))


def _whistle_wav():
    """0.7s referee whistle: 2.2kHz with fast trill."""
    n = int(_RATE * 0.7)
    env = _envelope(n, attack=0.02, release=0.2)
    out = bytearray()
    for i in range(n):
        t = i / _RATE
        trill = 1.0 + 0.03 * math.sin(2 * math.pi * 28 * t)
        s = math.sin(2 * math.pi * 2200 * trill * t) * env[i] * 0.4
        out += struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
    return _to_wav_bytes(bytes(out))


def _to_wav_bytes(frames):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_RATE)
        w.writeframes(frames)
    return buf.getvalue()


def _which(cmd):
    for p in os.environ.get("PATH", "").split(os.pathsep):
        full = os.path.join(p, cmd)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
    return None


class SoundEngine:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._cache = {}
        self._player = self._detect_player()

    # -- backend detection ------------------------------------------------
    def _detect_player(self):
        try:
            import simpleaudio as sa  # type: ignore
            return lambda path: sa.WaveObject.from_wave_file(path).play()
        except Exception:
            pass
        try:
            import pygame  # type: ignore
            try:
                pygame.mixer.init()
                return lambda path: pygame.mixer.Sound(path).play()
            except Exception:
                pass
        except Exception:
            pass
        aplay = _which("aplay")
        if aplay:
            return lambda path: subprocess.Popen(
                [aplay, "-q", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        afplay = _which("afplay")
        if afplay:
            return lambda path: subprocess.Popen(
                [afplay, path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if sys.platform == "win32":
            try:
                import winsound  # type: ignore
                return lambda path: winsound.PlaySound(
                    path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception:
                pass
        return None

    @property
    def available(self):
        return self._player is not None

    # -- public API (all non-blocking, never raise) ------------------------
    def goal_horn(self):
        self._play("horn", _horn_wav)
        # crowd swells right under the horn
        self._play("crowd", _crowd_wav)

    def crowd_swell(self):
        self._play("crowd", _crowd_wav)

    def whistle(self, count=1):
        def _seq():
            for _ in range(max(1, count)):
                self._play("whistle", _whistle_wav)
                import time
                time.sleep(0.85)
        threading.Thread(target=_seq, daemon=True).start()

    # -- internals ----------------------------------------------------------
    def _wav(self, name, synth):
        if name not in self._cache:
            try:
                data = synth()
                fd, path = tempfile.mkstemp(prefix=f"puck_{name}_",
                                            suffix=".wav")
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                self._cache[name] = path
            except Exception:
                return None
        return self._cache.get(name)

    def _play(self, name, synth):
        if not self.enabled or self._player is None:
            return
        def _run():
            try:
                path = self._wav(name, synth)
                if path:
                    self._player(path)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()
