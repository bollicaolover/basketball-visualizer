"""Compara el seguimiento del balón EMA (original) vs Kalman (método Pirotta).

Ejecuta el detector RF-DETR una sola vez por frame y alimenta las MISMAS
detecciones de balón a ambos seguidores, de modo que la única variable es el
algoritmo de tracking. Mide cobertura, relleno por oclusión (holdover) y
suavidad de la trayectoria, y opcionalmente vuelca un vídeo con ambas cajas
superpuestas (EMA en cian, Kalman en magenta) para inspección visual.

Uso:
    python scripts/compare_ball_tracker.py \
        --input data/test_videos/boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4 \
        --save-video data/ball_compare.mp4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import supervision as sv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import BALL_CLASSES, BallTrackingSettings, DetectionSettings
from pipeline.detection.rfdetr_detector import RFDETRDetector
from pipeline.tracking.ball_tracker import BallTracker
from pipeline.tracking.ball_tracker_kalman import KalmanBallTracker


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Comparar tracking del balón EMA vs Kalman")
    p.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/test_videos/boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4",
    )
    p.add_argument("--max-frames", type=int, default=0, help="0 = vídeo completo")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--save-video",
        type=Path,
        default=None,
        help="ruta opcional del vídeo comparativo (ambas cajas superpuestas)",
    )
    return p.parse_args()


def _ball_subset(raw: sv.Detections) -> sv.Detections:
    if raw is None or len(raw) == 0:
        return sv.Detections.empty()
    mask = np.isin(raw.class_id, list(BALL_CLASSES))
    return raw[mask] if mask.any() else sv.Detections.empty()


def _center(det: sv.Detections) -> np.ndarray | None:
    if det is None or len(det) == 0:
        return None
    box = det.xyxy[0]
    return np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])


class TrajectoryStats:
    """Acumula métricas de una trayectoria de balón frame a frame."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.frames = 0
        self.output_frames = 0          # frames con balón emitido por el tracker
        self.holdover_frames = 0        # emitido sin detección cruda (oclusión)
        self._centers: list[np.ndarray | None] = []

    def add(self, out: sv.Detections, had_raw: bool) -> None:
        self.frames += 1
        c = _center(out)
        if c is not None:
            self.output_frames += 1
            if not had_raw:
                self.holdover_frames += 1
        self._centers.append(c)

    def _steps(self) -> np.ndarray:
        """Desplazamientos entre centros consecutivos presentes en ambos frames."""
        steps = []
        for a, b in zip(self._centers, self._centers[1:]):
            if a is not None and b is not None:
                steps.append(float(np.linalg.norm(b - a)))
        return np.asarray(steps, dtype=np.float64)

    def summary(self, raw_ball_frames: int) -> dict:
        steps = self._steps()
        # Jerk ≈ variación del paso (segunda diferencia de la posición): a menor
        # valor, trayectoria más suave.
        jerk = np.abs(np.diff(steps)) if steps.size > 1 else np.array([0.0])
        return {
            "label": self.label,
            "frames": self.frames,
            "raw_ball_frames": raw_ball_frames,
            "output_frames": self.output_frames,
            "coverage_%": round(100.0 * self.output_frames / max(1, self.frames), 1),
            "holdover_frames": self.holdover_frames,
            "mean_step_px": round(float(steps.mean()) if steps.size else 0.0, 2),
            "max_step_px": round(float(steps.max()) if steps.size else 0.0, 2),
            "mean_jerk_px": round(float(jerk.mean()), 2),
        }


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
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    max_frames = args.max_frames or total

    print(f"[INFO] Clip: {args.input.name}")
    print(f"[INFO] Frames: {max_frames} / {total}  ({fps:.1f} fps)")

    ema = BallTracker(BallTrackingSettings(method="ema"))
    kalman = KalmanBallTracker(BallTrackingSettings(method="kalman"))
    ema_stats = TrajectoryStats("EMA (original)")
    kal_stats = TrajectoryStats("Kalman (Pirotta)")
    raw_ball_frames = 0

    writer = None
    if args.save_video is not None:
        args.save_video.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(args.save_video), fourcc, fps, (w, h))

    EMA_COLOR = (255, 255, 0)      # cian (BGR)
    KAL_COLOR = (255, 0, 255)      # magenta (BGR)

    frame_idx = 0
    while True:
        ok, frame_bgr = cap.read()
        if not ok or (max_frames and frame_idx >= max_frames):
            break
        frame_idx += 1

        raw = detector.detect(frame_bgr)
        ball_raw = _ball_subset(raw)
        had_raw = len(ball_raw) > 0
        if had_raw:
            raw_ball_frames += 1

        out_ema = ema.update(ball_raw)
        out_kal = kalman.update(ball_raw)
        ema_stats.add(out_ema, had_raw)
        kal_stats.add(out_kal, had_raw)

        if writer is not None:
            vis = frame_bgr.copy()
            for out, color, tag in ((out_ema, EMA_COLOR, "EMA"), (out_kal, KAL_COLOR, "KAL")):
                c = _center(out)
                if c is None:
                    continue
                x, y = int(c[0]), int(c[1])
                cv2.circle(vis, (x, y), 9, color, 2)
                cv2.putText(vis, tag, (x + 11, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            cv2.putText(vis, "cian=EMA  magenta=Kalman", (12, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            writer.write(vis)

    cap.release()
    if writer is not None:
        writer.release()

    rows = [ema_stats.summary(raw_ball_frames), kal_stats.summary(raw_ball_frames)]
    print()
    print(f"{'métrica':<18}{'EMA':>18}{'Kalman':>18}")
    keys = [
        ("output_frames", "frames con balón"),
        ("coverage_%", "cobertura %"),
        ("holdover_frames", "relleno oclusión"),
        ("mean_step_px", "paso medio (px)"),
        ("max_step_px", "paso máx (px)"),
        ("mean_jerk_px", "jerk medio (px)"),
    ]
    print(f"{'frames totales':<18}{rows[0]['frames']:>18}{rows[1]['frames']:>18}")
    print(f"{'det. crudas balón':<18}{raw_ball_frames:>18}{raw_ball_frames:>18}")
    for key, name in keys:
        print(f"{name:<18}{rows[0][key]:>18}{rows[1][key]:>18}")

    if args.save_video is not None:
        print(f"\n[INFO] Vídeo comparativo: {args.save_video}")
    print(
        "\nLectura: mayor cobertura y relleno-oclusión = más robusto a oclusiones; "
        "menor jerk medio = trayectoria más suave."
    )


if __name__ == "__main__":
    main()
