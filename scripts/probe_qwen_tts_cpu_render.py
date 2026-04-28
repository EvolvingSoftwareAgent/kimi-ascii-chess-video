#!/usr/bin/env python3
"""CPU render probe for local qwen-tts install."""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

import soundfile as sf
import torch

from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "outputs" / "qwen_cpu_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_wav = out_dir / "qwen_cpu_probe.wav"
    meta_path = out_dir / "qwen_cpu_probe.json"

    ckpt = os.environ.get("QWEN_TTS_CKPT", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    text = os.environ.get("QWEN_TTS_TEXT", "White to move.")
    speaker = os.environ.get("QWEN_TTS_SPEAKER", "Vivian")

    meta = {
        "checkpoint": ckpt,
        "text": text,
        "speaker": speaker,
        "python": sys.version,
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device": "cpu",
        "dtype": "float32",
        "started_at": time.time(),
    }

    log(f"starting Qwen CPU render probe: ckpt={ckpt!r}")
    log(f"torch={torch.__version__}; cuda_available={torch.cuda.is_available()}")

    try:
        load_start = time.time()
        tts = Qwen3TTSModel.from_pretrained(
            ckpt,
            device_map="cpu",
            dtype=torch.float32,
            attn_implementation=None,
        )
        meta["load_seconds"] = time.time() - load_start
        meta["model_type"] = getattr(tts.model, "tts_model_type", None)
        meta["tokenizer_type"] = getattr(tts.model, "tokenizer_type", None)
        meta["tts_model_size"] = getattr(tts.model, "tts_model_size", None)
        log(f"model loaded in {meta['load_seconds']:.1f}s; type={meta['model_type']}")

        if callable(getattr(tts.model, "get_supported_speakers", None)):
            speakers = tts.model.get_supported_speakers()
            meta["supported_speakers_sample"] = list(speakers)[:20] if speakers else []
            log(f"supported speakers sample: {meta['supported_speakers_sample']}")
            if speaker not in speakers and speakers:
                speaker = list(speakers)[0]
                meta["speaker"] = speaker
                log(f"requested speaker unavailable; using {speaker!r}")

        gen_start = time.time()
        wavs, sr = tts.generate_custom_voice(
            text=text,
            language="English",
            speaker=speaker,
            instruct="clear cinematic narrator voice",
            max_new_tokens=120,
            do_sample=False,
        )
        meta["generate_seconds"] = time.time() - gen_start
        wav = wavs[0]
        sf.write(out_wav, wav, sr)
        meta.update({
            "success": True,
            "sample_rate": sr,
            "samples": int(len(wav)),
            "duration_seconds": float(len(wav) / sr),
            "output_wav": str(out_wav),
            "finished_at": time.time(),
        })
        log(f"rendered {out_wav} duration={meta['duration_seconds']:.2f}s generate={meta['generate_seconds']:.1f}s")
        return 0
    except Exception as exc:
        meta.update({
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "finished_at": time.time(),
        })
        log(f"FAILED {type(exc).__name__}: {exc}")
        return 1
    finally:
        meta["total_seconds"] = time.time() - meta["started_at"]
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"metadata written: {meta_path}")


if __name__ == "__main__":
    raise SystemExit(main())
