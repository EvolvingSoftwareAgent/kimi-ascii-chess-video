# Gambit Arena

**Gambit Arena** turns LLM chess into something you can watch, audit, and feel.

It is a rules-bound arena where language-model players propose chess moves, a central referee enforces legality, and every accepted move becomes part of a cinematic event stream. The same system that plays the game also produces the film: board animation, model/referee telemetry, tactical effects, generated narration, procedural music, and final MP4 assembly.

Most AI benchmarks compress behavior into a number. Gambit Arena keeps the rigor, but exposes the behavior: the proposed move, the validation step, the tactical pressure, the recovery path, and the consequence on the board.

## The idea

Chess is a hard test for language models because it leaves almost no room for vibes.

For the broader argument behind chess as a no-tools LLM benchmark, read the write-up: [The 64-Square Test](https://evolvingsoftware.com/articles/the-64-square-test.html).

A model can sound strategic in prose, but in chess it has to produce one move from one exact position. That move must be legal. It must fit the board state. It must survive tactical pressure. If the model loses track, the failure is immediate and visible.

Gambit Arena uses that constraint as the foundation for a full creative system:

1. **Benchmark the model** — can it track state, respect rules, and recover from malformed output?
2. **Expose the process** — show the model/referee loop instead of burying it in logs.
3. **Render the drama** — transform structured game events into a watchable AI chess film.

The result is not just “an AI played chess.” It is a machine-room broadcast of reasoning under rules.

## What it does

Gambit Arena combines four layers:

- **Game layer** — player seats propose moves; the referee owns the canonical board.
- **Benchmark layer** — legality, retries, malformed output, tactical events, and final outcomes are recorded.
- **Show layer** — moves become scenes with timing, captions, ASCII board traces, capture effects, check effects, and final explanation beats.
- **Media layer** — narration, music, video frames, and final muxing are generated as reproducible artifacts.

That makes it useful both as a benchmark harness and as a generative media pipeline.

## How the arena works

Gambit Arena is built around one strict rule:

**Players propose moves. The arena owns the truth.**

```text
White seat / Black seat
        |
        v
Player adapter proposes exactly one move
        |
        v
Central referee / controller
- owns canonical board state
- validates legal moves
- records history
- emits structured events
        |
        v
Show layer
- board animation
- model/referee stream
- captions
- narration
- music
- final video export
```

The player seats are interchangeable. A seat can be backed by:

- an LLM adapter through an OpenAI-compatible endpoint,
- Stockfish through UCI,
- a deterministic mock/random-legal adapter for repeatable pipeline tests,
- or a human input adapter.

The controller is the load-bearing part. It stores the canonical board, validates moves through `python-chess`, records accepted moves, and emits structured events for the renderer. The move generator never mutates the board directly.

That separation keeps the benchmark fair. It also keeps the cinematic layer honest: the video is driven by the official game record, not by hand-authored drama.

## No-tools LLM play

The LLM side is deliberately constrained. The model receives the current position, side to move, and recent history, then must return one move. It does not receive a legal-move list and it does not get hidden engine advice.

The adapter supports strict parsing and recovery:

- prefer exact SAN from the current legal move set,
- normalize castling notation,
- accept legal UCI coordinates when appropriate,
- reject prose unless it contains a valid move candidate,
- retry malformed output within a budget,
- record recovery behavior as benchmark data.

This makes model behavior observable. The system can show when a model follows the rules, repairs itself, creates pressure, or needs fallback arbitration.

## From chess events to scenes

The controller emits a timeline of `GameEvent` objects. Each event contains the ply number, side, SAN/UCI move, board before/after, moved piece, captured piece, event kind, caption, commentary, and score context.

The renderer treats those events as an edit decision list:

- ordinary move,
- capture,
- underdog capture,
- check,
- checkmate,
- adapter/referee note,
- final explanation scene.

Ordinary moves become fast montage beats. Captures, checks, and tactical swings slow down into combat moments. Checkmate becomes a locked final state rather than just another move.

The full-game mode keeps every move in order. The viewer sees the whole game unfold, but the timing still feels edited: fast where the position is developing, slow where the board explodes.

## Video production pipeline

The video is not edited manually in a timeline editor. The Python renderer performs the edit from structured game data.

The production pipeline is:

1. **Play or simulate the game** — generate accepted moves and board states.
2. **Classify events** — identify ordinary moves, captures, checks, underdog captures, and checkmate.
3. **Build the timeline** — assign each ply a start time, duration, label, and importance score.
4. **Render the silent film** — stream RGB frames into `ffmpeg` as raw video.
5. **Generate narration** — write a commentary script and render full-line voice clips.
6. **Schedule voice clips** — place narration near the event it explains while avoiding overlap.
7. **Create music** — synthesize a procedural backing track as a WAV file.
8. **Mix commentary** — combine narration clips into one commentary stem.
9. **Mux final video** — combine silent video, music, and commentary into the final MP4.
10. **Verify artifacts** — inspect media streams, duration, logs, and preview frames.

The renderer writes audit artifacts under `outputs/full_game_work/`:

- `silent_reel.mp4` — video-only render,
- `synthetic_music.wav` — generated soundtrack,
- `commentary_script.txt` — exact narration script,
- generated narration clips,
- `commentary.wav` — mixed narration stem,
- `ffmpeg_video.log` — raw frame encode log,
- `ffmpeg_voice_mix.log` — narration-mix log,
- `ffmpeg_mux.log` — final mux log,
- `full_game_manifest.txt` — timeline/edit manifest,
- preview frames for visual review.

The important property is reproducibility. If a frame, voice line, timing beat, or audio level needs review, the intermediate artifact exists.

## Visual direction

The visual language is a hybrid of chessboard, terminal UI, and underground AI lab:

- 1280×720 MP4 output,
- warm brown board palette for readability,
- solid black and white chess pieces,
- green-neon research-lab HUD,
- terminal/protocol text in the model/referee stream,
- board-before and board-after ASCII traces,
- particle-driven capture impacts,
- piece-specific capture effects,
- red king-targeting animation for check,
- title card,
- final explanatory system scene.

The design goal is not to imitate a normal chess broadcast. Gambit Arena makes reasoning, legality, and tactical pressure feel like a machine-room sport.

## Capture and check effects

Captures are not a single generic explosion. Each piece type has its own impact profile:

- pawns create swarm-like contact,
- knights create bent L-shaped strike trails,
- bishops cut diagonal beams,
- rooks fire rank/file shockwaves,
- queens create vortex effects,
- kings create compression waves.

Checks are treated differently from captures. The king becomes the target. The board shifts into alarm mode, red targeting graphics appear, and the referee stream marks the threat. Checkmate becomes a locked final state.

## Narration

The narration is concise and cinematic. It explains the system, calls out key tactical beats, and avoids dense chess notation in the viewer-facing copy.

Instead of saying raw SAN such as `Qe6+`, the narrator says what the viewer can understand immediately:

- side,
- piece,
- action,
- victim,
- referee verdict.

Example style:

- “Black queen captures pawn from White. Queen Vortex impact; debris on the square.”
- “Black queen checks the king. The monarch has to answer in public.”
- “Black queen seals the king. No doors remain; the referee confirms checkmate.”

The final explanatory beat frames Gambit Arena as a system test of planning, tactics, rule discipline, recovery, and central adjudication.

## Music creation

The soundtrack is original procedural music generated inside the render pipeline.

`render_highlight_reel.py` creates `synthetic_music.wav` directly with Python WAV synthesis. The music bed is designed as urgent game-trailer backing:

- 150 BPM pulse,
- minor/tense arpeggio pattern,
- sub-bass movement,
- kick drum pulse,
- hi-hat noise bursts,
- rising tone over the full duration.

The soundtrack is not a static asset. It is generated as part of the render, then mixed under the narration during final muxing:

```text
silent_reel.mp4 + synthetic_music.wav + commentary.wav
        |
        v
ffmpeg filtergraph
        |
        v
gambit_arena_full_game_qwen_local_1_7b_seed184.mp4
```

The final mix uses `ffmpeg` filters to lower the music bed, raise the voice stem, combine both audio streams, encode AAC, and keep the video stream intact.

## Agentic build loop

Gambit Arena was built through an agentic software-and-media workflow. Hermes coordinated code changes, tests, rendering commands, long-running media jobs, artifact checks, and visual review from the same environment.

That matters because this project is not a single prompt output. It is a working loop:

- inspect the codebase,
- modify the controller or renderer,
- run focused tests,
- render smoke-test videos,
- inspect generated frames and media logs,
- revise timing, visual language, narration, or audio,
- render again,
- verify final streams and artifacts.

The system gets better because the creative pipeline is testable.

## Tooling stack

Core runtime:

- Python 3,
- `python-chess` for board state and legality,
- Stockfish through UCI for the classical engine seat,
- Pillow for frame rendering,
- NumPy and Python WAV tooling for audio,
- `ffmpeg` / `ffprobe` for video assembly and verification,
- Rich for the terminal-native prototype,
- Hermes for orchestration.

Project scripts:

- `terminal_chess_demo.py` — live terminal prototype and chess-controller experiment.
- `render_highlight_reel.py` — full-game speed-ramped renderer and final MP4 pipeline.
- `scripts/build_voice_bank_manifest.py` — reusable chess voice-bank manifest generator.
- `scripts/generate_voice_bank.py` — voice sample generator with resume and retry behavior.
- `scripts/probe_qwen_tts_cpu_render.py` — local CPU TTS proof-of-life tool.

## Key files

```text
README.md                         Project overview and build explanation
render_highlight_reel.py          Full-game video renderer and audio pipeline
terminal_chess_demo.py            Terminal chess prototype/controller
scripts/build_voice_bank_manifest.py
scripts/generate_voice_bank.py
scripts/probe_qwen_tts_cpu_render.py
tests/                            Rendering, TTS, voice-bank, and style tests
```

## Run the renderer

```bash
python render_highlight_reel.py \
  --mode full-game \
  --duration 90 \
  --max-plies 74 \
  --seed 184 \
  --tts-backend qwen-local \
  --voice-label 'local Qwen3-TTS 1.7B Ryan full-line narration' \
  --out outputs/gambit_arena_full_game_qwen_local_1_7b_seed184.mp4
```

## Verification

Representative checks:

```bash
python -m py_compile render_highlight_reel.py terminal_chess_demo.py scripts/generate_voice_bank.py scripts/build_voice_bank_manifest.py
python -m unittest tests.test_reel_rendering tests.test_tts_backends tests.test_gambit_arena_style tests.test_voice_bank_generator tests.test_voice_bank_manifest -v
ffprobe -v error -show_entries format=duration,size -of default=nw=1:nk=1 outputs/gambit_arena_full_game_qwen_local_1_7b_seed184.mp4
```

The system is tested at several levels:

- compile checks for scripts,
- unit tests for rendering style and TTS behavior,
- smoke renders for short video samples,
- `ffprobe` media validation,
- extracted preview frames,
- artifact logs for video encode, voice mix, and final mux.

## Why it matters

A normal benchmark compresses a model into a score. Gambit Arena keeps the discipline of a benchmark, but makes the behavior legible: move proposal, referee decision, tactical pressure, recovery path, and final consequence.

That changes how model capability feels. Instead of asking people to trust a result table, Gambit Arena puts the model inside a rules-bound arena and lets the audience watch every decision become reality.

That is the full system: LLM move generation, central adjudication, event-driven rendering, generated narration, procedural music, automated media assembly, and agentic iteration — all combined into one terminal-native AI chess film.