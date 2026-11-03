#!/usr/bin/env python3
"""Host-side preparation the compose file cannot do itself.

It reads .env from this folder and pins the embedder at the revision the
paper's runs used. Three jobs:

1. **Download weights on the host.** In-container downloads can fail under
   Docker Desktop on WSL: free-space checks through the bind-mounted HF cache
   report 0 bytes free and the downloader aborts even with plenty of room.
   Downloading natively sidesteps that, and the container then starts from a
   complete cache.
2. **Patch the unsloth Qwen3.8 tokenizer.** That checkpoint ships tokenizer.json
   with truncation compiled in at 2048 tokens, which silently cuts long
   prompts (forum #380244). Set it to null so vLLM can use the full context.
3. **Fetch what chat-sglang pins.** That service runs offline at fixed
   revisions of the chat model and its DFlash2 draft. SGLang also looks the
   draft up by "main", so the draft's refs/main must exist, and downloading a
   commit hash does not write it.

Run it where compose runs (on Windows, from WSL Ubuntu), so HF_CACHE is that
cache. Run once before the first `docker compose --profile llm up`, and again
after changing a model:

    python prepare_models.py            # both models
    python prepare_models.py --chat     # just the language model and draft
    python prepare_models.py --embed    # just the embedder
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CHAT = "unsloth/Qwen3.8-27B-NVFP4"
DEFAULT_EMBED = "nvidia/llama-nemotron-embed-vl-1b-v2"

# The revisions chat-sglang pins in docker-compose.yml. Change them together.
SGLANG_CHAT_REVISION = "f0b7c9e722f5565102fff8481c99e4d86ae099c7"
SGLANG_DRAFT = "z-lab/Qwen3.8-27B-DFlash2"
SGLANG_DRAFT_REVISION = "50307d4c4cde6860d4eee73e2547cd786fe8e8a4"
# The embedder's revision in the paper's runs. The embed service loads "main",
# so refs/main is pointed here when nothing else has set it.
EMBED_REVISION = "582e3bf72aee355e3c59ed89de53543c5b0657ee"


def load_env() -> dict[str, str]:
    """Read .env next to the compose file, without overriding the environment."""
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values


def hf_cache() -> Path:
    return Path(os.environ.get("HF_CACHE") or Path.home() / ".cache" / "huggingface")


def download(model_id: str, token: str | None, revision: str | None = None) -> bool:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is not installed on the host. Install it with")
        print("  pip install huggingface_hub")
        print("or let the container download the weights, which can fail on WSL.")
        return False
    label = f"{model_id}@{revision[:8]}" if revision else model_id
    print(f"Checking/downloading {label} ...")
    # Always the hub/ directory under HF_CACHE, which is what the containers
    # mount. Falling back to the default cache would leave them without weights.
    hub = hf_cache() / "hub"
    hub.mkdir(parents=True, exist_ok=True)
    snapshot_download(model_id, revision=revision, token=token or None, cache_dir=str(hub))
    print(f"  cached: {label}")
    return True


def ensure_refs_main(model_id: str, revision: str) -> None:
    """Point refs/main at a pinned revision if nothing else has set it.

    SGLang looks a draft model up by "main" even when given a revision, and
    downloading by commit hash writes no refs/main. An existing refs/main is
    left alone, with a warning when it names a different revision.
    """
    ref = hf_cache() / "hub" / f"models--{model_id.replace('/', '--')}" / "refs" / "main"
    if ref.exists():
        current = ref.read_text(encoding="utf-8").strip()
        if current != revision:
            print(f"  WARNING: {ref} names {current[:8]}, but compose pins {revision[:8]}")
        return
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(revision, encoding="utf-8")
    print(f"  wrote refs/main -> {revision[:8]} for {model_id}")


def patch_unsloth_tokenizer(model_id: str) -> None:
    """Remove the compiled-in 2048-token truncation from a tokenizer.json."""
    if "unsloth" not in model_id:
        return
    basename = model_id.replace("/", "--")
    pattern = str(hf_cache() / "hub" / f"models--{basename}" / "snapshots" / "*" / "tokenizer.json")
    paths = glob.glob(pattern)
    if not paths:
        print(f"  no tokenizer.json found for {model_id} (looked in {pattern})")
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("truncation") is None:
                print(f"  tokenizer already patched: {path}")
                continue
            data["truncation"] = None
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  patched tokenizer truncation: {path}")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  could not patch {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--chat", action="store_true", help="only the chat model")
    parser.add_argument("--embed", action="store_true", help="only the embedding model")
    args = parser.parse_args()
    both = not (args.chat or args.embed)

    load_env()
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        print("NOTE: HF_TOKEN is not set; gated checkpoints will fail to download.")
    print(f"Hugging Face cache: {hf_cache()}")

    if args.chat or both:
        model = os.environ.get("CHAT_MODEL", DEFAULT_CHAT)
        if download(model, token):
            # chat-sglang runs this exact revision offline, whatever main is.
            download(DEFAULT_CHAT, token, SGLANG_CHAT_REVISION)
            for patched in dict.fromkeys((model, DEFAULT_CHAT)):
                patch_unsloth_tokenizer(patched)
            if download(SGLANG_DRAFT, token, SGLANG_DRAFT_REVISION):
                ensure_refs_main(SGLANG_DRAFT, SGLANG_DRAFT_REVISION)
    if args.embed or both:
        embed = os.environ.get("EMBED_MODEL_ID", DEFAULT_EMBED)
        if embed == DEFAULT_EMBED:
            if download(embed, token, EMBED_REVISION):
                ensure_refs_main(embed, EMBED_REVISION)
        else:
            download(embed, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
