#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
python -m pip install 'qwen-tts==0.1.1' > outputs/qwen_tts_install.log 2>&1
python - <<'PY' > outputs/qwen_tts_probe.log 2>&1
import importlib.util
mods = ['qwen_tts', 'torch', 'transformers', 'torchaudio', 'soundfile']
for mod in mods:
    spec = importlib.util.find_spec(mod)
    print(mod, bool(spec), getattr(spec, 'origin', None) if spec else None)
try:
    import torch
    print('torch_version', torch.__version__)
    print('cuda_available', torch.cuda.is_available())
except Exception as exc:
    print('torch_error', repr(exc))
PY
