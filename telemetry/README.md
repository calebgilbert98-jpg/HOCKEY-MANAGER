# Beta telemetry

Puck Dynasty logs one compact record per simulated game to
`telemetry/games.jsonl` (in this folder). This happens automatically --
every `GameSim.run()` appends a line when the game ends.

## What's in it

Per game: score, shots, shooting/save %, penalties, PIM, power-play and
penalty-kill numbers, hits, takeaways/giveaways, blocked shots, faceoffs,
expected goals, goalie lines -- plus the rarer whistle events: icings,
offsides, fights, misconducts, penalty shots. Also the sim build (git
commit) and a timestamp.

## What it is not

- Local only. Nothing is uploaded anywhere, ever.
- No personal data. Player names in this game are fictional.
- It cannot break the game: logging is wrapped so any failure is silent.

## Using it

Analyze the log against NHL benchmarks:

```bash
python3 analyze_telemetry.py              # everything
python3 analyze_telemetry.py --last 50    # recent games only
python3 analyze_telemetry.py --by-sim     # compare sim builds
```

Metrics inside the NHL band are `[ok]`, near-misses `[~]`, and clear
misses `[!]` with a pointer to the tuning knob most likely responsible.

## For beta testers

Just play -- the file grows on its own. To share data with the developer,
send `telemetry/games.jsonl` (it's plain text, one game per line).
Deleting the file starts a fresh log.
