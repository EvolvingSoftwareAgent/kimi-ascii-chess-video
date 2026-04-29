# Gambit Arena

A cinematic LLM chess benchmark: model move proposals, central legality arbitration, generated narration, synthetic music, and an automated video pipeline orchestrated through Hermes.

Read the full project page:

- [Gambit Arena: A Cinematic LLM Chess Benchmark](docs/gambit-arena.md)

The system turns a complete chess game into a visual benchmark. Player adapters propose moves, the central referee validates legality, structured events drive a speed-ramped renderer, and the final MP4 is assembled with generated commentary and music.

## Key files

- `terminal_chess_demo.py` — live terminal chess prototype and controller/referee experiment.
- `render_highlight_reel.py` — full-game speed-ramped video renderer.
- `scripts/build_voice_bank_manifest.py` — reusable chess voice-bank manifest generator.
- `scripts/generate_voice_bank.py` — resumable Edge/Qwen voice sample generation.
- `docs/gambit-arena.md` — public-facing explanation page.

## Current render path

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
