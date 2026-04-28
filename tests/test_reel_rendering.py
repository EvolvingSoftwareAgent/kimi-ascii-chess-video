import unittest
from pathlib import Path
from types import SimpleNamespace

import chess

import render_highlight_reel as reel


FORBIDDEN_LABELS = ("Kimi", "kimi", "Razorfish", "razorfish")


class ReelRenderingTests(unittest.TestCase):
    def test_video_facing_copy_uses_generic_side_names(self):
        board = chess.Board()
        move = board.parse_san("e4")
        moved = board.piece_at(move.from_square)

        self.assertEqual(reel.side_display_name(chess.WHITE), "White")
        self.assertEqual(reel.side_display_name(chess.BLACK), "Black")

        commentary = reel.make_commentary(0, "e4", moved, None, "move", 0, chess.WHITE)
        narration = reel.build_narration_lines([], voice_label="Qwen Ryan Broadcast Hype")
        visible_strings = [commentary, *narration, reel.title_matchup_text(), reel.hud_matchup_text()]
        for text in visible_strings:
            for forbidden in FORBIDDEN_LABELS:
                self.assertNotIn(forbidden, text)

    def test_moving_piece_trail_uses_piece_colour_not_hardcoded_white(self):
        self.assertEqual(reel.moving_piece_color(chess.Piece(chess.PAWN, chess.WHITE)), reel.PURE_WHITE)
        self.assertEqual(reel.moving_piece_color(chess.Piece(chess.PAWN, chess.BLACK)), reel.PURE_BLACK)
        self.assertEqual(reel.trail_color_for_step(chess.Piece(chess.KNIGHT, chess.BLACK), 0), reel.PURE_BLACK)
        self.assertNotEqual(reel.trail_color_for_step(chess.Piece(chess.KNIGHT, chess.BLACK), 0), reel.PURE_WHITE)

    def test_capture_effect_profiles_are_streaming_explosions_not_one_boom_loop(self):
        pawn = reel.capture_style(chess.Piece(chess.PAWN, chess.WHITE))
        queen = reel.capture_style(chess.Piece(chess.QUEEN, chess.BLACK))

        self.assertEqual(pawn["motion"], "streaming-explosion")
        self.assertEqual(queen["motion"], "streaming-explosion")
        self.assertNotEqual(pawn["stream"], queen["stream"])
        self.assertIn("debris", pawn)
        self.assertIn("shock", queen)

    def test_board_coordinate_footer_is_below_playing_area(self):
        board_bottom = reel.BOARD_Y + 8 * reel.CELL
        file_label_y = reel.BOARD_Y + 8 * reel.CELL + 22

        self.assertGreater(file_label_y, board_bottom)
        self.assertLessEqual(file_label_y, board_bottom + 42)

    def test_main_board_uses_vector_piece_symbols_not_ascii_art(self):
        self.assertIn(reel.chess.QUEEN, reel.PIECE_SYMBOL)
        self.assertEqual(reel.PIECE_SYMBOL[reel.chess.QUEEN][0], "♕")
        self.assertEqual(reel.PIECE_SYMBOL[reel.chess.QUEEN][1], "♛")

    def test_piece_icon_is_solid_without_backplate_or_outline(self):
        class FakeDraw:
            def __init__(self):
                self.ellipses = []
                self.text_calls = []

            def ellipse(self, *args, **kwargs):
                self.ellipses.append((args, kwargs))

            def text(self, *args, **kwargs):
                self.text_calls.append((args, kwargs))

        fake = FakeDraw()
        piece = chess.Piece(chess.QUEEN, chess.BLACK)
        reel.draw_piece_icon(fake, 0, 0, reel.CELL, piece)
        self.assertEqual(fake.ellipses, [])
        fills = [kwargs.get('fill') for _args, kwargs in fake.text_calls]
        self.assertIn(reel.PURE_BLACK, fills)
        self.assertNotIn(reel.PURE_WHITE, fills)

    def test_event_side_comes_from_moved_piece_not_board_turn_label(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("d5")
        move = board.parse_san("exd5")
        moved = board.piece_at(move.from_square)
        self.assertEqual(reel.side_display_name(moved.color), "White")
        self.assertIn("White pawn", reel.make_commentary(2, "exd5", moved, board.piece_at(move.to_square), "capture", 0, moved.color))

    def test_model_stream_does_not_show_repeated_raw_notation_or_hidden_lines(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("e5")
        move = board.parse_san("Qh5")
        moved = board.piece_at(move.from_square)
        after = board.copy(stack=False)
        after.push(move)
        event = SimpleNamespace(
            side="White",
            ply=1,
            san="Qh5",
            uci=move.uci(),
            kind="move",
            board_before=board,
            board_after=after,
            moved_piece=moved,
            captured_piece=None,
            caption="White queen develops pressure",
        )
        class FakeDraw:
            def __init__(self):
                self.lines = []
            def rectangle(self, *args, **kwargs): pass
            def text(self, xy, text, *args, **kwargs): self.lines.append(str(text))
        fake = FakeDraw()
        reel.draw_llm_stream_panel(fake, event, 0.0)
        later = FakeDraw()
        reel.draw_llm_stream_panel(later, event, 1.0)
        joined = "\n".join([*fake.lines, *later.lines]).lower()
        self.assertNotIn("legal-move-list", joined)
        self.assertNotIn("legal moves hidden", joined)
        self.assertNotIn("fen:", joined)
        self.assertNotIn("raw:", joined)
        self.assertNotIn("uci:", joined)
        self.assertNotIn("qh5", joined)
        self.assertIn("board-ascii before", joined)
        self.assertIn("board-ascii after", joined)

    def test_voice_bank_tts_backend_maps_events_to_qwen_sample_files(self):
        with self.subTest("real qwen bank exists"):
            bank = Path("assets/voice_bank/generated/qwen_ryan_broadcast_hype")
            self.assertTrue((bank / "generated_index.json").exists())

        event = SimpleNamespace(
            moved_piece=chess.Piece(chess.KNIGHT, chess.BLACK),
            side="Black",
            ply=7,
            san="Nxc7+",
            commentary="unused",
        )
        segments = reel.make_tts_segments(
            [event],
            Path("/tmp"),
            backend="voice-bank",
            external_dir=Path("assets/voice_bank/generated/qwen_ryan_broadcast_hype"),
            voice_label="Qwen Ryan Broadcast Hype",
        )
        paths = [path for path, _ in segments]
        self.assertTrue(any("black_possessive.ogg" in str(path) for path in paths))
        self.assertTrue(any("piece_knight.ogg" in str(path) for path in paths))
        self.assertTrue(any("phrases/knight/" in str(path) for path in paths))


if __name__ == "__main__":
    unittest.main()
