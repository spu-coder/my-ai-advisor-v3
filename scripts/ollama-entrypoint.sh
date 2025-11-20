#!/usr/bin/env bash
set -euo pipefail

MODEL="${OLLAMA_MODEL:-llama3:8b}"

echo "[ollama-entrypoint] Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Give the server a few seconds to boot before pulling models
sleep 5

if ollama list | grep -q "${MODEL}"; then
  echo "[ollama-entrypoint] Model ${MODEL} already present."
else
  echo "[ollama-entrypoint] Pulling model ${MODEL}..."
  if ! ollama pull "${MODEL}"; then
    echo "[ollama-entrypoint] Failed to pull model ${MODEL}."
  fi
fi

echo "[ollama-entrypoint] Ready. Waiting for Ollama server process ${OLLAMA_PID}."
wait "${OLLAMA_PID}"

