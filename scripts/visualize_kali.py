"""Genera un vídeo con KaliCalib en acción.

Renderiza sobre cada frame:
  - Puntos de la cuadrícula 7×13 detectados (verde=inlier, rojo=outlier, gris=no detectado)
  - Proyección de las líneas de cancha FIBA usando la H estimada
  - Panel inferior: métricas del frame (inliers, residual, confidence)

Ejecutar:
    python scripts/visualize_kali.py --video data/test_possession_new_q1.mp4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))

from pipeline.court.kali_detector import KaliCalibDetector, _WORLD_PTS_FT, _INFER_W, _INFER_H


# ---------------------------------------------------------------------------
# Geometría FIBA en pies para dibujar líneas sobre el frame
# ---------------------------------------------------------------------------
CM2FT = 1.0 / 30.48
FL = 2800 * CM2FT   # longitud campo (ft)
FW = 1500 * CM2FT   # anchura campo (ft)

# Líneas principales [pt_a_ft, pt_b_ft]
_LINES = [
    # Perímetro
    ([0, 0], [FL, 0]),
    ([FL, 0], [FL, FW]),
    ([FL, FW], [0, FW]),
    ([0, FW], [0, 0]),
    # Línea del medio
    ([FL/2, 0], [FL/2, FW]),
    # Zonas (pintura izq)
    ([0, FW/2 - 488*CM2FT/2], [579*CM2FT, FW/2 - 488*CM2FT/2]),
    ([0, FW/2 + 488*CM2FT/2], [579*CM2FT, FW/2 + 488*CM2FT/2]),
    ([579*CM2FT, FW/2 - 488*CM2FT/2], [579*CM2FT, FW/2 + 488*CM2FT/2]),
    # Zonas (pintura dcha)
    ([FL, FW/2 - 488*CM2FT/2], [FL - 579*CM2FT, FW/2 - 488*CM2FT/2]),
    ([FL, FW/2 + 488*CM2FT/2], [FL - 579*CM2FT, FW/2 + 488*CM2FT/2]),
    ([FL - 579*CM2FT, FW/2 - 488*CM2FT/2], [FL - 579*CM2FT, FW/2 + 488*CM2FT/2]),
]

# Círculos: (centro_ft, radio_ft)
_CIRCLES = [
    ([FL/2, FW/2], 183*CM2FT),         # círculo central
    ([579*CM2FT, FW/2], 180*CM2FT),     # tiro libre izq
    ([FL - 579*CM2FT, FW/2], 180*CM2FT),# tiro libre dcha
]


def project_ft(pts_ft: np.ndarray, H_i2w: np.ndarray) -> np.ndarray:
    """Proyecta puntos mundo(ft) → imagen usando H_w2i = inv(H_i2w)."""
    H_w2i = np.linalg.inv(H_i2w)
    ones = np.ones((len(pts_ft), 1), dtype=np.float64)
    ph = np.hstack([pts_ft, ones]) @ H_w2i.T
    ph = ph[:, :2] / ph[:, 2:3]
    return ph.astype(np.float32)


def draw_court_lines(frame: np.ndarray, H_i2w: np.ndarray, color=(0, 255, 100), thickness=2):
    """Dibuja las líneas de la cancha FIBA proyectadas sobre el frame."""
    h, w = frame.shape[:2]

    def inside(p):
        return 0 <= p[0] < w and 0 <= p[1] < h

    for a_ft, b_ft in _LINES:
        pts = project_ft(np.array([a_ft, b_ft], dtype=np.float64), H_i2w)
        pa, pb = tuple(pts[0].astype(int)), tuple(pts[1].astype(int))
        if inside(pa) or inside(pb):
            cv2.line(frame, pa, pb, color, thickness, cv2.LINE_AA)

    for center_ft, radius_ft in _CIRCLES:
        # Discretizamos el círculo en 60 segmentos
        c = np.array(center_ft, dtype=np.float64)
        angles = np.linspace(0, 2 * np.pi, 61)
        ring = np.stack([
            c[0] + radius_ft * np.cos(angles),
            c[1] + radius_ft * np.sin(angles),
        ], axis=1)
        proj = project_ft(ring, H_i2w).astype(int)
        for i in range(len(proj) - 1):
            pa, pb = tuple(proj[i]), tuple(proj[i + 1])
            if inside(pa) or inside(pb):
                cv2.line(frame, pa, pb, color, thickness, cv2.LINE_AA)


def draw_keypoints(
    frame: np.ndarray,
    kp_img: np.ndarray,       # (91, 2) coords imagen a resolución original
    H_i2w: np.ndarray,
    kp_conf: np.ndarray,
):
    """Dibuja cada keypoint con color según es inlier/outlier/no detectado."""
    if H_i2w is None:
        return

    H_w2i = np.linalg.inv(H_i2w)
    world_3 = np.hstack([_WORLD_PTS_FT, np.ones((91, 1), dtype=np.float64)])
    reproj = (H_w2i @ world_3.T).T
    reproj = reproj[:, :2] / reproj[:, 2:3]

    for i in range(91):
        detected = kp_img[i, 0] != 0 or kp_img[i, 1] != 0
        if not detected:
            continue

        obs = kp_img[i].astype(int)
        rep = reproj[i].astype(int)

        err = float(np.linalg.norm(kp_img[i] - reproj[i]))
        is_inlier = err < 15.0  # px threshold visual

        col_obs = (0, 220, 0) if is_inlier else (0, 0, 220)   # verde / rojo
        cv2.circle(frame, tuple(obs), 5, col_obs, -1, cv2.LINE_AA)
        cv2.circle(frame, tuple(rep), 4, (255, 255, 0), 1, cv2.LINE_AA)  # reproyectado (amarillo)
        if not is_inlier:
            cv2.line(frame, tuple(obs), tuple(rep), (0, 0, 200), 1, cv2.LINE_AA)


def add_hud(
    frame: np.ndarray,
    frame_idx: int,
    est,
    ms: float,
):
    """Texto con métricas en la esquina superior izquierda."""
    h_valid = est.H is not None
    lines = [
        f"KaliCalib  frame={frame_idx}",
        f"H: {'OK' if h_valid else 'FAIL'}  inliers={est.num_inliers}",
        f"residual={est.residual_px:.1f}px  conf={est.confidence:.2f}",
        f"latencia={ms:.0f}ms",
    ]
    y0, dy = 28, 26
    for i, txt in enumerate(lines):
        cv2.putText(frame, txt, (12, y0 + i * dy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, txt, (12, y0 + i * dy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--max-frames", type=int, default=300)
    p.add_argument("--device", default="cuda")
    p.add_argument("--checkpoint", default="third_party/KaliCalib/models/model_challenge.pth")
    return p.parse_args()


def main():
    args = parse_args()
    video_path = Path(args.video)
    out_path = Path(args.out) if args.out else Path("docs/results") / f"kali_vis_{video_path.stem}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    fps  = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps, (w, h),
    )

    print(f"[setup] {video_path.name}  {w}×{h} @ {fps:.1f}fps")
    det = KaliCalibDetector(checkpoint=args.checkpoint, device=args.device)

    import time
    frame_idx = 0
    while frame_idx < args.max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        t0 = time.perf_counter()

        # --- Inferencia interna paso a paso para obtener kp_img también ---
        orig_h, orig_w = frame.shape[:2]
        heatmaps = det._run_model(frame)
        kp_img, kp_conf = det._extract_keypoints(heatmaps)

        # Escalar a resolución original
        kp_img_orig = kp_img.copy()
        kp_img_orig[:, 0] *= orig_w / _INFER_W
        kp_img_orig[:, 1] *= orig_h / _INFER_H

        est = det._estimate_homography(kp_img_orig, kp_conf, orig_w, orig_h)
        ms = (time.perf_counter() - t0) * 1000

        vis = frame.copy()

        if est.H is not None:
            draw_court_lines(vis, est.H, color=(0, 200, 80), thickness=2)
            draw_keypoints(vis, kp_img_orig, est.H, kp_conf)

        add_hud(vis, frame_idx, est, ms)
        writer.write(vis)

        if frame_idx % 30 == 0:
            print(f"  frame {frame_idx:4d} | inl={est.num_inliers:2d} "
                  f"res={est.residual_px:5.1f}px  conf={est.confidence:.2f}  {ms:.0f}ms")
        frame_idx += 1

    cap.release()
    writer.release()
    print(f"\n[done] → {out_path}")


if __name__ == "__main__":
    main()
