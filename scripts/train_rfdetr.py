"""(Opcional) Reentrena RF-DETR sobre las 11 clases de `basketball-player-detection`.

Produce un checkpoint propio equivalente al ya enlazado en
`models/detection/checkpoint_best_ema.pth`. Ajusta `devices`/`batch_size` a tu GPU.

Uso:
    python scripts/train_rfdetr.py
"""

from __future__ import annotations

import argparse

from rfdetr import RFDETRBase


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/raw/basketball-player-detection")
    ap.add_argument("--out", default="models/detection")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--resolution", type=int, default=672)
    ap.add_argument("--devices", type=int, default=1)
    args = ap.parse_args()

    model = RFDETRBase()
    model.train(
        dataset_dir=args.dataset,
        output_dir=args.out,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=1e-4,
        resolution=args.resolution,
        devices=args.devices,
        early_stopping_patience=10,
        early_stopping_min_delta=0.001,
        dropout=0.1,
        save_best=True,
        num_workers=4,
        verbose=True,
    )


if __name__ == "__main__":
    main()
