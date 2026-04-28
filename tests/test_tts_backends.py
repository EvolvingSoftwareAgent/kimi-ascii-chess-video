import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import render_highlight_reel as reel


class TTSBackendTests(unittest.TestCase):
    def test_narration_lines_use_chess_arena_script(self):
        event = SimpleNamespace(commentary="The queen cuts through the grid.")

        lines = reel.build_narration_lines([event], voice_label="premium cinematic voice")

        self.assertIn("Chess Arena", lines[0])
        self.assertIn("LLMs playing chess", lines[0])
        self.assertNotIn("Piper", lines[0])
        self.assertEqual(lines[1], "The queen cuts through the grid.")
        self.assertIn("central referee", lines[-1])

    def test_external_tts_backend_uses_prerendered_audio_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "premium_voice"
            work = root / "work"
            external.mkdir()
            work.mkdir()
            for idx in range(3):
                (external / f"voice_{idx:02d}.ogg").write_bytes(b"fake ogg")
            event = SimpleNamespace(commentary="The knight hits the alarm square.")

            segments = reel.make_tts_segments([event], work, backend="external", external_dir=external)

            self.assertEqual([path for path, _ in segments], [external / "voice_00.ogg", external / "voice_01.ogg", external / "voice_02.ogg"])
            self.assertEqual((work / "commentary_script.txt").read_text(encoding="utf-8").count("\n"), 2)

    def test_narration_starts_do_not_overlap(self):
        starts = reel.plan_narration_starts(
            desired_starts=[0.8, 1.0, 2.0, 9.5],
            durations=[1.5, 1.5, 2.0, 1.0],
            total_duration=10.0,
            gap=0.25,
        )

        self.assertEqual(starts[0], 0.8)
        for previous_start, previous_duration, next_start in zip(starts, [1.5, 1.5, 2.0], starts[1:]):
            self.assertGreaterEqual(next_start, previous_start + previous_duration + 0.25)
        self.assertLessEqual(starts[-1] + 1.0, 10.0)

    def test_qwen_local_backend_renders_full_lines_and_writes_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            calls = []

            def fake_render(line, out_path, *, speaker, instruct, checkpoint):
                calls.append((line, out_path.name, speaker, instruct, checkpoint))
                out_path.write_bytes(b"wav")
                return {"duration_seconds": 2.2, "rms": 0.08, "peak": 0.5, "leading_silence_seconds": 0.05, "trailing_silence_seconds": 0.1}

            segments = reel.make_qwen_local_tts_segments(
                ["Welcome to Chess Arena.", "The queen lights the board."],
                work,
                render_line=fake_render,
                speaker="ryan",
                instruct="cinematic sports broadcast",
                checkpoint="Qwen/test",
            )

            self.assertEqual([path.name for path, _ in segments], ["qwen_voice_00.wav", "qwen_voice_01.wav"])
            self.assertEqual([slot for _path, slot in segments], [0, 1])
            self.assertEqual(calls[0][0], "Welcome to Chess Arena.")
            self.assertIn("cinematic sports broadcast", calls[0][3])
            metadata = (work / "qwen_local_tts_manifest.json").read_text(encoding="utf-8")
            self.assertIn("Qwen/test", metadata)
            self.assertIn("Welcome to Chess Arena", metadata)

    def test_qwen_local_backend_rejects_drawn_out_or_silent_clips(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)

            def slow_render(_line, out_path, **_kwargs):
                out_path.write_bytes(b"wav")
                return {"duration_seconds": 15.0, "rms": 0.08, "peak": 0.5, "leading_silence_seconds": 0.1, "trailing_silence_seconds": 0.2}

            with self.assertRaisesRegex(ValueError, "failed quality gate"):
                reel.make_qwen_local_tts_segments(["Too slow."], work, render_line=slow_render)

    def test_make_tts_segments_routes_qwen_local_backend(self):
        event = SimpleNamespace(commentary="The bishop opens a laser line.")
        with tempfile.TemporaryDirectory() as tmp, patch.object(reel, "make_qwen_local_tts_segments", return_value=[(Path(tmp) / "qwen_voice_00.wav", 0)]) as qwen:
            segments = reel.make_tts_segments([event], Path(tmp), backend="qwen-local")

        self.assertEqual(segments[0][1], 0)
        qwen.assert_called_once()

    def test_viewer_commentary_avoids_repeating_san_notation(self):
        moved = reel.chess.Piece(reel.chess.QUEEN, reel.chess.BLACK)
        captured = reel.chess.Piece(reel.chess.PAWN, reel.chess.WHITE)

        caption = reel.make_caption("Qxg2", moved, captured, "capture", 8)
        commentary = reel.make_commentary(11, "Qxg2", moved, captured, "capture", 8, reel.chess.BLACK)

        self.assertNotIn("Qxg2", caption)
        self.assertNotIn("Qxg2", commentary)
        self.assertIn("queen", commentary)
        self.assertIn("White", commentary)


if __name__ == "__main__":
    unittest.main()
