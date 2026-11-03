# What served the paper-v4 runs

Recorded 2026-10-25 from the running servers (`docker inspect`, the servers'
own info endpoints, the Hugging Face cache). Scott: "Let's just make it
documented exactly what served the sims", and "make sure we don't delete the
current model version or server in case we need to run it again".

## Which runs

Every paper-v4 run, each run's `meta.json` naming `http://localhost:8355/v1`
for the model and `http://localhost:8360` for the embedder:

- the six forty-day runs (`results/paper_runs.txt`, 20261022-*),
- the three ten-year runs (`results/long_runs_v4/runs.txt`, 20261023-012700-seed1 to 3),
- the village of 300 (20261024-005651-seed1),
- the counterfactual replays and every analysis that called the model.

The retrieval ablation calls only the embedder. Both containers below were
started on 2026-10-18 and ran without a restart through all of these.

## Machine

The home workstation: NVIDIA RTX PRO 6000 Blackwell Workstation Edition,
96 GB, driver 582.16, WSL 2 with Docker.

## Language model server (port 8355)

- Container `sglang_qwen38_27b`, started 2026-10-18T02:29:01Z.
- Image `lmsysorg/sglang@sha256:64e4914593690fbba806f19ac8b2237f78815e9046dd2fc874f630129f281607`,
  the 2026-09-09 `:dev` nightly. `GET /get_server_info` reports version
  `0.0.0.dev1+gdb272201a`. Kept locally as `paper-v4/sglang:2026-09-09-dev`.
- Model `unsloth/Qwen3.8-27B-NVFP4` at revision `f0b7c9e722f5565102fff8481c99e4d86ae099c7`.
- Draft model `z-lab/Qwen3.8-27B-DFlash2` at revision `50307d4c4cde6860d4eee73e2547cd786fe8e8a4`.
- Launch arguments, as `docker inspect` gives them:

```
python3 -m sglang.launch_server --trust-remote-code
  --model-path=unsloth/Qwen3.8-27B-NVFP4 --revision=f0b7c9e722f5565102fff8481c99e4d86ae099c7
  --tp-size=1 --served-model-name=Qwen3.8-27B --random-seed=1 --sampling-defaults=model
  --kv-cache-dtype=fp8_e4m3 --mem-fraction-static=0.60 --attention-backend=flashinfer
  --chunked-prefill-size=2048 --disable-prefill-cuda-graph --cuda-graph-max-bs-decode=8
  --disable-flashinfer-autotune
  --speculative-algorithm=DFLASH --speculative-draft-model-path=z-lab/Qwen3.8-27B-DFlash2
  --speculative-draft-model-revision=50307d4c4cde6860d4eee73e2547cd786fe8e8a4
  --speculative-num-draft-tokens=8 --speculative-draft-model-quantization=unquant
  --mamba-radix-cache-strategy=extra_buffer --mamba-ssm-dtype=bfloat16 --max-mamba-cache-size=96
  --max-running-requests=8 --enable-torch-compile --torch-compile-max-bs=4
  --num-continuous-decode-steps=2 --reasoning-parser=qwen3 --tool-call-parser=qwen3_coder
  --sleep-on-idle --host=0.0.0.0 --port=8000
```

The client side is Hearthwick's: thinking off (`thinking=False` through
BEAR), speech and rewording at temperature 0.8 with top-p 0.95 and top-k 20
and at most 80 tokens (the paper's Appendix B), and the counterfactual
replays at temperature 0 with one seed per pair.

## Embedder (port 8360)

- Container `nemotron_embed`, started 2026-10-18T11:19:34Z.
- Image `model-server/nemotron-embed:latest`, id
  `sha256:68c6b8fb61c8d1d47f233a7cac968cb6af857158ea40f67443809f62e1b2660f`,
  built 2026-10-18 from the model-server repository's `serve_embed.py`. Kept
  locally as `paper-v4/nemotron-embed:2026-10-18`, since a rebuild moves `latest`.
- Model `nvidia/llama-nemotron-embed-vl-1b-v2`. The service does not pin a
  revision. The cache's `refs/main` resolves to
  `582e3bf72aee355e3c59ed89de53543c5b0657ee`, loaded in bfloat16 on the GPU,
  with PyTorch 2.13.0+cu130 and Transformers 5.15.0. 2048 dimensions.

## A known issue in this SGLang build

The build has [sglang#37817](https://github.com/sgl-project/sglang/issues/37817).
With DFlash on a hybrid model such as Qwen3.8, a request that reuses a cached
prompt prefix can start from stale recurrent state, with no error. v0.5.21
fixes it. The model-server README ("Results served by the old SGLang build")
asks for prefix-sharing results from this build to carry the caveat, and
Hearthwick's prompts share prefixes. Every run and replay above shares the
condition, so comparisons between them are like for like. Scott, 2026-10-25:
the runs were consistent, so the paper keeps them and documents exactly what
served them. The same-prompt floor of the absorption counterfactual, on this
server at temperature 0, gave a different wording in 75 of 382 pairs (19.6%)
and a different keep or discard in 2, which includes any effect of the issue
along with ordinary nondeterminism.

## Keeping it

Do not remove the two tagged images or the three model snapshots (in
`/home/snhwang/.cache/huggingface/hub`: 22 GB, 3.6 GB and 3.2 GB). The images
are 53 GB and 31 GB. All of them sit in WSL's virtual disk, which is on D:.
An offline copy of all five, made 2026-10-25 with checksums and the steps to
restore them, is in `C:\Users\Scott\Documents\Work\hearthwick-paper-v4-serving`
on C:, which neither OneDrive nor Google Drive syncs. To
serve the paper's model again after the move to v0.5.21, set
`SGLANG_IMAGE=paper-v4/sglang:2026-09-09-dev` (or the digest above, while
Docker Hub keeps it) in model-server's `.env` and start `chat-sglang` with the
arguments above.

## The trial of the later build

rtx-lab's three trial runs (`results/dated_trial/runs.txt`, 2026-10-24 00:32
to about 10:42 EDT, Hearthwick 54146f5 with BEAR 1ceebc7) used the lab
workstation's own servers, as rtx-lab reported them on 2026-10-25:

- Machine: NVIDIA RTX PRO 6000 Blackwell Workstation Edition, 96 GB, Windows
  driver 596.86, Docker Engine 29.9.2 in WSL (Ubuntu 26.04).
- Both containers created and started 2026-10-23 20:00 UTC, with no restart
  during the trial.
- Language model server: the same image as at home (digest `64e49145`, build
  commit db272201a, version `0.0.0.dev1+gdb272201a`), the same model and draft
  model revisions (f0b7c9e, 50307d4), and launch arguments identical to the
  list above. Kept there as `paper-v4/sglang:2026-09-09-dev`.
- Embedder: a separate local build of model-server's embed image (id
  `sha256:9ec9f48be869611ca137fae1700d5ff58d9fe1e3c6a859b26b346a9676dbc525`,
  built 2026-10-23 from model-server 69b9c29), so its id differs from home's.
  The same model snapshot (582e3bf), PyTorch 2.13.0+cu130 and Transformers
  5.15.0. Kept there as `paper-v4/nemotron-embed:rtxlab-built-2026-10-23`.

So the trial differs from the paper-v4 runs in the code change, the machine
(its own GPU of the same model and its driver) and the embed image's build,
not in the model, the serving software or its settings.
