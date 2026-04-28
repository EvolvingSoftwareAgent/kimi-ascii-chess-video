# Chess Arena: An ASCII-System Benchmark for LLM Chess

Chess Arena is a cinematic AI experiment: a full chess game rendered as a neon terminal battle, with language-model move proposals, a central legality referee, generated commentary, synthetic music, and an automated video pipeline orchestrated from Hermes.

The project began as a simple idea: make an LLM play chess visibly, without hiding the hard parts. The final system is not just a chess board and not just a video render. It is a complete benchmark-showcase pipeline where model reasoning, rule discipline, tactical pressure, arbitration, narration, and production tooling are all exposed as part of the performance.

## The core idea

Chess is useful because it is unforgiving. A model can sound strategic in prose, but chess asks for one legal move from one exact position. Chess Arena turns that constraint into a visual benchmark:

- Can a language model maintain board state?
- Can it propose a legal move without engine help?
- Can it recover when a proposal is malformed or illegal?
- Can it continue planning under tactical pressure?
- Can the system make those moments observable instead of hiding them in logs?

The video presents that benchmark as an arena. The left side is the board. The right side is a terminal-style model/referee stream. The center is the cinematic explanation layer. Captures become particle events. Checks become red targeting alarms. Ordinary moves accelerate through a fast montage, while tactical moments slow down into battle beats.

## System architecture

Chess Arena is built around one strict rule: players propose moves, but the arena owns the truth.

```text
White seat / Black seat
        |
        v
Player adapter proposes exactly one move
        |
        v
Central referee / controller
- owns board state
- validates legality
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

- an LLM adapter using an OpenAI-compatible HTTP endpoint,
- Stockfish through UCI,
- a mock/random-legal player for repeatable pipeline testing,
- or a human input adapter.

The controller is the important middle layer. It is not Stockfish in disguise. It is the referee: it stores the canonical board, checks legal moves through `python-chess`, records every accepted move, and emits structured events for the renderer. This separation keeps the chess experiment fair and keeps the visual system from contaminating the move generator.

## No-tools LLM play

The LLM side is deliberately constrained. The model receives the current board position, side to move, and recent history. It is asked to infer one move and return only that move. It does not receive a legal-move list and it does not get hidden engine advice.

After the model proposes a move, the central referee validates it. The adapter supports strict parsing and recovery:

- prefer exact SAN from the legal move set,
- normalize castling notation,
- fall back to legal UCI coordinates when needed,
- reject prose unless it contains a valid move candidate,
- retry malformed or illegal outputs within a budget,
- apply an AI-only touch-move rule when the model clearly identifies a source piece but proposes an illegal destination.

That means invalid behavior becomes visible data instead of a crash. The system can show whether a model follows the rules, repairs itself, or needs fallback arbitration.

## From game events to video scenes

The controller emits a timeline of game events. The renderer treats those events as a score for the final film:

- ordinary move,
- capture,
- underdog capture,
- check,
- checkmate,
- invalid retry,
- adapter note,
- final explanation scene.

Each event is scored for cinematic importance. Ordinary moves become fast-montage flashes. Captures, checks, and underdog attacks stretch into slow-motion combat segments. Checkmate gets the longest lockdown beat.

The full-game render keeps every move in order, rather than cutting directly to highlights. That matters because the viewer sees the whole game unfold, but the timing still feels like a trailer: quick where the position is developing, slow where the board explodes.

The current full-game render command is:

```bash
python render_highlight_reel.py \
  --mode full-game \
  --duration 90 \
  --max-plies 74 \
  --seed 184 \
  --tts-backend qwen-local \
  --voice-label 'local Qwen3-TTS 1.7B Ryan full-line narration' \
  --out outputs/chess_arena_full_game_qwen_local_1_7b_seed184.mp4
```

## Visual design

The visual language evolved from a terminal demo into a hybrid ASCII/game-art arena:

- 1280×720 MP4 output,
- brown chess-board squares for piece readability,
- solid black and white pieces,
- a green-neon research-lab / underground terminal HUD,
- true ASCII/protocol text in the model/referee stream,
- particle-driven capture impacts,
- red king-targeting animations for check,
- an intro card and final explanatory scene.

The design goal was not to imitate a normal chess broadcast. It was to make reasoning, legality, and tactical pressure feel like a machine-room sport.

## Hermes orchestration

Hermes acted as the project conductor. It coordinated the build as a sequence of tool-using agent sessions rather than a single manual script run.

Hermes was used to:

- inspect and modify the Python codebase,
- design the controller/referee architecture,
- harden the LLM move parser,
- add event scoring and timeline generation,
- run focused tests and syntax checks,
- generate and audition voice samples,
- launch long-running TTS jobs in the background,
- monitor generated audio counts and logs,
- render smoke-test videos,
- extract verification frames,
- inspect final frames for visual regressions,
- verify audio and video streams with `ffmpeg` and `ffprobe`,
- iterate from rough draft to publishable cut.

The important part is that Hermes was not just asked for advice. It executed the pipeline: code edits, test runs, rendering commands, media checks, and artifact review all happened through the same orchestrated agent environment.

## Audio sample generation

The audio pipeline went through several stages.

First, a reusable game-audio bank was scaffolded. The bank separates short atoms from reusable phrases:

- side atoms: `White's`, `Black's`,
- piece atoms: pawn, knight, bishop, rook, queen, king,
- phrase templates: reusable action lines that can be combined with pieces.

The manifest builder expands these into hundreds of possible samples. The generator supports resumable output so long batches can survive transient provider failures.

```bash
python scripts/build_voice_bank_manifest.py
python scripts/generate_voice_bank.py --provider edge --voice en-US-GuyNeural --resume
```

For the final direction, atom stitching was rejected because technically valid clips can still have the wrong cadence. The production path moved to full-line narration: each commentary line is generated as one complete performance so the delivery feels coherent.

The preferred local final candidate became Qwen3-TTS 1.7B CustomVoice using the Ryan voice on CPU. It is slow, but it gives a better offline cinematic result than stitching hundreds of tiny fragments.

The renderer writes a commentary script, generates full-line clips, quality-checks them, schedules them against the timeline, and mixes them into the final video. Quality gates check for empty files, duration budget, peak/RMS level, and leading/trailing silence.

## Commentary design

The narration is intentionally sparse. The video is not a move-by-move lecture. It uses short action beats:

- opening explanation,
- key captures,
- checks,
- underdog swings,
- checkmate,
- final benchmark explanation.

The copy avoids dense chess notation in viewer-facing narration. Instead of speaking raw SAN such as `Qe6+`, the video describes what the viewer can understand immediately: side, piece, action, victim, and referee verdict.

The final explanatory beat frames Chess Arena as a system test of planning, tactics, rule discipline, recovery, and central adjudication.

## Music creation

The soundtrack is generated inside the render pipeline as original synthetic backing music. The renderer creates a local music bed, mixes it under the narration, and then muxes the music, commentary, and silent video render into the final MP4.

The pipeline produces separate intermediate artifacts for auditability:

- silent reel video,
- synthetic music WAV,
- individual narration clips,
- mixed commentary WAV,
- ffmpeg video logs,
- ffmpeg voice-mix logs,
- ffmpeg mux logs,
- full-game manifest,
- preview frames.

That makes the final video reproducible and debuggable. If the audio is too quiet, the frame timing is wrong, or narration overlaps a tactical beat, the intermediate files show where the problem happened.

## Tooling stack

Core runtime:

- Python 3,
- `python-chess` for board state and legal move validation,
- Stockfish through UCI for the classical engine seat,
- Pillow for frame rendering,
- NumPy and WAV tooling for procedural audio,
- `ffmpeg` / `ffprobe` for video and audio assembly,
- Rich for the terminal-native prototype,
- Hermes for orchestration.

Project scripts:

- `terminal_chess_demo.py` — live terminal prototype and chess-controller experiment,
- `render_highlight_reel.py` — full-game speed-ramped renderer and final MP4 pipeline,
- `scripts/build_voice_bank_manifest.py` — reusable chess voice-bank manifest generator,
- `scripts/generate_voice_bank.py` — Edge/Qwen voice sample generator with resume and retry behavior,
- `scripts/probe_qwen_tts_cpu_render.py` — local CPU TTS proof-of-life tool.

## Verification

The system is checked at several levels:

- Python compile checks for modified scripts,
- unit tests for rendering style, TTS backends, and voice-bank behavior,
- smoke renders for short video samples,
- `ffprobe` checks for duration, streams, resolution, and media validity,
- `ffmpeg` audio checks for non-silent output,
- extracted verification frames for title, gameplay, and final-scene review.

Representative verification commands:

```bash
python -m py_compile render_highlight_reel.py terminal_chess_demo.py
python -m unittest tests.test_reel_rendering tests.test_tts_backends tests.test_chess_arena_style -v
ffprobe -v error -show_entries format=duration,size -of default=nw=1:nk=1 outputs/chess_arena_full_game_qwen_local_1_7b_seed184.mp4
```

## Why it matters

Chess Arena is a benchmark wrapped in a spectacle.

A normal benchmark compresses a model into a score. Chess Arena keeps the score, but also shows the behavior: the proposed move, the referee decision, the tactical pressure, the recovery path, and the final consequence on the board.

It is a way to make LLM chess less abstract. Instead of saying a model can or cannot reason, the system puts the model in a rules-bound arena and makes every decision visible.

That is the full system: LLM move generation, central adjudication, event-driven rendering, generated narration, synthetic music, automated media assembly, and Hermes-orchestrated iteration — all combined into one terminal-native AI chess film.
