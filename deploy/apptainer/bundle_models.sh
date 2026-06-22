#!/usr/bin/env bash
# =============================================================================
# Empaqueta los PESOS del pipeline para portar el proyecto a otra máquina.
# -----------------------------------------------------------------------------
# En este servidor, varios modelos de `models/` son SYMLINKS al proyecto
# original (`/home/gdfraile/tfg/tfg-baloncesto-tacticas`). Esos enlaces se
# rompen en otra máquina. Este script los DEREFERENCIA (copia el contenido real)
# a un directorio portable que luego se mueve al host destino y se monta en el
# contenedor Apptainer con `--bind` (ver docs/reproducibilidad-apptainer.md).
#
# La imagen `tfg.sif` reproduce CÓDIGO + ENTORNO; los pesos van aparte (no se
# meten en la imagen). Este script cubre justamente esos pesos.
#
# Uso:
#   bash deploy/apptainer/bundle_models.sh                 # núcleo (~1,1 GB)
#   bash deploy/apptainer/bundle_models.sh --with-sam3     # + SAM3 (~7,7 GB)
#   bash deploy/apptainer/bundle_models.sh --all           # todo lo que exista
#   bash deploy/apptainer/bundle_models.sh --dest /ruta    # destino a medida
#
# Núcleo (siempre): detection, court-keypoints, jersey-ocr.
# SAM3 (--with-sam3): 6,5 GB. Alternativa sin moverlo: ejecutar el pipeline con
#   `--tracker botsort` (no necesita SAM3), o dejar que se descargue de
#   HuggingFace apuntando el modelo a `facebook/sam3`.
# Opcionales (--all): legibility, parseq-nba, reid-osnet (bootstrap/alternativas).
# =============================================================================
set -euo pipefail

# Raíz del repo (este script vive en deploy/apptainer/)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="$ROOT/deploy/apptainer/models_bundle"

CORE=(detection court-keypoints jersey-ocr)
OPTIONAL=(legibility parseq-nba reid-osnet)

WITH_SAM3=0
WITH_OPTIONAL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-sam3) WITH_SAM3=1; shift ;;
    --all)       WITH_SAM3=1; WITH_OPTIONAL=1; shift ;;
    --dest)      DEST="$2"; shift 2 ;;
    -h|--help)   sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; exit 2 ;;
  esac
done

GROUPS=("${CORE[@]}")
[[ $WITH_SAM3 -eq 1 ]] && GROUPS+=(sam3)
[[ $WITH_OPTIONAL -eq 1 ]] && GROUPS+=("${OPTIONAL[@]}")

echo "[INFO] Repo:    $ROOT"
echo "[INFO] Destino: $DEST/models"
mkdir -p "$DEST/models"

for g in "${GROUPS[@]}"; do
  src="$ROOT/models/$g"
  if [[ ! -e "$src" ]]; then
    echo "[SKIP] no existe: models/$g"
    continue
  fi
  echo "[COPY] models/$g  (dereferenciando symlinks)..."
  # -L: sigue los symlinks y copia el contenido real
  cp -rL "$src" "$DEST/models/"
done

echo
echo "[OK] Pesos empaquetados en: $DEST/models"
du -sh "$DEST/models" 2>/dev/null || true
cat <<EOF

Siguientes pasos para portar a otro host:
  1) Copia el bundle:   scp -r "$DEST/models" usuario@host:/ruta/destino/models
  2) En el host destino, monta los pesos en el contenedor con --bind:
       apptainer run --nv \\
         --bind /ruta/destino/models:/ruta/al/repo/models \\
         tfg.sif run.py data/clip.mp4
     (o simplemente coloca 'models/' junto al repo y ejecuta desde su raíz:
      Apptainer monta \$PWD por defecto y el pipeline lee rutas relativas.)
  3) Si NO mueves SAM3, usa el tracker alternativo:  run.py ... --tracker botsort
EOF
