"""(Opcional) Reentrena el detector de keypoints de cancha (YOLO-pose, 33 kpts).

Réplica de `basketball-court-detection-2`. Necesita un dataset YOLO-pose con
33 keypoints (data.yaml). Produce `models/court-keypoints/best.pt`.

Uso:
    python scripts/train_court_keypoints.py --data data/raw/court/data.yaml
"""

from __future__ import annotations

import argparse

from ultralytics import YOLO


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="ruta al data.yaml YOLO-pose")
    ap.add_argument("--model", default="yolo11m-pose.pt", help="pesos base")
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--project", default="models/court-keypoints")
    args = ap.parse_args()

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        project=args.project,
        name="train",
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
