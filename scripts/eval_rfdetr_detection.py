"""Evaluación del detector RF-DETR de `tfg-junio` (11 clases).

Usa el mismo wrapper que el pipeline (`pipeline/detection/rfdetr_detector.py`)
y las clases de `pipeline/config.py`. Calcula mAP@50, mAP@50-95 (COCO),
Precision, Recall y F1 por clase sobre el split test.

Uso:
    python scripts/eval_rfdetr_detection.py \
        --device cuda \
        --output docs/results/rfdetr_detection_metrics.json

Requisitos previos:
    python scripts/fetch_models.py   # checkpoint + dataset (symlinks)
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import supervision as sv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import CLASS_NAMES, DetectionSettings, IN_POSSESSION_CLASS
from pipeline.detection.rfdetr_detector import RFDETRDetector, NUM_CLASSES

DEFAULT_WEIGHTS = ROOT / "models/detection/checkpoint_best_ema.pth"
DEFAULT_DATASET = ROOT / "data/raw/basketball-player-detection"
FALLBACK_DATASET = (
    ROOT.parent / "tfg-baloncesto-tacticas/data/raw/basketball-player-detection"
)
IOU_THRESH = 0.5
LATENCY_WARMUP = 10
LATENCY_ITERS = 50


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluación RF-DETR (tfg-junio)")
    p.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    p.add_argument("--dataset", type=Path, default=None)
    p.add_argument("--split", default="test", choices=("train", "valid", "test"))
    p.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="umbral para P/R/F1 greedy (producción posesión: possession.class5_score_threshold)",
    )
    p.add_argument("--resolution", type=int, default=None)
    p.add_argument("--variant", default=None)
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/results/rfdetr_detection_metrics.json",
    )
    return p.parse_args()


def resolve_dataset(path: Path | None) -> Path:
    if path is not None:
        return path
    if DEFAULT_DATASET.is_dir():
        return DEFAULT_DATASET
    if FALLBACK_DATASET.is_dir():
        return FALLBACK_DATASET
    raise FileNotFoundError(
        "Dataset no encontrado. Ejecuta `python scripts/fetch_models.py` "
        f"o pasa --dataset (esperado en {DEFAULT_DATASET})."
    )


def box_iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def match_greedy(
    preds: list[tuple[np.ndarray, float]],
    gts: list[np.ndarray],
) -> tuple[int, int, int]:
    preds = sorted(preds, key=lambda x: -x[1])
    matched: set[int] = set()
    tp = 0
    for box, _ in preds:
        best_iou, best_j = 0.0, -1
        for j, gt in enumerate(gts):
            if j in matched:
                continue
            iou = box_iou(box, gt)
            if iou > best_iou:
                best_iou, best_j = iou, j
        if best_iou >= IOU_THRESH and best_j >= 0:
            tp += 1
            matched.add(best_j)
    fp = len(preds) - tp
    fn = len(gts) - len(matched)
    return tp, fp, fn


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def coco_xywh_to_xyxy(bbox: list[float]) -> np.ndarray:
    x, y, w, h = bbox
    return np.array([x, y, x + w, y + h], dtype=np.float32)


def detections_to_coco(
    dets: sv.Detections, img_id: int, idx_to_coco_id: dict[int, int],
) -> list[dict]:
    out: list[dict] = []
    if dets is None or len(dets) == 0:
        return out
    for box, score, class_id in zip(dets.xyxy, dets.confidence, dets.class_id):
        cls = int(class_id)
        if cls < 0 or cls >= NUM_CLASSES:
            continue
        x1, y1, x2, y2 = map(float, box)
        out.append(
            {
                "image_id": img_id,
                "category_id": idx_to_coco_id[cls],
                "bbox": [x1, y1, x2 - x1, y2 - y1],
                "score": float(score),
            }
        )
    return out


def run_coco_eval(
    detector: RFDETRDetector,
    split_dir: Path,
    ann_file: Path,
) -> tuple[float, float, dict[str, float]]:
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    coco_gt = COCO(str(ann_file))
    categories = sorted(coco_gt.loadCats(coco_gt.getCatIds()), key=lambda c: c["id"])
    idx_to_coco_id = {i: cat["id"] for i, cat in enumerate(categories)}
    name_by_id = {cat["id"]: cat["name"] for cat in categories}

    detections: list[dict] = []
    for img_id in coco_gt.getImgIds():
        img_info = coco_gt.loadImgs(img_id)[0]
        img_path = split_dir / img_info["file_name"]
        frame_bgr = cv2.imread(str(img_path))
        if frame_bgr is None:
            raise FileNotFoundError(f"No se pudo leer: {img_path}")
        dets = detector.detect(frame_bgr, threshold=0.01)
        detections.extend(detections_to_coco(dets, img_id, idx_to_coco_id))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(detections, tmp)
        det_path = tmp.name

    coco_dt = coco_gt.loadRes(det_path)
    Path(det_path).unlink(missing_ok=True)

    coco_eval = COCOeval(coco_gt, coco_dt, iouType="bbox")
    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()

    ap50_by_class: dict[str, float] = {}
    precisions = coco_eval.eval["precision"]
    for idx, cat in enumerate(categories):
        precision = precisions[0, :, idx, 0, -1]
        precision = precision[precision > -1]
        ap50_by_class[name_by_id[cat["id"]]] = float(precision.mean()) if precision.size else 0.0

    return float(coco_eval.stats[1]), float(coco_eval.stats[0]), ap50_by_class


def run_greedy_prf(
    detector: RFDETRDetector,
    split_dir: Path,
    ann_file: Path,
    conf: float,
) -> dict[str, dict]:
    from pycocotools.coco import COCO

    coco_gt = COCO(str(ann_file))
    tp_c = {i: 0 for i in range(NUM_CLASSES)}
    fp_c = {i: 0 for i in range(NUM_CLASSES)}
    fn_c = {i: 0 for i in range(NUM_CLASSES)}

    for img_id in coco_gt.getImgIds():
        img_info = coco_gt.loadImgs(img_id)[0]
        img_path = split_dir / img_info["file_name"]
        frame_bgr = cv2.imread(str(img_path))
        anns = coco_gt.loadAnns(coco_gt.getAnnIds(imgIds=img_id))

        gts_by_cls: dict[int, list[np.ndarray]] = {i: [] for i in range(NUM_CLASSES)}
        for ann in anns:
            cls_id = int(ann["category_id"])
            gts_by_cls.setdefault(cls_id, []).append(coco_xywh_to_xyxy(ann["bbox"]))

        dets = detector.detect(frame_bgr, threshold=conf)
        preds_by_cls: dict[int, list[tuple[np.ndarray, float]]] = {
            i: [] for i in range(NUM_CLASSES)
        }
        if dets is not None and len(dets) > 0:
            for box, score, class_id in zip(dets.xyxy, dets.confidence, dets.class_id):
                cls_id = int(class_id)
                if 0 <= cls_id < NUM_CLASSES:
                    preds_by_cls[cls_id].append(
                        (np.asarray(box, dtype=np.float32), float(score)),
                    )

        for cls_id in range(NUM_CLASSES):
            tp, fp, fn = match_greedy(preds_by_cls[cls_id], gts_by_cls[cls_id])
            tp_c[cls_id] += tp
            fp_c[cls_id] += fp
            fn_c[cls_id] += fn

    per_class: dict[str, dict] = {}
    for cls_id, name in enumerate(CLASS_NAMES):
        p, r, f1 = prf(tp_c[cls_id], fp_c[cls_id], fn_c[cls_id])
        per_class[name] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "support_gt": tp_c[cls_id] + fn_c[cls_id],
            "tp": tp_c[cls_id],
            "fp": fp_c[cls_id],
            "fn": fn_c[cls_id],
        }
    return per_class


def measure_latency(detector: RFDETRDetector, split_dir: Path, device: str) -> tuple[float, float]:
    import torch

    images = sorted(split_dir.glob("*.jpg")) or sorted(split_dir.glob("*.png"))
    frame_bgr = cv2.imread(str(images[0]))
    for _ in range(LATENCY_WARMUP):
        detector.detect(frame_bgr)
    if device != "cpu" and torch.cuda.is_available():
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(LATENCY_ITERS):
        detector.detect(frame_bgr)
    if device != "cpu" and torch.cuda.is_available():
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    return elapsed / LATENCY_ITERS * 1000, LATENCY_ITERS / elapsed


def main() -> None:
    args = parse_args()
    dataset = resolve_dataset(args.dataset)
    split_dir = dataset / args.split
    ann_file = split_dir / "_annotations.coco.json"
    if not args.weights.is_file():
        raise FileNotFoundError(
            f"Sin checkpoint: {args.weights}\n"
            "Ejecuta `python scripts/fetch_models.py`."
        )
    if not ann_file.is_file():
        raise FileNotFoundError(f"Sin anotaciones COCO: {ann_file}")

    det_kwargs: dict = {"device": args.device}
    if args.resolution is not None:
        det_kwargs["resolution"] = args.resolution
    if args.variant is not None:
        det_kwargs["variant"] = args.variant
    settings = DetectionSettings(
        checkpoint_path=str(args.weights),
        **det_kwargs,
    )

    print(f"[INFO] Detector tfg-junio: {settings.variant} @ {args.weights}")
    detector = RFDETRDetector(settings)

    print(f"[INFO] Dataset: {dataset} ({args.split})")
    print("[INFO] Calculando mAP COCO...")
    map50, map5095, ap50_by_class = run_coco_eval(detector, split_dir, ann_file)

    print(f"[INFO] Calculando P/R/F1 greedy (conf={args.conf})...")
    per_class = run_greedy_prf(detector, split_dir, ann_file, args.conf)
    for name in CLASS_NAMES:
        per_class[name]["ap50"] = round(ap50_by_class.get(name, 0.0), 4)

    print("[INFO] Midiendo latencia...")
    ms, fps = measure_latency(detector, split_dir, args.device)

    pip = CLASS_NAMES[IN_POSSESSION_CLASS]
    report = {
        "project": "tfg-junio",
        "detector": "pipeline/detection/rfdetr_detector.py",
        "weights": str(args.weights),
        "dataset": f"{dataset.name} ({args.split} split)",
        "resolution": settings.resolution,
        "production_score_threshold": settings.score_threshold,
        "possession_class5_score_threshold": 0.55,
        "iou_threshold": IOU_THRESH,
        "conf_threshold_greedy": args.conf,
        "mAP50": round(map50, 4),
        "mAP50_95": round(map5095, 4),
        "latency_ms_per_frame": round(ms, 2),
        "fps_detector": round(fps, 1),
        "per_class": per_class,
    }

    print(f"\n=== RF-DETR tfg-junio ({args.split}) ===")
    print(f"  mAP@50:       {map50:.4f}")
    print(f"  mAP@50-95:    {map5095:.4f}")
    print(f"  Latencia:     {ms:.1f} ms/frame  ({fps:.1f} FPS)")
    print(f"\n  {pip}:")
    m = per_class[pip]
    print(
        f"    AP@50={m['ap50']:.3f}  P={m['precision']:.3f}  "
        f"R={m['recall']:.3f}  F1={m['f1']:.3f}  (GT n={m['support_gt']})"
    )
    print("\n  Todas las clases (AP@50 | P/R/F1):")
    for name in CLASS_NAMES:
        mc = per_class[name]
        print(
            f"    {name:<22} AP@50={mc['ap50']:.3f}  "
            f"P={mc['precision']:.3f}  R={mc['recall']:.3f}  F1={mc['f1']:.3f}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[INFO] Guardado en {args.output}")


if __name__ == "__main__":
    main()
