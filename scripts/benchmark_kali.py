"""Benchmark: KaliCalib vs YOLO-pose para homografía de cancha.

Ejecutar:
    python scripts/benchmark_kali.py --video data/test_possession_new_q1.mp4

Produce:
    docs/results/kali_benchmark_<video>.csv
    docs/results/kali_benchmark_<video>.png

Las métricas por frame son:
    residual_px   — mediana del error de reproyección en píxeles
    num_inliers   — keypoints usados en el fit
    confidence    — 0..1 (misma fórmula en ambos estimadores)
    H_valid       — si la homografía fue estimada (True/False)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))

from pipeline.config import CourtSettings
from pipeline.court.homography import HomographyEstimator
from pipeline.court.keypoint_detector import CourtKeypointDetector
from pipeline.court.kali_detector import KaliCalibDetector
from pipeline.court.stabilizer import KeypointStabilizer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--max-frames", type=int, default=300)
    p.add_argument("--device", default="cuda")
    p.add_argument("--skip", type=int, default=1, help="Procesar 1 de cada N frames")
    p.add_argument("--kali-checkpoint", default="third_party/KaliCalib/models/model_challenge.pth")
    p.add_argument("--no-plot", action="store_true")
    return p.parse_args()


def run_yolo_pipeline(
    frame: np.ndarray,
    detector: CourtKeypointDetector,
    stabilizer: KeypointStabilizer,
    estimator: HomographyEstimator,
    settings: CourtSettings,
):
    pred = detector.predict(frame)
    stab = stabilizer.update(pred.xy, pred.confidence)
    est = estimator.update(stab.xy, stab.valid_mask)
    return est


def main() -> None:
    args = parse_args()
    video_path = Path(args.video)
    out_dir = Path("docs/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem
    csv_path = out_dir / f"kali_benchmark_{stem}.csv"
    png_path = out_dir / f"kali_benchmark_{stem}.png"

    settings = CourtSettings()

    print("[setup] Cargando YOLO detector …")
    yolo_det = CourtKeypointDetector(settings, device=args.device)
    yolo_stab = KeypointStabilizer(settings)
    yolo_est  = HomographyEstimator(settings)

    print("[setup] Cargando KaliCalib detector …")
    kali_det = KaliCalibDetector(
        checkpoint=args.kali_checkpoint,
        device=args.device,
    )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"ERROR: no se puede abrir {video_path}")
        sys.exit(1)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[video] {video_path.name} — {total_frames} frames @ {fps:.1f} fps")

    rows = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame_idx >= args.max_frames:
            break

        if frame_idx % args.skip != 0:
            frame_idx += 1
            continue

        # --- YOLO ---
        t0 = time.perf_counter()
        yolo_est_result = run_yolo_pipeline(frame, yolo_det, yolo_stab, yolo_est, settings)
        t_yolo = time.perf_counter() - t0

        # --- KaliCalib ---
        t0 = time.perf_counter()
        kali_result = kali_det.update_from_frame(frame)
        t_kali = time.perf_counter() - t0

        rows.append({
            "frame":              frame_idx,
            "yolo_valid":         yolo_est_result.H is not None,
            "yolo_inliers":       yolo_est_result.num_inliers,
            "yolo_residual_px":   yolo_est_result.residual_px if yolo_est_result.H is not None else float("nan"),
            "yolo_confidence":    yolo_est_result.confidence,
            "yolo_cached":        yolo_est_result.used_cached,
            "yolo_ms":            t_yolo * 1000,
            "kali_valid":         kali_result.H is not None,
            "kali_inliers":       kali_result.num_inliers,
            "kali_residual_px":   kali_result.residual_px if kali_result.H is not None else float("nan"),
            "kali_confidence":    kali_result.confidence,
            "kali_ms":            t_kali * 1000,
        })

        if frame_idx % 30 == 0:
            r = rows[-1]
            print(
                f"  frame {frame_idx:4d} | "
                f"YOLO  inl={r['yolo_inliers']:2d} res={r['yolo_residual_px']:5.1f}px ({r['yolo_ms']:.0f}ms) | "
                f"Kali  inl={r['kali_inliers']:2d} res={r['kali_residual_px']:5.1f}px ({r['kali_ms']:.0f}ms)"
            )

        frame_idx += 1

    cap.release()

    # ------------------------------------------------------------------ CSV
    import csv
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[csv] → {csv_path}")

    # ------------------------------------------------------------------ stats
    def stats(key: str, valid_key: str) -> dict:
        vals = [r[key] for r in rows if r[valid_key] and not np.isnan(r[key])]
        if not vals:
            return {}
        return {
            "n_valid": sum(r[valid_key] for r in rows),
            "pct_valid": 100 * sum(r[valid_key] for r in rows) / len(rows),
            "median_res": float(np.median(vals)),
            "p25_res": float(np.percentile(vals, 25)),
            "p75_res": float(np.percentile(vals, 75)),
            "pct_under_5px": 100 * sum(v < 5 for v in vals) / len(vals),
            "pct_under_10px": 100 * sum(v < 10 for v in vals) / len(vals),
        }

    y = stats("yolo_residual_px", "yolo_valid")
    k = stats("kali_residual_px", "kali_valid")

    print("\n=== RESUMEN ===")
    print(f"{'Métrica':<25} {'YOLO-pose':>12} {'KaliCalib':>12}")
    print("-" * 50)
    for label, yk, kk in [
        ("Frames válidos (%)",   "pct_valid",    "pct_valid"),
        ("Residual mediana (px)", "median_res",  "median_res"),
        ("P25 residual (px)",    "p25_res",      "p25_res"),
        ("P75 residual (px)",    "p75_res",      "p75_res"),
        ("% frames <5px",        "pct_under_5px","pct_under_5px"),
        ("% frames <10px",       "pct_under_10px","pct_under_10px"),
    ]:
        yv = f"{y.get(yk, 'N/A'):.1f}" if isinstance(y.get(yk), float) else str(y.get(yk, "N/A"))
        kv = f"{k.get(kk, 'N/A'):.1f}" if isinstance(k.get(kk), float) else str(k.get(kk, "N/A"))
        print(f"  {label:<23} {yv:>12} {kv:>12}")

    # ------------------------------------------------------------------ plot
    if not args.no_plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            frames = [r["frame"] for r in rows]
            fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

            # Residual
            ax = axes[0]
            yr = [r["yolo_residual_px"] if r["yolo_valid"] else float("nan") for r in rows]
            kr = [r["kali_residual_px"] if r["kali_valid"] else float("nan") for r in rows]
            ax.plot(frames, yr, label="YOLO-pose", color="steelblue", linewidth=1.2)
            ax.plot(frames, kr, label="KaliCalib", color="darkorange", linewidth=1.2)
            ax.axhline(5,  color="green", linestyle="--", linewidth=0.8, alpha=0.7, label="5px")
            ax.axhline(10, color="gold",  linestyle="--", linewidth=0.8, alpha=0.7, label="10px")
            ax.set_ylabel("Residual reproyección (px)")
            ax.set_yscale("log")
            ax.legend(fontsize=9)
            ax.set_title(f"Benchmark homografía — {video_path.name}")
            ax.grid(True, alpha=0.3)

            # Inliers
            ax = axes[1]
            yi = [r["yolo_inliers"] for r in rows]
            ki = [r["kali_inliers"] for r in rows]
            ax.plot(frames, yi, label="YOLO-pose (33 kp max)", color="steelblue", linewidth=1.2)
            ax.plot(frames, ki, label="KaliCalib (91 kp max)", color="darkorange", linewidth=1.2)
            ax.set_ylabel("Inliers RANSAC")
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)

            # Confianza
            ax = axes[2]
            yc = [r["yolo_confidence"] for r in rows]
            kc = [r["kali_confidence"] for r in rows]
            ax.plot(frames, yc, label="YOLO-pose", color="steelblue", linewidth=1.2)
            ax.plot(frames, kc, label="KaliCalib", color="darkorange", linewidth=1.2)
            ax.set_ylabel("Confianza")
            ax.set_xlabel("Frame")
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(png_path, dpi=150)
            print(f"[plot] → {png_path}")
        except Exception as e:
            print(f"[plot] Error al generar gráfico: {e}")


if __name__ == "__main__":
    main()
