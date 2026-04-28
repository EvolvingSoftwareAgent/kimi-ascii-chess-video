Project: evolving-ascii-chess

Concept
- A Nous research agent / Kimi competitor concept piece.
- An ASCII art chess video showing an LLM playing chess.
- Kimi is the chess brain.
- No tool calling for the chess brain.
- Presentation target: ASCII art / ASCII video format, using the latest available ASCII art workflow/plugin stack in this environment.
- Competition demo target: a terminal-native app that we can screen-record into the submission video.

Current milestone
- Build the first runnable pipeline where the same terminal chess system can support three modes:
  - AI vs traditional computer chess engine
  - AI vs AI with mandatory legality/arbitration in the middle
  - Human vs AI
- The terminal app should already feel cinematic enough to record:
  - animated board updates
  - move-transition highlights
  - capture explosions / impact moments
  - status overlays / telemetry
- This milestone is about the live terminal experience first; polished post-processing / video packaging comes after.

Practical stack chosen
- Terminal renderer: Python + Rich live terminal UI
- Chess state / legality: python-chess
- Traditional engine: Stockfish (UCI)
- LLM side: Kimi-compatible OpenAI-style HTTP adapter, with a random-legal fallback for offline testing
- Recording approach: run the app in terminal and screen-record it for the competition

Environment status
- Local venv created at:
  /home/evosoft/Projects/kimi-ascii-chess-video/.venv
- Installed Python deps:
  - python-chess
  - rich
- Stockfish installed system-wide
- Offline local TTS path confirmed:
  - engine: Piper
  - binary: /home/evosoft/.local/bin/piper
  - selected voice: /home/evosoft/Projects/kimi-ascii-chess-video/assets/voices/piper/en_US-lessac-high.onnx
  - sample output: /home/evosoft/Projects/kimi-ascii-chess-video/assets/voices/piper/sample_excited.wav
- First runnable scaffold:
  /home/evosoft/Projects/kimi-ascii-chess-video/terminal_chess_demo.py
- Highlight reel generator:
  /home/evosoft/Projects/kimi-ascii-chess-video/render_highlight_reel.py
- Latest generated video:
  /home/evosoft/Projects/kimi-ascii-chess-video/outputs/evolving_ascii_chess_highlight_reel.mp4
- Latest whole-game speed-ramped cut:
  /home/evosoft/Projects/kimi-ascii-chess-video/outputs/evolving_ascii_chess_full_game_speed_ramp.mp4
- Python requirements file:
  /home/evosoft/Projects/kimi-ascii-chess-video/requirements.txt

Current capabilities of scaffold
- Runs an ASCII chess match in the terminal
- Can generate a 90-second MP4 highlight reel from a simulated Kimi-vs-Stockfish game:
  - chooses tactical/check/capture moments
  - renders ASCII battle-cam board animations
  - creates fast-paced local Piper voice-over commentary
  - generates an original synthetic music backing track
  - muxes video/music/commentary into a final sendable artifact
- Can now generate a whole-game speed-ramped submission cut:
  - every move is included in timeline order
  - ordinary moves play as fast montage flashes
  - captures/checks/underdog raids/checkmate stretch into slow-motion combat beats
  - narration is selected only for key beats so the video does not become a move-by-move lecture
  - writes a timestamped manifest plus an offline premium TTS strategy note for Qwen/Orpheus/Chatterbox final narration
- Supports:
  - Stockfish as the classical engine
  - random-legal mock player for pipeline testing
  - Kimi/OpenAI-compatible HTTP mode via env vars for real LLM move generation
- Kimi adapter is now hardened enough for repeated demo attempts:
  - strict SAN extraction against the current legal move list
  - UCI fallback when the model emits coordinate notation
  - retry/repair loop before falling back
  - AI-only touch-move constrained retry when a source square is recoverable
  - per-call timeout and optional raw-output JSONL logging
- Emits a lightweight structured match event stream for the renderer:
  - move-proposed
  - move-accepted
  - capture
  - check
  - checkmate
  - invalid-retry / adapter-note diagnostics
- Animates:
  - cinematic title card / versus boot sequence
  - move transitions
  - destination-square highlights
  - stronger capture explosion frames
  - check/checkmate alarm pulses
  - final end card
- Shows live telemetry:
  - side names
  - move list
  - event stream
  - raw chooser output source
  - current status / game result

Rule direction now chosen
- Touch-move-style consequences apply to AI players only.
- If an AI makes an invalid move but still clearly identifies the piece/square being moved, the retry should be constrained to legal moves from that same piece.
- If no source piece can be recovered, or that piece has no legal move, fall back to a normal unconstrained retry.
- Humans still need to make legal moves, but do not inherit AI touch enforcement in the default mode.

Architecture direction now chosen
- Two player-side interfaces/seats:
  - white player seat
  - black player seat
- One central controller/referee interface:
  - authoritative board state
  - move legality
  - move history
  - full board + last-move context passed to the next player
- One audience/show interface:
  - dramatic colourful ASCII presentation
  - commentary / announcer layer
  - local TTS voice output

Current run command
- Activate environment:
  source /home/evosoft/Projects/kimi-ascii-chess-video/.venv/bin/activate
- Run with mock LLM for pipeline testing:
  python /home/evosoft/Projects/kimi-ascii-chess-video/terminal_chess_demo.py --llm-mode random --max-plies 20
- Render the whole-game speed-ramped submission cut:
  python /home/evosoft/Projects/kimi-ascii-chess-video/render_highlight_reel.py --mode full-game --duration 90 --max-plies 74 --out /home/evosoft/Projects/kimi-ascii-chess-video/outputs/evolving_ascii_chess_full_game_speed_ramp.mp4
- Run with Kimi-compatible endpoint once credentials are set:
  KIMI_API_KEY=... KIMI_MODEL=... KIMI_BASE_URL=... python /home/evosoft/Projects/kimi-ascii-chess-video/terminal_chess_demo.py --llm-mode kimi --max-plies 20

Next buildable steps
1. Push the event bus deeper into the renderer:
   - keep event history serializable for later replay/export
   - split match orchestration and show rendering into separate modules
2. Upgrade terminal spectacle:
   - stronger capture explosions
   - check/checkmate alarm states
   - richer intro title card and versus screen
3. Add lightweight commentary layer:
   - short hype-caster lines for captures/checks/mates
   - optional local Piper synthesis for selected lines
4. Make the visual language pixel-native and competition-ready:
   - denser ASCII board styling
   - themed overlays matching one coherent retro aesthetic
5. Add recording/export workflow:
   - stable terminal dimensions
   - terminal recording recipe
   - optional cleanup/compositing into final submission video
6. If/when the newer Discord pixel-art image-conversion plugin becomes available locally, evaluate it only for supporting assets/interstitials. It is not the core workflow, because this project should stay pixel-native from the start.

Roadmap note
- Detailed implementation roadmap lives in:
  /home/evosoft/Projects/kimi-ascii-chess-video/PLAN.txt

Original creative framing
- Board rendered as animated ASCII grids.
- Move text and evaluation overlays can appear as terminal-style captions.
- Narrative arc: opening -> middlegame tension -> endgame / mate / blunder / twist.
- Different scenes can use different ASCII densities and shader moods while keeping one cohesive visual language.

Research questions
- What benchmark best captures raw intelligence without tools?
- What benchmark best captures strategic multi-step reasoning relevant to chess commentary and move selection?
- How should Kimi be constrained so the piece is a fair 'no tools' comparison?

Created by Neo on request from Sebastian.
