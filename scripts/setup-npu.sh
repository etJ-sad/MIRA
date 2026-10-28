#!/usr/bin/env bash
# Lädt LLM und Embedding-Modell für die NPU (Docker) und trägt beide in models/config.json ein.
set -euo pipefail
IMAGE="${OVMS_IMAGE:-openvino/model_server:latest-gpu}"
LLM_MODEL="${MIRA_LLM_MODEL:-OpenVINO/Qwen3-8B-int4-cw-ov}"
EMBED_MODEL="${MIRA_EMBED_MODEL:-OpenVINO/Qwen3-Embedding-0.6B-int8-ov}"
MAX_PROMPT_LEN="${MAX_PROMPT_LEN:-4000}"

mkdir -p models
run() { docker run --rm -u "$(id -u):$(id -g)" -v "$(pwd)/models:/models:rw" "$IMAGE" "$@"; }

run --pull --source_model "$LLM_MODEL" --model_repository_path /models --target_device NPU --task text_generation \
    --cache_dir /models/.ov_cache --enable_prefix_caching true --max_prompt_len "$MAX_PROMPT_LEN"
run --add_to_config --config_path /models/config.json --model_name "$LLM_MODEL" --model_path "/models/$LLM_MODEL"

run --pull --source_model "$EMBED_MODEL" --model_repository_path /models --target_device NPU --task embeddings \
    --pooling LAST --max_length 1000
run --add_to_config --config_path /models/config.json --model_name "$EMBED_MODEL" --model_path "/models/$EMBED_MODEL"

echo "Fertig. Starten mit: docker compose up -d"
