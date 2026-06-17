"""Enlaza los checkpoints ya entrenados desde el proyecto original.

Trae a `tfg-junio/models/` los modelos propios que ya existen en
`tfg-baloncesto-tacticas` (detección RF-DETR 11 clases, SAM 3, keypoints de
cancha, y opcionalmente PARSeq/legibility como puente de bootstrap del OCR).

Por defecto crea **symlinks** (no duplica los GBs de SAM 3 ni los checkpoints).
Usa `--copy` para copiar de verdad.

Uso:
    python scripts/fetch_models.py            # symlinks a todo lo disponible
    python scripts/fetch_models.py --copy     # copia física
    python scripts/fetch_models.py --src /ruta/al/proyecto/original
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DEFAULT_SRC = Path("/home/gdfraile/tfg/tfg-baloncesto-tacticas")

# (origen relativo al src, destino relativo a tfg-junio/, ¿es directorio?)
ITEMS = [
    ("models/artifacts/checkpoint_best_ema.pth", "models/detection/checkpoint_best_ema.pth", False),
    ("data/raw/basketball-player-detection", "data/raw/basketball-player-detection", True),
    ("models/artifacts/court-keypoints/best.pt", "models/court-keypoints/best.pt", False),
    ("models/artifacts/sam3", "models/sam3", True),
    # Puente de bootstrap opcional para el OCR (hasta entrenar el SmolVLM2):
    ("models/artifacts/parseq-nba/parseq_nba_v2.ckpt", "models/parseq-nba/parseq_nba_v2.ckpt", False),
    ("models/artifacts/legibility/legibility_soccernet.pth", "models/legibility/legibility_soccernet.pth", False),
    ("models/artifacts/reid-osnet/osnet_x0_25_sportsmot.pt", "models/reid-osnet/osnet_x0_25_sportsmot.pt", False),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--copy", action="store_true", help="copia física en vez de symlink")
    args = ap.parse_args()
    src_root = args.src.resolve()

    here = Path(__file__).resolve().parent.parent
    for rel_src, rel_dst, is_dir in ITEMS:
        src = (src_root / rel_src).resolve()
        dst = here / rel_dst
        if not src.exists():
            print(f"[SKIP] no existe en origen: {src}")
            continue
        if dst.exists() or dst.is_symlink():
            print(f"[SKIP] ya existe: {dst}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if args.copy:
            if is_dir:
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            print(f"[COPY] {src}  ->  {dst}")
        else:
            dst.symlink_to(src)
            print(f"[LINK] {dst}  ->  {src}")


if __name__ == "__main__":
    main()
