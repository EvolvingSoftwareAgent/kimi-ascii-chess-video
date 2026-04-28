import unittest

import chess

import render_highlight_reel as reel
from terminal_chess_demo import OpenAICompatibleLLMPlayer


class ChessArenaStyleTests(unittest.TestCase):
    def test_branding_uses_chess_arena_and_explains_benchmark(self):
        self.assertEqual(reel.project_title_text(), "CHESS ARENA")
        lines = reel.build_narration_lines([], voice_label="scripted narration")
        joined = "\n".join(lines)
        self.assertIn("Chess Arena", joined)
        self.assertIn("LLMs playing chess", joined)
        self.assertIn("benchmark", joined.lower())
        self.assertIn("rule discipline", joined.lower())
        self.assertNotIn("legal move list", joined.lower())
        self.assertNotIn("legal moves", joined.lower())
        self.assertNotIn("Qwen Ryan", joined)

    def test_piece_colours_are_literal_black_and_white(self):
        self.assertEqual(reel.piece_fill_color(chess.Piece(chess.PAWN, chess.WHITE)), reel.PURE_WHITE)
        self.assertEqual(reel.piece_fill_color(chess.Piece(chess.PAWN, chess.BLACK)), reel.PURE_BLACK)
        self.assertEqual(reel.moving_piece_color(chess.Piece(chess.KNIGHT, chess.BLACK)), reel.PURE_BLACK)

    def test_board_palette_is_brown_not_blue_gray(self):
        light, dark = reel.wood_square_colors(0, 0)
        self.assertGreater(light[0], light[1])
        self.assertGreater(light[1], light[2])
        self.assertGreater(dark[0], dark[1])
        self.assertGreater(dark[1], dark[2])
        self.assertNotEqual(light, (192, 205, 210))
        self.assertNotEqual(dark, (20, 34, 52))

    def test_piece_ascii_art_is_multiline_not_single_letter(self):
        art = reel.piece_ascii_art(chess.Piece(chess.QUEEN, chess.WHITE))
        self.assertGreaterEqual(len(art.splitlines()), 4)
        self.assertGreater(len(art.replace("\n", "")), 8)
        self.assertNotEqual(art, "Q")

    def test_llm_prompt_does_not_supply_legal_move_list(self):
        board = chess.Board()
        player = OpenAICompatibleLLMPlayer(name="TestModel")
        prompt = player._build_prompt(
            board,
            move_history=[],
            legal_san=[board.san(move) for move in board.legal_moves],
            attempt=1,
            constrained_from=None,
            recent_errors=[],
        )
        lowered = prompt.lower()
        self.assertNotIn("legal san moves", lowered)
        self.assertNotIn("legal move list", lowered)
        self.assertNotIn("from the legal san list", lowered)
        self.assertNotIn("nh3", prompt.lower())
        self.assertIn("referee will check legality", lowered)

    def test_final_scene_copy_explains_system(self):
        lines = reel.final_explanation_lines()
        joined = " ".join(lines)
        self.assertIn("LLMs playing chess", joined)
        self.assertIn("benchmark", joined.lower())
        self.assertIn("central referee", joined.lower())
        self.assertIn("checks legality", joined.lower())
        self.assertNotIn("legal move list", joined.lower())


if __name__ == "__main__":
    unittest.main()
