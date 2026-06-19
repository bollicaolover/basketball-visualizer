"""Compara resolución de posesión (antigua vs nueva) en un clip de vídeo.

Usa el detector RF-DETR de tfg-junio y un tracker ligero por IoU (sin SAM)
para medir el impacto de los filtros de clase 5 en vídeo real.

Uso:
    python scripts/compare_possession_video.py \
        --input data/test_videos/boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import supervision as sv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import (
    BALL_CLASSES,
    DetectionSettings,
    IN_POSSESSION_CLASS,
    PLAYER_CLASSES,
    PossessionSettings,
)
from pipeline.detection.rfdetr_detector import RFDETRDetector
from pipeline.possession.resolver import PossessionResolver
from pipeline.tracking.ball_tracker import BallTracker
from pipeline.tracking.types import TrackedEntity


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Comparar posesión antigua vs nueva en vídeo")
    p.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/test_videos/boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4",
    )
    p.add_argument("--max-frames", type=int, default=0, help="0 = vídeo completo")
    p.add_argument("--device", default="cuda")
    return p.parse_args()


def _subset(raw: sv.Detections, classes: set[int]) -> sv.Detections:
    if raw is None or len(raw) == 0:
        return sv.Detections.empty()
    mask = np.isin(raw.class_id, list(classes))
    if not mask.any():
        return sv.Detections.empty()
    return raw[mask]


def _filter_confidence(dets: sv.Detections, min_conf: float) -> sv.Detections:
    if dets is None or len(dets) == 0 or dets.confidence is None:
        return sv.Detections.empty() if dets is None or len(dets) == 0 else dets
    mask = dets.confidence >= min_conf
    if not mask.any():
        return sv.Detections.empty()
    return dets[mask]


class SimpleIoUTracker:
    """Asocia cajas de jugador entre frames por IoU (solo para la comparación)."""

    def __init__(self, iou_thresh: float = 0.4) -> None:
        self._iou_thresh = iou_thresh
        self._next_id = 1
        self._tracks: dict[int, np.ndarray] = {}

    def update(self, player_dets: sv.Detections) -> list[TrackedEntity]:
        entities: list[TrackedEntity] = []
        if player_dets is None or len(player_dets) == 0:
            self._tracks.clear()
            return entities

        boxes = player_dets.xyxy.astype(np.float32)
        confs = (
            player_dets.confidence
            if player_dets.confidence is not None
            else np.ones(len(player_dets), dtype=np.float32)
        )
        assigned: dict[int, int] = {}
        used_tracks: set[int] = set()

        for i, box in enumerate(boxes):
            best_tid, best_iou = None, 0.0
            for tid, prev in self._tracks.items():
                if tid in used_tracks:
                    continue
                iou = float(sv.box_iou_batch(box.reshape(1, 4), prev.reshape(1, 4))[0, 0])
                if iou > best_iou:
                    best_iou, best_tid = iou, tid
            if best_tid is not None and best_iou >= self._iou_thresh:
                tid = best_tid
            else:
                tid = self._next_id
                self._next_id += 1
            assigned[i] = tid
            used_tracks.add(tid)
            self._tracks[tid] = box
            entities.append(
                TrackedEntity(
                    track_id=tid,
                    class_id=4,
                    confidence=float(confs[i]),
                    bbox_xyxy=box,
                )
            )

        self._tracks = {tid: self._tracks[tid] for tid in used_tracks}
        return entities


def _old_possession_settings() -> PossessionSettings:
    return PossessionSettings(
        class5_score_threshold=0.40,
        class5_iou=0.30,
        class5_requires_ball=False,
        class5_max_ball_distance_heights=0.60,
        max_ball_distance_heights=0.60,
        suppress_proximity_near_rim=False,
    )


def _new_possession_settings() -> PossessionSettings:
    return PossessionSettings()


def _run_variant(
    *,
    label: str,
    detector: RFDETRDetector,
    possession_settings: PossessionSettings,
    class5_filter_threshold: float,
    cap: cv2.VideoCapture,
    max_frames: int,
) -> dict:
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ball_tracker = BallTracker()
    player_tracker = SimpleIoUTracker()
    resolver = PossessionResolver(possession_settings)

    stats = {
        "label": label,
        "frames": 0,
        "frames_with_possessor": 0,
        "frames_loose_ball": 0,
        "raw_class5_dets": 0,
        "filtered_class5_dets": 0,
        "class5_candidate_frames": 0,
        "proximity_only_frames": 0,
        "unique_possessors": set(),
        "possessor_switches": 0,
    }
    prev_possessor = None

    frame_idx = 0
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        if max_frames and frame_idx >= max_frames:
            break
        frame_idx += 1

        raw = detector.detect(frame_bgr)
        players = _subset(raw, set(PLAYER_CLASSES))
        players = _subset(players, {4})  # solo clase player canónica para tracks
        ball_raw = _subset(raw, set(BALL_CLASSES))
        ball = ball_tracker.update(ball_raw)

        in_possession_raw = _subset(raw, {IN_POSSESSION_CLASS})
        in_possession = _filter_confidence(in_possession_raw, class5_filter_threshold)
        stats["raw_class5_dets"] += len(in_possession_raw)
        stats["filtered_class5_dets"] += len(in_possession)

        entities = player_tracker.update(players)

        # Señal diagnóstica: ¿habría candidato clase 5 sin estado temporal?
        diag = PossessionResolver(possession_settings)
        class5_tid = diag._class5_candidate(ball, in_possession, entities)
        prox_tid = diag._proximity_candidate(ball, entities) if class5_tid is None else None

        possessor = resolver.update(ball, entities, in_possession)
        stats["frames"] += 1
        if possessor is not None:
            stats["frames_with_possessor"] += 1
            stats["unique_possessors"].add(possessor)
        else:
            stats["frames_loose_ball"] += 1
        if class5_tid is not None:
            stats["class5_candidate_frames"] += 1
        elif prox_tid is not None:
            stats["proximity_only_frames"] += 1
        if prev_possessor is not None and possessor is not None and possessor != prev_possessor:
            stats["possessor_switches"] += 1
        prev_possessor = possessor

    stats["unique_possessors"] = len(stats["unique_possessors"])
    return stats


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)

    detector = RFDETRDetector(DetectionSettings(device=args.device))
    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir {args.input}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    max_frames = args.max_frames or total

    print(f"[INFO] Clip: {args.input.name}")
    print(f"[INFO] Frames: {max_frames} / {total}  ({fps:.1f} fps)")

    old = _run_variant(
        label="antigua",
        detector=detector,
        possession_settings=_old_possession_settings(),
        class5_filter_threshold=0.40,
        cap=cap,
        max_frames=max_frames,
    )
    new = _run_variant(
        label="nueva",
        detector=detector,
        possession_settings=_new_possession_settings(),
        class5_filter_threshold=0.55,
        cap=cap,
        max_frames=max_frames,
    )

    def pct(n: int, d: int) -> str:
        return f"{100.0 * n / d:.1f}%" if d else "n/a"

    print("\n=== Comparativa posesión en vídeo ===")
    for key, title in [
        ("frames_with_possessor", "Frames con poseedor"),
        ("frames_loose_ball", "Frames balón suelto"),
        ("raw_class5_dets", "Detecciones clase 5 (brutas)"),
        ("filtered_class5_dets", "Detecciones clase 5 (tras umbral)"),
        ("class5_candidate_frames", "Frames candidato vía clase 5"),
        ("proximity_only_frames", "Frames candidato solo proximidad"),
        ("unique_possessors", "Poseedores distintos"),
        ("possessor_switches", "Cambios de poseedor"),
    ]:
        print(f"  {title:<34}  antigua={old[key]:>5}   nueva={new[key]:>5}")

    frames = old["frames"]
    print("\n  Cobertura:")
    print(
        f"    antigua: {old['frames_with_possessor']}/{frames} "
        f"({pct(old['frames_with_possessor'], frames)}) con poseedor"
    )
    print(
        f"    nueva:   {new['frames_with_possessor']}/{frames} "
        f"({pct(new['frames_with_possessor'], frames)}) con poseedor"
    )
    if old["filtered_class5_dets"] > 0:
        reduction = 100.0 * (1 - new["filtered_class5_dets"] / old["filtered_class5_dets"])
        print(
            f"\n  Detecciones clase 5 tras filtro: "
            f"{old['filtered_class5_dets']} → {new['filtered_class5_dets']} "
            f"({reduction:+.1f}% vs antigua)"
        )
    if old["class5_candidate_frames"] > 0:
        reduction = 100.0 * (1 - new["class5_candidate_frames"] / old["class5_candidate_frames"])
        print(
            f"  Frames con candidato clase 5: "
            f"{old['class5_candidate_frames']} → {new['class5_candidate_frames']} "
            f"({reduction:+.1f}% vs antigua)"
        )


if __name__ == "__main__":
    main()
