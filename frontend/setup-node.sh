#!/usr/bin/env bash
# Entorno de build del frontend, aislado y reproducible, SIN sudo.
#
# Descarga una versión fijada de Node.js (oficial, binario portable) dentro de
# ``frontend/.node/``, verifica su checksum SHA-256 y construye el frontend.
# No toca el Node del sistema ni requiere privilegios.
#
# Uso:
#   bash setup-node.sh           # instala Node portable + npm ci + npm run build
#   bash setup-node.sh install   # solo instala Node portable (sin build)
#   bash setup-node.sh dev       # instala + arranca el servidor de desarrollo
#   bash setup-node.sh shell     # imprime cómo añadir Node al PATH de tu shell
#
# Para revertir por completo (volver al estado actual):
#   rm -rf frontend/.node frontend/node_modules
set -euo pipefail

# --- Directorio del script (raíz del frontend) ------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Versión fijada (fuente única: .nvmrc) ----------------------------------
NODE_VERSION="$(tr -d '[:space:]' < .nvmrc)"
NODE_DIR="$SCRIPT_DIR/.node"
NODE_HOME="$NODE_DIR/node-v${NODE_VERSION}-linux-x64"
NODE_BIN="$NODE_HOME/bin"

# --- Checksums oficiales conocidos (de https://nodejs.org/dist/.../SHASUMS256.txt)
# Clave: "<version>-<arch>". Verifícalo si subes de versión.
declare -A NODE_SHA256=(
  ["20.18.0-x64"]="4543670b589593f8fa5f106111fd5139081da42bb165a9239f05195e405f240a"
)

# --- Detección de arquitectura ----------------------------------------------
RAW_ARCH="$(uname -m)"
case "$RAW_ARCH" in
  x86_64) ARCH="x64" ;;
  aarch64|arm64) ARCH="arm64" ;;
  *) echo "[ERROR] Arquitectura no soportada por este script: $RAW_ARCH" >&2; exit 1 ;;
esac

install_node() {
  if [ -x "$NODE_BIN/node" ]; then
    local have
    have="$("$NODE_BIN/node" --version 2>/dev/null || echo "")"
    if [ "$have" = "v${NODE_VERSION}" ]; then
      echo "[INFO] Node portable ya instalado: $have ($NODE_BIN)"
      return 0
    fi
  fi

  local key="${NODE_VERSION}-${ARCH}"
  local expected="${NODE_SHA256[$key]:-}"
  local tarball="node-v${NODE_VERSION}-linux-${ARCH}.tar.xz"
  local url="https://nodejs.org/dist/v${NODE_VERSION}/${tarball}"

  echo "[INFO] Descargando Node v${NODE_VERSION} (${ARCH})..."
  mkdir -p "$NODE_DIR"
  local tmp
  tmp="$(mktemp -d "$NODE_DIR/.dl.XXXXXX")"
  trap 'rm -rf "$tmp"' RETURN

  if command -v curl >/dev/null 2>&1; then
    curl -fSL --retry 3 -o "$tmp/$tarball" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$tmp/$tarball" "$url"
  else
    echo "[ERROR] Ni curl ni wget disponibles para descargar Node." >&2
    exit 1
  fi

  # --- Verificación de integridad ---
  local actual
  actual="$(sha256sum "$tmp/$tarball" | awk '{print $1}')"
  if [ -n "$expected" ]; then
    if [ "$actual" != "$expected" ]; then
      echo "[ERROR] Checksum NO coincide para $tarball" >&2
      echo "        esperado: $expected" >&2
      echo "        obtenido: $actual" >&2
      exit 1
    fi
    echo "[INFO] Checksum verificado OK."
  else
    echo "[WARN] Sin checksum fijado para '$key'. Verifica manualmente:" >&2
    echo "       $actual  $tarball" >&2
    echo "       (compáralo con https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt)" >&2
  fi

  echo "[INFO] Extrayendo en $NODE_DIR ..."
  # Limpia restos de una versión anterior antes de extraer la nueva.
  rm -rf "$NODE_DIR/node-v"*"-linux-${ARCH}"
  tar -xJf "$tmp/$tarball" -C "$NODE_DIR"
  echo "[INFO] Node portable instalado: $("$NODE_BIN/node" --version)"
}

ensure_path() {
  export PATH="$NODE_BIN:$PATH"
  # Evita que un ~/.npmrc global o un prefix del sistema interfieran.
  export npm_config_prefix="$NODE_HOME"
}

build() {
  ensure_path
  echo "[INFO] node: $(node --version)  npm: $(npm --version)"
  if [ -f package-lock.json ]; then
    echo "[INFO] npm ci (instalación reproducible desde package-lock.json)..."
    npm ci
  else
    echo "[WARN] Sin package-lock.json; usando npm install."
    npm install
  fi
  echo "[INFO] npm run build..."
  npm run build
  echo "[INFO] Build completado -> $SCRIPT_DIR/dist"
}

case "${1:-build}" in
  install)
    install_node
    ;;
  build|"")
    install_node
    build
    ;;
  dev)
    install_node
    ensure_path
    echo "[INFO] Arrancando servidor de desarrollo (Ctrl-C para salir)..."
    [ -d node_modules ] || npm ci
    npm run dev
    ;;
  shell)
    install_node
    echo "# Añade esto a tu shell para usar el Node portable manualmente:"
    echo "export PATH=\"$NODE_BIN:\$PATH\""
    ;;
  *)
    echo "Uso: bash setup-node.sh [install|build|dev|shell]" >&2
    exit 1
    ;;
esac
