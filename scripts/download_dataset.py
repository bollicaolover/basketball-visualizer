"""(Opcional) Descarga el dataset de detección de 11 clases para reentrenar RF-DETR.

Réplica del detector del cuaderno (`basketball-player-detection-3`). Usa la
`ROBOFLOW_API_KEY` del `.env` solo para la descarga.

Uso:
    python scripts/download_dataset.py --workspace <ws> [--project basketball-player-detection-3] [--version 4]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--project", default="basketball-player-detection-3")
    ap.add_argument("--version", type=int, default=4)
    ap.add_argument("--format", default="coco")
    ap.add_argument("--out", default="data/raw/basketball-player-detection")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent.parent
    load_dotenv(here / ".env")
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        raise SystemExit("Falta ROBOFLOW_API_KEY en el .env")

    from roboflow import Roboflow

    rf = Roboflow(api_key=api_key)
    project = rf.workspace(args.workspace).project(args.project)
    out = here / args.out
    print(f"[INFO] Descargando {args.project} v{args.version} ({args.format}) -> {out}")
    project.version(args.version).download(args.format, location=str(out))
    print(f"[OK] Dataset en {out}")


if __name__ == "__main__":
    main()
