# Gambit Arena

**Gambit Arena** is a cinematic LLM chess benchmark and automated video-production pipeline built for the **Hermes Agent Creative Hackathon**, presented by [Kimi.ai](https://x.com/Kimi_Moonshot) and [Nous Research](https://x.com/NousResearch).

The hackathon brief asks builders to push Hermes Agent into creative domains: video, image, audio, 3D, long-form writing, creative software, interactive media, and more. Gambit Arena answers that brief with a complete AI chess film system: model move generation, central legality adjudication, event-driven video editing, generated narration, procedural music, and final MP4 assembly orchestrated through Hermes.

The project turns a chess game into a visible benchmark. Instead of hiding the hard parts in logs, the video shows the board, the model/referee stream, tactical pressure, legal-move discipline, captures, checks, checkmate, narration, and soundtrack as one coherent arena.

Project page: https://evolvingsoftwareagent.github.io/gambit-arena/

Repository: https://github.com/EvolvingSoftwareAgent/gambit-arena

## What it is

Gambit Arena is both:

1. **An LLM chess benchmark** — language-model player seats propose moves from board state and history while a central controller owns the truth.
2. **A generative video pipeline** — structured chess events become an edited 1280×720 cinematic video with speed ramps, visual effects, narration, and music.

Chess is useful because it is unforgiving. A model can sound strategic in prose, but chess asks for one legal move from one exact position. Gambit Arena turns that constraint into a filmable system test:

- Can a model track board state?
- Can it propose a legal move without receiving a hidden legal-move list?
- Can it recover when output is malformed?
- Can it keep planning while tactical pressure increases?
- Can the system make those moments observable instead of burying them?

The result is a benchmark wrapped in spectacle: every accepted move becomes data, every important tactical event becomes a scene, and the final video explains how the system works as it plays.

## How the app works

Gambit Arena is built around one strict rule:

**Players propose moves, but the arena owns the truth.**

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

The controller is the important middle layer. It stores the canonical board, validates moves through `python-chess`, records every accepted move, and emits structured events for the renderer. The move generator does not get to mutate the board directly. That separation keeps the benchmark fair and keeps the cinematic layer from contaminating the game logic.

## No-tools LLM play

The LLM side is deliberately constrained. The model receives the current position, side to move, and recent history, then must return one move. It does not receive a legal-move list and it does not get hidden engine advice.

The adapter supports strict parsing and recovery:

- prefer exact SAN from the current legal move set,
- normalize castling notation,
- accept legal UCI coordinates when appropriate,
- reject prose unless it contains a valid move candidate,
- retry malformed output within a budget,
- record recovery behavior as benchmark data.

That means model behavior becomes visible and measurable. The system can show when a model follows rules, repairs itself, creates pressure, or needs fallback arbitration.

## From game events to video scenes

The controller emits a timeline of `GameEvent` objects. Each event contains the ply number, side, SAN/UCI move, board before/after, moved piece, captured piece, event kind, caption, commentary, and score context.

The renderer treats those events as an edit decision list for the final film:

- ordinary move,
- capture,
- underdog capture,
- check,
- checkmate,
- adapter/referee note,
- final explanation scene.

Each event receives cinematic importance. Ordinary moves become fast montage flashes. Captures, checks, and underdog swings slow down into combat beats. Checkmate receives the longest lockdown moment.

The full-game mode keeps every move in order rather than cutting only to highlights. The viewer sees the whole game unfold, but the timing still feels edited: fast where the position is developing, slow where the board explodes.

Current full-game render command:

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

## Video editing process

The video is not edited manually in a timeline editor. The Python renderer performs the edit from structured game data.

The production pipeline is:

1. **Simulate or play the game** — generate accepted moves and board states.
2. **Classify events** — identify ordinary moves, captures, checks, underdog captures, and checkmate.
3. **Build a full-game timeline** — assign each ply a start time, duration, label, and importance score.
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
- `qwen_voice_XX.wav` — generated narration clips,
- `commentary.wav` — mixed narration stem,
- `ffmpeg_video.log` — raw frame encode log,
- `ffmpeg_voice_mix.log` — narration-mix log,
- `ffmpeg_mux.log` — final mux log,
- `full_game_manifest.txt` — timeline/edit manifest,
- preview frames for visual review.

This makes the video reproducible. If a frame, voice line, timing beat, or audio level needs review, the intermediate artifact exists.

## Visual design

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

The design goal is not to imitate a normal chess broadcast. It makes reasoning, legality, and tactical pressure feel like a machine-room sport.

## Capture and check effects

Captures are not a single generic explosion. Each piece type has its own impact profile:

- pawns create swarm-like contact,
- knights create bent L-shaped strike trails,
- bishops cut diagonal beams,
- rooks fire rank/file shockwaves,
- queens create vortex effects,
- kings create compression waves.

Checks are treated differently from captures. The king becomes the target. The board shifts into alarm mode, red targeting graphics appear, and the referee stream marks the threat. Checkmate becomes a locked final state rather than just another move.

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

## Voice generation

The audio pipeline supports multiple TTS backends:

- local Piper draft narration,
- Edge neural draft narration,
- external pre-rendered clips,
- reusable voice-bank samples,
- local Qwen3-TTS full-line narration.

For the final direction, the production path uses full-line narration. Each commentary line is generated as a complete performance so timing, cadence, and emphasis stay coherent.

The preferred final local voice path is:

- backend: `qwen-local`,
- model: `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`,
- voice: Ryan,
- mode: full-line narration,
- validation: duration, loudness, leading/trailing silence, and empty-file checks.

The renderer writes a commentary script, generates narration lines, checks clip quality, schedules them against the timeline, and mixes them into a single commentary stem.

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

## Hermes orchestration

Hermes acted as the project conductor. It coordinated the build as tool-using agent sessions rather than a single manual script run.

Hermes was used to:

- inspect and modify the codebase,
- design the controller/referee architecture,
- harden the LLM move parser,
- add event scoring and timeline generation,
- run focused tests and syntax checks,
- generate and audition voice samples,
- launch long-running TTS jobs,
- monitor generated audio and logs,
- render smoke-test videos,
- extract verification frames,
- inspect final frames for visual regressions,
- verify streams with `ffmpeg` and `ffprobe`,
- iterate from prototype to publishable cut.

The important part is that Hermes executed the creative pipeline: code edits, tests, rendering commands, media checks, and artifact review all happened through the same agent environment.

## Hackathon fit

Gambit Arena fits the Hermes Agent Creative Hackathon brief because it combines multiple creative domains in one working system:

- **Video** — event-driven cinematic rendering and automated MP4 assembly.
- **Audio** — generated narration, voice scheduling, procedural soundtrack, and mixdown.
- **Creative software** — a reusable pipeline that turns structured game events into finished media.
- **Interactive media** — a chess-controller architecture that can support LLM, engine, and human seats.
- **Long-form explanation** — the final README and project page document how the system works and how the video was made.
- **Agentic production** — Hermes orchestrates the coding, rendering, verification, and media iteration loop.

The entry is not just a video made with an AI tool. It is a system for making AI behavior visible as cinema.

## Kimi ideas to explore next

The hackathon is presented by Kimi and Nous, and Gambit Arena is a natural place to bring Kimi deeper into the system. Good next directions:

### 1. Kimi as a player seat

Use Kimi as the White or Black adapter through an OpenAI-compatible endpoint. The benchmark can compare Kimi against Stockfish, another LLM, or a human seat while the referee keeps the rules consistent.

This is the cleanest integration because the architecture already supports interchangeable player seats.

### 2. Kimi as the commentator

Feed Kimi the structured event manifest after the game and ask it to produce short broadcast lines for selected beats: captures, checks, momentum swings, and final explanation. The renderer can still enforce timing and narration length.

This keeps game play and commentary separate: Kimi can be creative after the referee has already produced the official timeline.

### 3. Kimi as the post-game analyst

Use Kimi to generate a human-readable match report from `full_game_manifest.txt`: key moments, turning points, why the checkmate happened, and which model behaviors looked strong or fragile.

That report could become a companion article or be displayed as a final credits card.

### 4. Kimi as the trailer editor

Give Kimi the list of events, scores, and available scene types, then ask it to choose a trailer cut: which beats to slow down, which captures to emphasize, and where narration should land. The renderer would execute the edit decisions deterministically.

This would turn Kimi into a creative director without letting it break media validity.

### 5. Kimi vs Nous exhibition mode

A hackathon-themed cut could seat Kimi on one side and a Nous model on the other, with the same central referee and the same video pipeline. The video would become both a benchmark and a sponsor-themed exhibition match.

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
- `scripts/generate_voice_bank.py` — Edge/Qwen voice sample generator with resume and retry behavior.
- `scripts/probe_qwen_tts_cpu_render.py` — local CPU TTS proof-of-life tool.

## Key files

```text
README.md                         Hackathon/project entry and build explanation
docs/gambit-arena.md              GitHub Pages project page
docs/index.md                     GitHub Pages index
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

A normal benchmark compresses a model into a score. Gambit Arena keeps the score, but also shows the behavior: the proposed move, the referee decision, the tactical pressure, the recovery path, and the final consequence on the board.

It makes LLM chess less abstract. Instead of only saying a model can or cannot reason, the system puts the model in a rules-bound arena and makes every decision visible.

That is the full system: LLM move generation, central adjudication, event-driven rendering, generated narration, procedural music, automated media assembly, and Hermes-orchestrated iteration — all combined into one terminal-native AI chess film.
