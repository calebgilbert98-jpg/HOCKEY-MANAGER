# Multiplayer Fantasy Draft Bug — Root Cause

**Reported by Caleb (Oct 6):** Friend could join the MP game, but they couldn't
start a fantasy draft.

## Root Cause

`pending_fantasy_draft` is set on the host during game setup (main.py:382,528),
but it is **never referenced in any multiplayer code**:

- Not included in the state snapshot (`net_host.py` broadcast_state)
- `start_game()` (net_host.py:320) broadcasts START_GAME without checking the flag
- Client never receives the flag, never opens the draft UI

The draft sync infrastructure EXISTS (protocol.py: `FANTASY_DRAFT_CLOCK`,
`fantasy_draft_pick`; net_host.py: `send_fantasy_draft_clock`). The bug is
purely that the draft never STARTS in MP.

## Fix for Native

1. Include `pending_fantasy_draft` in MP snapshot
2. `start_game()` checks the flag; if set, host initiates the draft flow
   instead of jumping straight to day 1
3. Host runs the draft; clients receive `fantasy_draft_clock` messages
   for their picks (infrastructure already exists)
4. On draft complete, broadcast state and proceed to regular game flow
