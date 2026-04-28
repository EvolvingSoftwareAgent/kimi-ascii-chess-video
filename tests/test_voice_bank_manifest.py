import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_voice_bank_manifest import build_manifest, main as build_main


class VoiceBankManifestTests(unittest.TestCase):
    def test_manifest_uses_only_black_and_white_side_atoms(self):
        manifest = build_manifest()
        atom_ids = {sample["id"] for sample in manifest["samples"] if sample["role"] == "atom"}

        self.assertIn("white_possessive", atom_ids)
        self.assertIn("black_possessive", atom_ids)
        self.assertNotIn("kimi", atom_ids)
        self.assertNotIn("stockfish", atom_ids)
        self.assertEqual(manifest["sample_count_if_expanded"], 608)


if __name__ == "__main__":
    unittest.main()
