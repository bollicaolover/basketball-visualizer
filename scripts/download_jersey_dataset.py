"""Descarga el dataset de dorsales de Roboflow para entrenar el OCR localmente.

Usa la `ROBOFLOW_API_KEY` del `.env` SOLO para descargar el dataset (no para
inferencia). Réplica del reconocedor del cuaderno (`basketball-jersey-numbers-ocr`)
pero entrenando un modelo propio.

El identificador del modelo del cuaderno es `basketball-jersey-numbers-ocr/3`.
El *workspace* que lo aloja se indica con `--workspace` (búscalo en la página de
Roboflow Universe del dataset; no viene en el id del modelo).

Formato de exportación: `folder` (clasificación) → un subdirectorio por número,
que es lo que consume `train_jersey_ocr.py`. Si el proyecto exporta el OCR en
otro formato, ajusta `--format`.

Uso:
    python scripts/download_jersey_dataset.py --workspace <ws> [--version 3]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="workspace de Roboflow que aloja el dataset")
    ap.add_argument("--project", default="basketball-jersey-numbers-ocr")
    ap.add_argument("--version", type=int, default=3)
    ap.add_argument("--format", default="folder", help="folder|multiclass|jsonl|...")
    ap.add_argument("--out", default="data/jersey-numbers")
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
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Descargando {args.project} v{args.version} ({args.format}) -> {out}")
    project.version(args.version).download(args.format, location=str(out))
    print(f"[OK] Dataset en {out}")


if __name__ == "__main__":
    main()
