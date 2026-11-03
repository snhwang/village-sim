# Serving the models yourself

Village Sim needs two models: a language model for speech, for rewording what
a villager hears and for writing new instructions, and an embedder for
retrieval. The main README's "Choosing the models" lists every option,
including hosted ones that need no GPU. This folder serves the two the paper
used, on your own machine.

| | Language model | Embedder |
|---|---|---|
| Model | `unsloth/Qwen3.8-27B-NVFP4` at f0b7c9e, with the DFlash draft `z-lab/Qwen3.8-27B-DFlash2` at 50307d4 | `nvidia/llama-nemotron-embed-vl-1b-v2` at 582e3bf |
| Port | 8355 (OpenAI-compatible) | 8360 |
| Needs | an NVIDIA Blackwell GPU (NVFP4). The paper used a 96 GB RTX PRO 6000 | a GPU, or just a CPU |

Exactly what served the paper's runs, down to every argument and image
digest, is in `results/paper_v4/SERVING.md`.

## Both models on an NVIDIA GPU, with Docker

You need Docker with the NVIDIA Container Toolkit. On Windows, run these
from WSL Ubuntu.

```bash
cd serving
cp .env.example .env              # then set HF_CACHE in it
pip install huggingface_hub
python prepare_models.py          # downloads both models at the pinned revisions
docker compose --profile llm --profile embed up -d
```

The first start compiles for a few minutes. Check both answer:

```bash
curl -s localhost:8355/v1/models | head -c 100; echo
curl -s localhost:8360/health; echo
```

`prepare_models.py` also patches the language model's tokenizer, which ships
with a 2048-token truncation compiled in. The default image is SGLang
v0.5.21. To serve the language model exactly as the paper's runs were served,
set `SGLANG_IMAGE` as `.env.example` shows. That build has SGLang issue 37817,
recorded in `results/paper_v4/SERVING.md`.

## The embedder on a CPU, without Docker

The embedder is small enough to run on a CPU. On an AMD Zen 4 or Zen 5
processor, whose AVX-512 BF16 instructions it uses, a short sentence takes
about a tenth of a second, which keeps up with a village at play speed. On
other CPUs it is slower. Its vectors match the GPU's to a cosine of 0.9999.

```bash
python -m venv .venv-embed && source .venv-embed/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install transformers fastapi "uvicorn[standard]" pillow requests numpy huggingface_hub
python serving/prepare_models.py --embed        # the model at the paper's revision
cd serving/embed && python -m uvicorn serve_embed:app --host 127.0.0.1 --port 8360
```

It takes about a minute to load, and about 3 GB of memory. Then run Village
Sim with the default `--embedder service`, and a language model from the main
README: a hosted one, or any OpenAI-compatible server.
