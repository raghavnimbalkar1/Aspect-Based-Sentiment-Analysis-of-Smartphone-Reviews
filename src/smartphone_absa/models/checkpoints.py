"""Download only a pinned checkpoint's inert configuration, tokenizer, and weights."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHECKPOINT = "yangheng/deberta-v3-base-absa-v1.1"
REVISION = "10c9dff335a44073e1352360c3a7bc54dc58eb01"
TRANSFER_ID = "deberta-absa-10c9dff3"
TRANSFER_FILES = (
    "config.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "spm.model",
    "model.safetensors",
)


def download_checkpoint(output: Path) -> dict:
    from huggingface_hub import snapshot_download

    output.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        CHECKPOINT,
        revision=REVISION,
        allow_patterns=list(TRANSFER_FILES),
        local_dir=output,
        max_workers=2,
    )
    files = {}
    for name in TRANSFER_FILES:
        path = output / name
        if not path.exists():
            raise ValueError(f"Checkpoint is incomplete: missing {name}")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        files[name] = {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}
    metadata = {
        "id": TRANSFER_ID,
        "kind": "transferred_absa",
        "checkpoint": CHECKPOINT,
        "revision": REVISION,
        "license": "MIT",
        "files": files,
        "task": "Explicit aspect detection plus transferred three-state sentiment classification",
        "smartphone_finetuned": False,
        "smartphone_evaluated": False,
    }
    (output / "checkpoint.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata
