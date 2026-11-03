# Built on the vLLM image on purpose: it already carries CUDA, torch and a
# transformers new enough for this checkpoint, so the embedding service adds a
# few megabytes rather than another multi-gigabyte pull.
ARG BASE_IMAGE=vllm/vllm-openai:v0.27.1-ubuntu2404
FROM ${BASE_IMAGE}

# The image ships fastapi, uvicorn and pillow already; this only fills gaps and
# leaves satisfied requirements at their pinned versions.
RUN python3 -m pip install --no-cache-dir "fastapi>=0.110" "uvicorn[standard]>=0.27" "pillow>=10.0"

WORKDIR /app
COPY serve_embed.py /app/serve_embed.py

EXPOSE 8000
# The base image's entrypoint is vLLM's API server; replace it.
# python3, not python: the base image has no `python` on PATH.
ENTRYPOINT ["python3", "-m", "uvicorn", "serve_embed:app", "--host", "0.0.0.0", "--port", "8000"]
