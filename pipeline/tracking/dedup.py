"""Supresión de detecciones duplicadas del mismo jugador (IoU alto)."""

from __future__ import annotations

import numpy as np
import supervision as sv


def _bbox_iou(a: np.ndarray, b: np.ndarray) -> float:
    ix1 = max(float(a[0]), float(b[0]))
    iy1 = max(float(a[1]), float(b[1]))
    ix2 = min(float(a[2]), float(b[2]))
    iy2 = min(float(a[3]), float(b[3]))
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def deduplicate_player_detections(
    detections: sv.Detections,
    *,
    min_iou: float = 0.45,
    enabled: bool = True,
) -> sv.Detections:
    if not enabled or detections is None or len(detections) < 2:
        return detections

    n = len(detections)
    confidences = (
        detections.confidence
        if detections.confidence is not None
        else np.ones(n, dtype=np.float32)
    )
    drop: set[int] = set()

    for i in range(n):
        if i in drop:
            continue
        for j in range(i + 1, n):
            if j in drop:
                continue
            iou = _bbox_iou(detections.xyxy[i], detections.xyxy[j])
            if iou < min_iou:
                continue
            if float(confidences[i]) >= float(confidences[j]):
                drop.add(j)
            else:
                drop.add(i)
                break

    if not drop:
        return detections
    keep = [i for i in range(n) if i not in drop]
    return detections[keep]
