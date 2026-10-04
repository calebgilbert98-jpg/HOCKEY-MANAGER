# Puck Dynasty Web UI — Bridge Architecture Plan

Date: 2026-10-04
Status: planning (tile hub POC approved in principle, awaiting Caleb's look)

## Goal
Replace Tkinter screens with a 2K-style tile web UI, one screen at a time.
Python sim, database, AI, and game logic do not change. Only the presentation
layer is replaced.

## Architecture: same-process Flask + command queue

```
┌─────────────────────────────┐
│  Puck Dynasty process       │
│                             │
│  ┌──────────┐  ┌─────────┐  │
│  │ Tkinter  │  │ Flask   │  │
│  │ mainloop │◄─┤ :5050   │  │
│  │ (UI #1)  │  │ thread  │  │
│  └────┬─────┘  └────┬────┘  │
│       │             │       │
│       ▼             ▼       │
│  ┌──────────────────────┐   │
│  │ command queue        │   │
│  │ (web → game writes)  │   │
│  └──────────────────────┘   │
│       │                     │
│       ▼                     │
│  ┌──────────────────────┐   │
│  │ GameManager / league │   │
│  │ (unchanged)          │   │
│  └──────────────────────┘   │
└─────────────────────────────┘
        ▲
        │  http://localhost:5050
        │
┌───────┴────────┐
│ Browser (user) │
│ tile hub UI    │
└────────────────┘
```

### Why same-process
- The game state is a live object graph (GameManager → league → teams →
  players). Serializing it across processes every request is wasteful and
  risks stale reads.
- Flask in a background thread reads the same objects the Tkinter UI reads.
- No save/load round-trip needed; the web UI sees the live game.

### Reads (web → game state)
Flask handlers read attributes directly off `app.game_manager` /
`app.user_team`. Rules:
- Never touch a Tk widget from a Flask thread (Tkinter is not thread-safe).
- Read-only access to the model is safe; the model is only mutated on the
  main thread.
- Serialize via small `to_web_*()` helpers (Player → dict with name,
  overall, age, salary, etc.). Never leak raw objects to JSON.

### Writes (web → game actions)
All mutations go through a `queue.Queue` drained by the Tk mainloop via
`root.after(50, drain)`. Flask POSTs enqueue a command dict like
`{"op": "advance_day"}`; the main thread executes it and the next GET
reflects the result. This avoids every Tkinter threading hazard:
- Continue / advance day
- Tile actions (open roster with filter, mark inbox read, etc.)
- Any future write (trades, line changes) follows the same path

### Migration order (one screen at a time)
1. Hub (done as POC) — read-only, lowest risk
2. Inbox — reads + mark-read/delete (first writes via queue)
3. Roster / player profile — reads, then demote/promote actions
4. Schedule / game center — reads, then sim/play actions
5. Continue flow + blocker modal — the write-heavy path, last

Each screen ships behind a flag: the Tkinter window stays until its web
replacement is proven, then the nav tile points at the browser instead.
No big-bang rewrite; the game stays playable throughout.

### Packaging
- Flask is a pip dependency; the Windows build bundles it like
  customtkinter today.
- The game opens the hub in the user's default browser on launch
  (or an embedded webview later). Localhost only — no network exposure.
- Long term: the Tkinter shell becomes a thin launcher; the browser is
  the game.

## Open questions for Caleb
- Browser tab vs embedded webview for the final feel?
- Which screen after the hub — inbox or roster?
