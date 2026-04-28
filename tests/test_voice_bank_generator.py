import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_voice_bank.py"

spec = importlib.util.spec_from_file_location("generate_voice_bank", SCRIPT)
generate_voice_bank = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_voice_bank)


class VoiceBankGeneratorTests(unittest.TestCase):
    def test_edge_tts_503_websocket_handshake_is_transient(self):
        exc = Exception("WSServerHandshakeError: 503, message='Invalid response status'")

        self.assertTrue(generate_voice_bank.is_transient_edge_tts_error(exc))

    def test_zero_byte_resume_file_is_regenerated(self):
        self.assertFalse(generate_voice_bank.is_complete_audio_file(Path("missing.ogg")))

    def test_qwen_auto_runtime_uses_cpu_safe_defaults_without_cuda(self):
        class FakeCuda:
            @staticmethod
            def is_available():
                return False

        class FakeTorch:
            cuda = FakeCuda()
            float32 = "float32"
            bfloat16 = "bfloat16"
            float16 = "float16"

        options = generate_voice_bank.resolve_qwen_runtime_options(
            device="auto",
            dtype="auto",
            flash_attn=True,
            torch_module=FakeTorch,
        )

        self.assertEqual(options.device, "cpu")
        self.assertEqual(options.dtype, "float32")
        self.assertEqual(options.model_kwargs, {"device_map": "cpu", "torch_dtype": "float32"})

    def test_qwen_custom_voice_generation_writes_audio(self):
        calls = []

        class FakeInnerModel:
            tts_model_type = "custom_voice"

        class FakeQwenModel:
            model = FakeInnerModel()

            def generate_custom_voice(self, **kwargs):
                calls.append(kwargs)
                return [[0.0, 0.25, -0.25]], 24000

        written = []
        generate_voice_bank.generate_one_qwen_sample(
            FakeQwenModel(),
            {"id": "white_possessive", "text": "White's", "relpath": "atoms/white_possessive.ogg"},
            Path("out.ogg"),
            language="English",
            speaker="Dylan",
            instruct="A focused cinematic chess commentator.",
            max_new_tokens=64,
            generation_kwargs={
                "do_sample": True,
                "temperature": 1.05,
                "top_p": 0.92,
                "top_k": 80,
            },
            writer=lambda path, wav, sample_rate: written.append((path, wav, sample_rate)),
        )

        self.assertEqual(written, [(Path("out.ogg"), [0.0, 0.25, -0.25], 24000)])
        self.assertEqual(calls[0]["text"], "White's")
        self.assertEqual(calls[0]["language"], "English")
        self.assertEqual(calls[0]["speaker"], "Dylan")
        self.assertEqual(calls[0]["instruct"], "A focused cinematic chess commentator.")
        self.assertEqual(calls[0]["max_new_tokens"], 64)
        self.assertIs(calls[0]["do_sample"], True)
        self.assertEqual(calls[0]["temperature"], 1.05)
        self.assertEqual(calls[0]["top_p"], 0.92)
        self.assertEqual(calls[0]["top_k"], 80)


if __name__ == "__main__":
    unittest.main()
