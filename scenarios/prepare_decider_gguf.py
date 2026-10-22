"""Download one pinned-on-run GGUF quant and matching published tokenizer.

Both quant variants resolve from the same mradermacher repository revision.
The manifest records the actual Hugging Face commit and SHA256. The GGUF
source model revision is not automatically provable from the repository tag;
do not silently treat this as BF16 v3 parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from huggingface_hub import HfApi, hf_hub_download, snapshot_download


REPO = "mradermacher/decider-4b-GGUF"
TOKENIZER_REPO = "Mapika/decider-4b-GGUF"
PATTERNS = [
    "config.json", "decider_config.json", "tokenizer.json",
    "tokenizer_config.json", "special_tokens_map.json",
    "*.jinja", "vocab.json", "merges.txt", "added_tokens.json",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quant", required=True, choices=("Q2_K", "Q4_K_M"))
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    api = HfApi()
    quant_info = api.model_info(REPO, files_metadata=True)
    # Use an explicit resolved commit for both variants; never download from
    # a moving branch after resolving the listed filenames.
    qsha = quant_info.sha
    options = [
        item.rfilename for item in quant_info.siblings
        if item.rfilename.lower().endswith(".gguf")
        and re.search(r"(?:^|[-_.])" + re.escape(args.quant) + r"\.gguf$",
                      item.rfilename, re.IGNORECASE)
    ]
    if len(options) != 1:
        raise ValueError(f"Expected one {args.quant} GGUF in {REPO}, found {options}")
    filename = options[0]
    if "/" in filename or filename.startswith("."):
        raise ValueError("Expected a single-file GGUF at repository root")
    tokenizer_info = api.model_info(TOKENIZER_REPO)
    tsha = tokenizer_info.sha

    args.model_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=TOKENIZER_REPO, revision=tsha,
        allow_patterns=PATTERNS, local_dir=str(args.model_dir),
        max_workers=3,
    )
    for required in ("decider_config.json", "tokenizer.json"):
        if not (args.model_dir / required).is_file():
            raise RuntimeError(f"Model tokenizer/config missing: {required}")

    downloaded = hf_hub_download(repo_id=REPO, filename=filename, revision=qsha)
    path = args.model_dir / filename
    if not path.exists():
        shutil.copyfile(downloaded, path)
    h = hashlib.sha256()
    with path.open("rb") as file:
        while data := file.read(8 * 1024 * 1024):
            h.update(data)
    size = path.stat().st_size
    if args.quant == "Q2_K" and not 1_500_000_000 < size < 2_500_000_000:
        raise ValueError("Unexpected Q2_K GGUF file size")
    if args.quant == "Q4_K_M" and not 2_300_000_000 < size < 3_400_000_000:
        raise ValueError("Unexpected Q4_K_M GGUF file size")
    data = {
        "quant": args.quant,
        "gguf_file": filename,
        "sha256": h.hexdigest(),
        "size_bytes": size,
        "quant_repo": REPO,
        "quant_repo_revision": qsha,
        "tokenizer_repo": TOKENIZER_REPO,
        "tokenizer_repo_revision": tsha,
        "source_finetune_identity": "UNVERIFIED against Ollaya BF16 v3",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print(json.dumps(data, sort_keys=True))


if __name__ == "__main__":
    main()
