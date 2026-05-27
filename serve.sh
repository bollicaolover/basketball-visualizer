#!/usr/bin/env bash
# Compila el frontend y arranca el backend FastAPI (que sirve los estáticos).
# Uso: bash serve.sh [--port 8000] [--host 0.0.0.0]
set -e

PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

# Directorio raíz del proyecto (donde está este script)
cd "$(dirname "$0")"

# Ruta ABSOLUTA al Node embebido: `npm --prefix frontend` ejecuta el script con
# cwd=frontend/, así que una ruta relativa en PATH no resolvería (caería al Node
# del sistema, demasiado antiguo para Vite 5).
NODE_BIN="$PWD/frontend/.node/node-v20.18.0-linux-x64/bin"

echo "[INFO] Compilando frontend..."
PATH="$NODE_BIN:$PATH" npm --prefix frontend run build

UVICORN="$(conda run -n tfg-baloncesto which uvicorn 2>/dev/null \
  || echo /home/gdfraile/miniconda3/envs/tfg-baloncesto/bin/uvicorn)"

echo "[INFO] Iniciando servidor en http://${HOST}:${PORT}"
exec "$UVICORN" backend.app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload
