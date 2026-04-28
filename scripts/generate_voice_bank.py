#!/usr/bin/env python3
"""Generate voice-bank samples from assets/voice_bank/manifest.json.

Default provider is edge-tts because it can run as a long offline-ish batch on this
machine today. Qwen is intentionally a separate provider mode so Qwen setup can be
probed without changing the game-audio manifest.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path


TRANSIENT_EDGE_TTS_MARKERS = (
    "WSServerHandshakeError",
    "Invalid response status",
    "503",
    "Server disconnected",
    "Connection reset",
    "Cannot connect to host",
    "TimeoutError",
)


def is_complete_audio_file(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def is_transient_edge_tts_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return any(marker in text for marker in TRANSIENT_EDGE_TTS_MARKERS)


class QwenRuntimeOptions:
    def __init__(self, device: str, dtype: object, model_kwargs: dict):
        self.device = device
        self.dtype = dtype
        self.model_kwargs = model_kwargs


def resolve_qwen_runtime_options(device: str, dtype: str, flash_attn: bool, torch_module) -> QwenRuntimeOptions:
    resolved_device = device
    if device == "auto":
        resolved_device = "cuda:0" if torch_module.cuda.is_available() else "cpu"

    resolved_dtype_name = dtype
    if dtype == "auto":
        resolved_dtype_name = "bfloat16" if str(resolved_device).startswith("cuda") else "float32"
    dtype_map = {
        "bfloat16": torch_module.bfloat16,
        "bf16": torch_module.bfloat16,
        "float16": torch_module.float16,
        "fp16": torch_module.float16,
        "float32": torch_module.float32,
        "fp32": torch_module.float32,
    }
    if resolved_dtype_name not in dtype_map:
        raise ValueError(f"Unsupported Qwen dtype: {dtype}")

    model_kwargs = {"device_map": resolved_device, "torch_dtype": dtype_map[resolved_dtype_name]}
    if flash_attn and str(resolved_device).startswith("cuda"):
        model_kwargs["attn_implementation"] = "flash_attention_2"
    return QwenRuntimeOptions(device=resolved_device, dtype=dtype_map[resolved_dtype_name], model_kwargs=model_kwargs)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def expanded_samples(manifest: dict) -> list[dict]:
    out = []
    pieces = manifest["pieces"]
    for sample in manifest["samples"]:
        if sample["role"] == "atom":
            out.append({"id": sample["id"], "text": sample["text"], "relpath": sample["path"]})
        elif sample["role"] == "template":
            for piece in pieces:
                out.append({
                    "id": f"{sample['id']}_{piece}",
                    "text": sample["template"].format(piece=piece),
                    "relpath": sample["path_template"].format(piece=piece),
                    "piece": piece,
                    "template_id": sample["id"],
                })
    return out


async def generate_edge_tts(samples: list[dict], out_dir: Path, voice: str, limit: int | None, resume: bool) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise SystemExit("edge-tts is not installed. Run: python -m pip install edge-tts") from exc

    selected = samples[:limit] if limit else samples
    total = len(selected)
    for idx, sample in enumerate(selected, start=1):
        out_path = out_dir / sample["relpath"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if resume and is_complete_audio_file(out_path):
            print(f"[{idx}/{total}] skip {out_path}", flush=True)
            continue
        print(f"[{idx}/{total}] {sample['id']} -> {out_path}", flush=True)
        attempts = 4
        for attempt in range(1, attempts + 1):
            try:
                communicate = edge_tts.Communicate(sample["text"], voice)
                await communicate.save(str(out_path))
                break
            except Exception as exc:
                if out_path.exists() and out_path.stat().st_size == 0:
                    out_path.unlink()
                if attempt >= attempts or not is_transient_edge_tts_error(exc):
                    raise
                sleep_for = min(90, 10 * attempt * attempt)
                print(
                    f"[{idx}/{total}] transient edge-tts failure on attempt {attempt}/{attempts}: {exc}; "
                    f"sleeping {sleep_for}s",
                    flush=True,
                )
                await asyncio.sleep(sleep_for)


def write_audio_file(path: Path, wav, sample_rate: int) -> None:
    import numpy as np
    import soundfile as sf

    audio = np.asarray(wav, dtype="float32")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sample_rate)


def qwen_model_kind(tts_model) -> str:
    return getattr(getattr(tts_model, "model", None), "tts_model_type", "")


def generate_one_qwen_sample(
    tts_model,
    sample: dict,
    out_path: Path,
    *,
    language: str,
    speaker: str,
    instruct: str,
    max_new_tokens: int | None,
    generation_kwargs: dict | None = None,
    writer=write_audio_file,
) -> None:
    kwargs = dict(generation_kwargs or {})
    if max_new_tokens is not None:
        kwargs["max_new_tokens"] = max_new_tokens

    model_kind = qwen_model_kind(tts_model)
    if model_kind == "custom_voice":
        wavs, sample_rate = tts_model.generate_custom_voice(
            text=sample["text"],
            language=language,
            speaker=speaker,
            instruct=instruct,
            **kwargs,
        )
    elif model_kind == "voice_design":
        wavs, sample_rate = tts_model.generate_voice_design(
            text=sample["text"],
            language=language,
            instruct=instruct,
            **kwargs,
        )
    else:
        raise SystemExit(
            f"Qwen model type '{model_kind or 'unknown'}' is not wired for bank generation yet. "
            "Use a CustomVoice or VoiceDesign checkpoint."
        )
    writer(out_path, wavs[0], sample_rate)


def generate_qwen_tts(
    samples: list[dict],
    out_dir: Path,
    limit: int | None,
    resume: bool,
    *,
    model_id: str,
    device: str,
    dtype: str,
    flash_attn: bool,
    language: str,
    speaker: str,
    instruct: str,
    max_new_tokens: int | None,
    generation_kwargs: dict | None = None,
) -> None:
    try:
        import torch
        from qwen_tts import Qwen3TTSModel
    except ImportError as exc:
        raise SystemExit("qwen-tts is not installed in this venv yet; run scripts/probe_qwen_tts_setup.sh") from exc

    options = resolve_qwen_runtime_options(device=device, dtype=dtype, flash_attn=flash_attn, torch_module=torch)
    print(f"Loading Qwen TTS model {model_id} on {options.device} with dtype={options.dtype}", flush=True)
    tts_model = Qwen3TTSModel.from_pretrained(model_id, **options.model_kwargs)

    selected = samples[:limit] if limit else samples
    total = len(selected)
    for idx, sample in enumerate(selected, start=1):
        out_path = out_dir / sample["relpath"]
        if resume and is_complete_audio_file(out_path):
            print(f"[{idx}/{total}] skip {out_path}", flush=True)
            continue
        print(f"[{idx}/{total}] {sample['id']} -> {out_path}", flush=True)
        if out_path.exists() and out_path.stat().st_size == 0:
            out_path.unlink()
        generate_one_qwen_sample(
            tts_model,
            sample,
            out_path,
            language=language,
            speaker=speaker,
            instruct=instruct,
            max_new_tokens=max_new_tokens,
            generation_kwargs=generation_kwargs,
        )


def write_index(samples: list[dict], out_dir: Path) -> None:
    index = []
    for sample in samples:
        path = out_dir / sample["relpath"]
        if path.exists():
            index.append({**sample, "path": str(path), "bytes": path.stat().st_size})
    (out_dir / "generated_index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("assets/voice_bank/manifest.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("assets/voice_bank/generated/edge"))
    parser.add_argument("--provider", choices=["edge", "qwen"], default="edge")
    parser.add_argument("--voice", default="en-US-GuyNeural")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--qwen-model", default="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
    parser.add_argument("--qwen-device", default="auto")
    parser.add_argument("--qwen-dtype", default="auto", choices=["auto", "bfloat16", "bf16", "float16", "fp16", "float32", "fp32"])
    parser.add_argument("--qwen-flash-attn", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--qwen-language", default="English")
    parser.add_argument("--qwen-speaker", default="Dylan")
    parser.add_argument("--qwen-instruct", default="A focused cinematic chess commentator with crisp dramatic timing.")
    parser.add_argument("--qwen-max-new-tokens", type=int, default=256)
    parser.add_argument("--qwen-do-sample", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--qwen-temperature", type=float, default=None)
    parser.add_argument("--qwen-top-p", type=float, default=None)
    parser.add_argument("--qwen-top-k", type=int, default=None)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    samples = expanded_samples(manifest)
    generation_kwargs = {}
    if args.qwen_do_sample is not None:
        generation_kwargs["do_sample"] = args.qwen_do_sample
    if args.qwen_temperature is not None:
        generation_kwargs["temperature"] = args.qwen_temperature
    if args.qwen_top_p is not None:
        generation_kwargs["top_p"] = args.qwen_top_p
    if args.qwen_top_k is not None:
        generation_kwargs["top_k"] = args.qwen_top_k
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.provider == "edge":
        asyncio.run(generate_edge_tts(samples, args.out_dir, args.voice, args.limit, args.resume))
    else:
        generate_qwen_tts(
            samples,
            args.out_dir,
            args.limit,
            args.resume,
            model_id=args.qwen_model,
            device=args.qwen_device,
            dtype=args.qwen_dtype,
            flash_attn=args.qwen_flash_attn,
            language=args.qwen_language,
            speaker=args.qwen_speaker,
            instruct=args.qwen_instruct,
            max_new_tokens=args.qwen_max_new_tokens,
            generation_kwargs=generation_kwargs,
        )
    write_index(samples, args.out_dir)


if __name__ == "__main__":
    main()
