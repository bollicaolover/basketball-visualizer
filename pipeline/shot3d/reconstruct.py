"""Reconstrucción 3D de un tiro (Pirotta cap. 5).

Invocable desde el pipeline principal, el backend web o el CLI
``scripts/reconstruct_shot_3d.py``. Reutiliza ``{out}_metadata.json`` cuando
existe. Ver ``docs/resultados-trayectoria-3d.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import supervision as sv

from pipeline.config import BALL_CLASSES, BallTrackingSettings, Settings
from pipeline.court.ball_3d import (
    FT_TO_M,
    RIM_HEIGHT_FT,
    solve_ballistic_trajectory,
)
from pipeline.config import PLAYER_CLASSES, PoseSettings, ReleaseSettings, RIM_CLASS
from pipeline.court.camera_model import PnPCameraEstimator
from pipeline.court.keypoint_detector import CourtKeypointDetector
from pipeline.court.stabilizer import KeypointStabilizer
from pipeline.detection.rfdetr_detector import RFDETRDetector
from pipeline.io.pipeline_metadata import (
    ball_center_from_frame,
    load_pipeline_metadata,
    nearest_player_bbox,
    rim_observation_from_frame,
)
from pipeline.pose.pose_estimator import PoseEstimator
from pipeline.scoring.release_detector import ReleaseDetector
from pipeline.tracking.ball_tracker_kalman import KalmanBallTracker


class Shot3DError(Exception):
    """Fallo recuperable (sin arco balístico, sin muestras, etc.)."""


@dataclass
class Shot3DResult:
    frames: list[int]
    reproj_rmse_px: float
    apex_height_m: float
    launch_angle_deg: float
    launch_speed_mps: float
    plausible: bool
    video_path: Path | None = None
    json_path: Path | None = None


def shot3d_output_paths(near_output_video: str | Path) -> tuple[Path, Path]:
    """Rutas estándar junto al overlay del job/pipeline."""
    parent = Path(near_output_video).resolve().parent
    return parent / "shot3d.mp4", parent / "shot3d.json"


def _nearest_player_box(raw: sv.Detections, ball_xy: np.ndarray) -> np.ndarray | None:
    """Caja del jugador más cercana al balón (poseedor aproximado, sin resolver)."""
    if raw is None or len(raw) == 0:
        return None
    mask = np.isin(raw.class_id, list(PLAYER_CLASSES))
    if not mask.any():
        return None
    boxes = raw.xyxy[mask]
    cx = (boxes[:, 0] + boxes[:, 2]) / 2.0
    cy = (boxes[:, 1] + boxes[:, 3]) / 2.0
    d = np.hypot(cx - ball_xy[0], cy - ball_xy[1])
    return boxes[int(np.argmin(d))]


def _ball_center(raw: sv.Detections, tracker: KalmanBallTracker) -> np.ndarray | None:
    mask = np.isin(raw.class_id, list(BALL_CLASSES)) if len(raw) else np.array([], dtype=bool)
    ball_raw = raw[mask] if mask.any() else sv.Detections.empty()
    out = tracker.update(ball_raw)
    if len(out) == 0:
        return None
    b = out.xyxy[0]
    return np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0], dtype=np.float64)


def _rim_observation(
    raw: sv.Detections, min_conf: float = 0.30,
) -> tuple[np.ndarray, float] | None:
    """Centro del aro (clase ``rim``) y radio ≈ mitad de la altura del bbox (px)."""
    if raw is None or len(raw) == 0:
        return None
    mask = raw.class_id == RIM_CLASS
    if not mask.any():
        return None
    conf = raw.confidence if raw.confidence is not None else np.ones(len(raw))
    best_i, best_c = None, -1.0
    for i in np.where(mask)[0]:
        c = float(conf[i])
        if c >= min_conf and c > best_c:
            best_i, best_c = int(i), c
    if best_i is None:
        return None
    box = raw.xyxy[best_i]
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    radius = max(float(box[3] - box[1]) / 2.0, 8.0)
    return np.array([cx, cy], dtype=np.float64), radius


def _nearest_P(P_by_frame: dict[int, np.ndarray], frame: int) -> np.ndarray | None:
    if frame in P_by_frame:
        return P_by_frame[frame]
    if not P_by_frame:
        return None
    return P_by_frame[min(P_by_frame, key=lambda k: abs(k - frame))]


def _rim_target(
    rim_by_frame: dict[int, tuple[np.ndarray, float]],
    seg_frames: list[int],
) -> tuple[np.ndarray, float] | None:
    """Posición estable del aro (mediana) durante el tramo del tiro."""
    obs = [rim_by_frame[f] for f in seg_frames if f in rim_by_frame]
    if len(obs) < 2:
        obs = list(rim_by_frame.values())
    if not obs:
        return None
    centers = np.array([c for c, _ in obs])
    radii = [r for _, r in obs]
    return np.median(centers, axis=0), float(np.median(radii))


def _arc_end_at_rim(
    traj,
    after_t: float,
    rim_xy: np.ndarray,
    rim_r_px: float,
    P_by_frame: dict[int, np.ndarray],
    lo: int,
    fps: float,
    oriented,
    hit_factor: float = 1.25,
) -> float | None:
    """Primer instante (bajada) en que la parábola 3D reproyectada entra en el aro."""
    t_hi, _ = traj.extrapolation_end(after_t=after_t)
    t_lo = max(after_t, traj.apex_time_s) + 1e-6
    if t_hi <= t_lo:
        return None
    hit_r = hit_factor * rim_r_px
    best_t: float | None = None
    best_d = float("inf")
    for t in np.linspace(t_lo, t_hi, 400):
        fr = lo + int(round(t * fps))
        P = _nearest_P(P_by_frame, fr)
        if P is None:
            continue
        pt = _project_pt(oriented(P), traj.position(t))
        if pt is None:
            continue
        d = float(np.hypot(pt[0] - rim_xy[0], pt[1] - rim_xy[1]))
        if d <= hit_r:
            return float(t)
        if d < best_d:
            best_d, best_t = d, float(t)
    if best_t is not None and best_d <= 3.0 * rim_r_px:
        return best_t
    return None


def _resolve_arc_end(
    traj,
    after_t: float,
    rim_by_frame: dict[int, tuple[np.ndarray, float]],
    P_by_frame: dict[int, np.ndarray],
    seg_frames: list[int],
    lo: int,
    fps: float,
    oriented,
) -> tuple[float, str]:
    """Fin del arco: cruce con el aro detectado (RF-DETR) o fallback analítico."""
    analytical_t, reason = traj.extrapolation_end(after_t=after_t)
    target = _rim_target(rim_by_frame, seg_frames)
    if target is not None:
        rim_xy, rim_r = target
        t_hit = _arc_end_at_rim(
            traj, after_t, rim_xy, rim_r, P_by_frame, lo, fps, oriented,
        )
        if t_hit is not None:
            return t_hit, "rim"
    return analytical_t, reason


def _contiguous_runs(frames: list[int]) -> list[list[int]]:
    """Parte una lista ordenada de frames en tramos de índices consecutivos."""
    runs: list[list[int]] = []
    for f in frames:
        if runs and f == runs[-1][-1] + 1:
            runs[-1].append(f)
        else:
            runs.append([f])
    return runs


def _best_arc_window(
    samples: dict[int, tuple[np.ndarray, np.ndarray]],
    fps: float,
    min_len: int,
    half_window_s: float = 0.5,
    max_resid_px: float = 22.0,
    min_amplitude_px: float = 60.0,
) -> tuple[int, int] | None:
    """Localiza el arco balístico y lo recorta a ±``half_window_s`` del ápice.

    Durante un tiro la Y-imagen del balón sube y baja → parábola **convexa**
    (coef. cuadrático > 0 en coordenadas imagen). Se localiza el ápice (mínimo de
    Y-imagen) dentro del tramo contiguo más largo y se toma una ventana centrada
    en él (≈ duración de un tiro real), donde la pose suele ser mejor y el modelo
    balístico se cumple. Devuelve (lo, hi) o ``None`` si no hay arco claro.
    """
    half = max(min_len // 2, int(round(half_window_s * fps)))
    best: tuple[float, int, int] | None = None
    for run in _contiguous_runs(sorted(samples)):
        if len(run) < min_len:
            continue
        ys = np.array([samples[f][0][1] for f in run])
        apex_i = int(np.argmin(ys))                     # ápice = Y-imagen mínima
        i = max(0, apex_i - half)
        j = min(len(run) - 1, apex_i + half)
        if j - i + 1 < min_len:
            continue
        t = np.arange(j - i + 1, dtype=np.float64)
        y = ys[i : j + 1]
        coeffs, res, *_ = np.polyfit(t, y, 2, full=True)
        t_vertex = -coeffs[1] / (2 * coeffs[0]) if coeffs[0] != 0 else -1.0
        rms = float(np.sqrt(res[0] / len(t))) if res.size else 0.0
        amp = float(y.max() - y.min())
        # Convexa, ápice dentro de la ventana, buen ajuste y amplitud suficiente.
        if (
            coeffs[0] > 0
            and 0.0 <= t_vertex <= (len(t) - 1)
            and rms <= max_resid_px
            and amp >= min_amplitude_px
            and (best is None or amp > best[0])
        ):
            best = (amp, run[i], run[j])
    return None if best is None else (best[1], best[2])


def _project_pt(P: np.ndarray, xyz: np.ndarray) -> tuple[int, int] | None:
    h = P @ np.array([xyz[0], xyz[1], xyz[2], 1.0])
    if abs(h[2]) < 1e-9:
        return None
    return int(round(h[0] / h[2])), int(round(h[1] / h[2]))


def _arc_geometry(
    traj,
    seg_frames: list[int],
    rim_by_frame: dict[int, tuple[np.ndarray, float]],
    P_by_frame: dict[int, np.ndarray],
    fps: float,
    oriented,
) -> dict[str, Any]:
    """Parámetros compartidos del arco extrapolado (vídeo y capa web)."""
    lo, hi = seg_frames[0], seg_frames[-1]
    t_obs_end = float(traj.times[-1])
    t_end, end_reason = _resolve_arc_end(
        traj, t_obs_end, rim_by_frame, P_by_frame, seg_frames, lo, fps, oriented,
    )
    t_end = max(t_end, t_obs_end)
    n_samples = max(90, int(round((t_end - traj.times[0]) * fps * 2)))
    t_dense = np.linspace(traj.times[0], t_end, n_samples)
    arc_xyz = np.array([traj.position(t) for t in t_dense])
    end_xyz = traj.position(t_end)
    overlay_hi = hi + max(int(0.4 * fps), int(round((t_end - t_obs_end) * fps)) + 2)
    return {
        "lo": lo,
        "hi": hi,
        "overlay_hi": overlay_hi,
        "t_end": t_end,
        "end_reason": end_reason,
        "arc_xyz": arc_xyz,
        "end_xyz": end_xyz,
        "rim_target": _rim_target(rim_by_frame, seg_frames),
    }


def _project_arc_poly(
    Po: np.ndarray,
    arc_xyz: np.ndarray,
    end_reason: str,
    rim_obs: tuple[np.ndarray, float] | None,
) -> list[list[int]]:
    poly = [p for p in (_project_pt(Po, w) for w in arc_xyz) if p is not None]
    if end_reason == "rim" and rim_obs is not None and len(poly) >= 2:
        rim_pt = (int(round(rim_obs[0][0])), int(round(rim_obs[0][1])))
        if np.hypot(poly[-1][0] - rim_pt[0], poly[-1][1] - rim_pt[1]) > 4:
            poly.append(rim_pt)
    return [[int(x), int(y)] for x, y in poly]


def _frame_overlay(
    *,
    f: int,
    Po: np.ndarray,
    geom: dict[str, Any],
    rim_obs: tuple[np.ndarray, float] | None,
    ball_meas: np.ndarray | None,
    traj,
    fps: float,
) -> dict[str, Any]:
    """Datos 2D de una frame para la capa interactiva del frontend."""
    lo, hi = geom["lo"], geom["hi"]
    entry: dict[str, Any] = {}
    poly = _project_arc_poly(Po, geom["arc_xyz"], geom["end_reason"], rim_obs)
    if len(poly) >= 2:
        entry["arc"] = poly

    end_reason = geom["end_reason"]
    end_pt = _project_pt(Po, geom["end_xyz"])
    if end_pt is not None and end_reason == "rim":
        rim_tgt = geom["rim_target"]
        if rim_tgt is not None:
            end_pt = (int(round(rim_tgt[0][0])), int(round(rim_tgt[0][1])))
    if end_pt is not None and end_reason != "observed":
        entry["end"] = [end_pt[0], end_pt[1]]
        entry["end_reason"] = end_reason

    if rim_obs is not None:
        entry["rim"] = [
            float(rim_obs[0][0]),
            float(rim_obs[0][1]),
            float(rim_obs[1]),
        ]

    if lo <= f <= hi:
        tf = (f - lo) / fps
        pos = traj.position(tf)
        pb = _project_pt(Po, pos)
        if pb is not None:
            entry["ball_proj"] = [pb[0], pb[1]]
            entry["ball_z_m"] = round(float(pos[2] * FT_TO_M), 2)
        if ball_meas is not None:
            entry["ball_meas"] = [float(ball_meas[0]), float(ball_meas[1])]

    return entry


def _build_overlay_by_frame(
    traj,
    seg_frames: list[int],
    P_by_frame: dict[int, np.ndarray],
    ball_by_frame: dict[int, np.ndarray],
    rim_by_frame: dict[int, tuple[np.ndarray, float]],
    fps: float,
    oriented,
) -> dict[str, Any]:
    """Serializa la parábola reproyectada por frame (capa canvas del frontend)."""
    geom = _arc_geometry(traj, seg_frames, rim_by_frame, P_by_frame, fps, oriented)
    lo, overlay_hi = geom["lo"], geom["overlay_hi"]
    frames: dict[str, Any] = {}
    for f in range(lo, overlay_hi + 1):
        P = P_by_frame.get(f)
        if P is None:
            continue
        entry = _frame_overlay(
            f=f,
            Po=oriented(P),
            geom=geom,
            rim_obs=rim_by_frame.get(f),
            ball_meas=ball_by_frame.get(f),
            traj=traj,
            fps=fps,
        )
        if entry:
            frames[str(f)] = entry
    return {
        "lo": lo,
        "hi": geom["hi"],
        "overlay_hi": overlay_hi,
        "end_reason": geom["end_reason"],
        "hud": {
            "apex_m": round(traj.apex_height_ft * FT_TO_M, 2),
            "rmse_px": round(traj.reproj_rmse_px, 1),
        },
        "frames": frames,
    }


def _render_overlay(
    input_path: Path,
    out_path: Path,
    traj,
    seg_frames: list[int],
    P_by_frame: dict[int, np.ndarray],
    ball_by_frame: dict[int, np.ndarray],
    rim_by_frame: dict[int, tuple[np.ndarray, float]],
    fps: float,
    size: tuple[int, int],
) -> None:
    """Segunda pasada: reproyecta la parábola 3D (anclada a la cancha) sobre cada
    frame usando su propia P, con la altura del balón anotada. Reutiliza las P ya
    calculadas, así que no vuelve a invocar modelos.

    La curva se extrapola más allá de las detecciones hasta que la reproyección
    3D entra en el aro detectado (clase ``rim``, misma señal que el pipeline).
    Si no hay aro visible, cae al cruce analítico con la altura del aro o el suelo.
    """
    def oriented(P: np.ndarray) -> np.ndarray:
        if not traj.oriented:
            return P
        Pf = P.copy()
        Pf[:, 2] *= -1.0   # mismo volteo que usó el solver (Z→arriba)
        return Pf

    geom = _arc_geometry(traj, seg_frames, rim_by_frame, P_by_frame, fps, oriented)
    lo, hi = geom["lo"], geom["hi"]
    end_reason = geom["end_reason"]
    end_xyz = geom["end_xyz"]
    overlay_hi = geom["overlay_hi"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(input_path))
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    ARC, BALL, MEAS = (0, 215, 255), (0, 140, 255), (80, 220, 80)  # BGR
    RIM_REF = (0, 197, 253)   # dorado, como en el pipeline
    END_RIM, END_FLOOR = (0, 165, 255), (180, 180, 180)  # naranja / gris
    end_color = END_RIM if end_reason == "rim" else END_FLOOR
    end_label = "aro" if end_reason == "rim" else "suelo"
    f = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        P = P_by_frame.get(f)
        if P is not None and lo <= f <= overlay_hi:
            Po = oriented(P)
            rim_obs = rim_by_frame.get(f)
            ov = _frame_overlay(
                f=f,
                Po=Po,
                geom=geom,
                rim_obs=rim_obs,
                ball_meas=ball_by_frame.get(f),
                traj=traj,
                fps=fps,
            )
            if rim_obs is not None:
                rcx, rcy = rim_obs[0]
                rr = int(round(rim_obs[1]))
                cv2.circle(frame, (int(rcx), int(rcy)), rr, RIM_REF, 2, cv2.LINE_AA)
            poly = ov.get("arc")
            if poly and len(poly) >= 2:
                cv2.polylines(frame, [np.array(poly, np.int32)], False, ARC, 3, cv2.LINE_AA)
            end_pt = ov.get("end")
            if end_pt is not None and end_reason != "observed":
                cv2.circle(frame, tuple(end_pt), 10, end_color, 2, cv2.LINE_AA)
                cv2.putText(
                    frame, end_label, (end_pt[0] + 12, end_pt[1] + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, end_color, 2, cv2.LINE_AA,
                )
            ball_proj = ov.get("ball_proj")
            if ball_proj is not None:
                pb = tuple(ball_proj)
                z_m = ov.get("ball_z_m", 0)
                cv2.circle(frame, pb, 8, BALL, -1, cv2.LINE_AA)
                cv2.putText(
                    frame, f"Z={z_m:.1f} m", (pb[0] + 12, pb[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, BALL, 2, cv2.LINE_AA,
                )
            ball_meas = ov.get("ball_meas")
            if ball_meas is not None:
                cv2.circle(
                    frame, (int(ball_meas[0]), int(ball_meas[1])), 5, MEAS, 2, cv2.LINE_AA,
                )
            cv2.putText(
                frame,
                f"apice {traj.apex_height_ft * FT_TO_M:.2f} m | RMSE {traj.reproj_rmse_px:.1f}px",
                (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, ARC, 2, cv2.LINE_AA,
            )
        writer.write(frame)
        f += 1
    cap.release()
    writer.release()
    if end_reason != "observed":
        print(
            f"\n[INFO] Vídeo con trayectoria 3D → {out_path} "
            f"(extrapolada hasta {end_label}, t={geom['t_end']:.2f}s)",
            flush=True,
        )
    else:
        print(f"\n[INFO] Vídeo con trayectoria 3D → {out_path}", flush=True)


def _window_is_physical(
    samples: dict[int, tuple[np.ndarray, np.ndarray]],
    lo: int,
    hi: int,
    fps: float,
    min_release_ft: float = 4.0,
    min_floor_ft: float = -1.0,
) -> bool:
    """¿El ajuste 3D del tramo [lo, hi] es físicamente plausible? (suelta por
    encima de ~1.2 m y sin puntos bajo el suelo). Mismos umbrales que el
    guardarraíl de la extensión heurística."""
    fr = [f for f in sorted(samples) if lo <= f <= hi]
    if len(fr) < 4:
        return False
    uv = np.array([samples[f][0] for f in fr])
    Ps = [samples[f][1] for f in fr]
    t = np.array([(f - fr[0]) / fps for f in fr])
    tr = solve_ballistic_trajectory(Ps, uv, t)
    return bool(
        tr.points_3d[0, 2] >= min_release_ft and tr.points_3d[:, 2].min() >= min_floor_ft
    )


def _extend_window_to_release(
    samples: dict[int, tuple[np.ndarray, np.ndarray]],
    lo: int,
    hi: int,
    fps: float,
    rmse_cap_px: float = 20.0,
    max_gap: int = 4,
) -> tuple[int, int]:
    """Extiende la ventana hacia atrás hasta el punto de suelta.

    Añade frames anteriores uno a uno (saltando huecos breves de detección, p.ej.
    el balón perdido un frame) reajustando la parábola balística, mientras el RMSE
    de reproyección global se mantenga por debajo de ``rmse_cap_px``. La suelta es
    el límite: antes de soltar el balón va en la mano del tirador y no describe el
    vuelo libre, lo que dispara el error. El RMSE crece de forma gradual al incluir
    la fase de subida (más ruidosa), de ahí un umbral más laxo que el del ajuste
    del ápice. Tope: 1.2 s hacia atrás.
    """
    # Guardarraíles físicos (en pies, coords Z-arriba del solver): una suelta real
    # está por encima de ~1.2 m y ningún punto del vuelo cae bajo el suelo. Evita
    # sobre-extender hacia frames que ya no son vuelo libre (balón en la mano,
    # otra jugada), que producirían alturas negativas aunque el RMSE aún sea bajo.
    MIN_RELEASE_FT = 4.0
    MIN_FLOOR_FT = -1.0
    avail = sorted(samples)
    cur = [f for f in avail if lo <= f <= hi]
    max_back = int(round(1.2 * fps))
    back = 0
    while back < max_back:
        earlier = [f for f in avail if f < cur[0]]
        if not earlier:
            break
        prev = max(earlier)
        if cur[0] - prev > max_gap:   # hueco demasiado grande: corte de jugada
            break
        trial = [prev] + cur
        uv = np.array([samples[f][0] for f in trial])
        Ps = [samples[f][1] for f in trial]
        t = np.array([(f - trial[0]) / fps for f in trial])
        tr = solve_ballistic_trajectory(Ps, uv, t)
        if (
            tr.reproj_rmse_px <= rmse_cap_px
            and tr.points_3d[0, 2] >= MIN_RELEASE_FT
            and tr.points_3d[:, 2].min() >= MIN_FLOOR_FT
        ):
            cur = trial
            back += 1
        else:
            break
    return cur[0], cur[-1]


def run_shot3d(
    *,
    input_video: Path,
    metadata_path: Path | None = None,
    video_out: Path | None = None,
    json_out: Path | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
    min_segment: int = 8,
    pose_release: bool = False,
    require_parabola: bool = False,
    extend_to_release: bool = True,
    device: str = "cuda",
) -> Shot3DResult:
    """Reconstruye la trayectoria 3D y opcionalmente escribe vídeo + JSON."""
    if not input_video.is_file():
        raise FileNotFoundError(input_video)

    pipeline_meta = None
    if metadata_path is not None:
        if not metadata_path.is_file():
            raise FileNotFoundError(f"Metadata no encontrada: {metadata_path}")
        pipeline_meta = load_pipeline_metadata(metadata_path)
        print(f"[INFO] Modo pipeline: metadata {metadata_path}", flush=True)

    settings = Settings.default()
    if device:
        settings.detection.device = device

    detector = None
    ball = None
    if pipeline_meta is None:
        detector = RFDETRDetector(settings.detection)
        ball_s = BallTrackingSettings(method="kalman")
        if require_parabola:
            ball_s.require_parabola = True
        ball = KalmanBallTracker(ball_s)
        print("[INFO] Modo detector: RF-DETR + Kalman (balón/aro)", flush=True)

    court_kp = CourtKeypointDetector(settings.court)
    stab = KeypointStabilizer(settings.court)
    cam = PnPCameraEstimator(settings.court)

    pose_est = release_det = None
    if pose_release:
        pose_s = PoseSettings(); pose_s.enabled = True; pose_s.device = device or "cuda"
        rel_s = ReleaseSettings(); rel_s.enabled = True
        pose_est = PoseEstimator(pose_s)
        release_det = ReleaseDetector(rel_s)
    pose_releases: list[tuple[int, float]] = []

    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir {input_video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cam.set_image_size(w, h)

    print(f"[INFO] Clip: {input_video.name}  ({fps:.1f} fps, {w}x{h})", flush=True)

    # Recolecta por frame: centro del balón (px) y P calibrada, cuando ambos existen.
    samples: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    P_by_frame: dict[int, np.ndarray] = {}   # P de cada frame (para el overlay)
    rim_by_frame: dict[int, tuple[np.ndarray, float]] = {}
    n_ball = n_pose = n_rim = 0
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        kp = court_kp.predict(frame)
        s = stab.update(kp.xy, kp.confidence)
        cam.update(s.xy, s.valid_mask)          # impulsa la calibración de focal
        P = cam.solve_projection(s.xy, s.valid_mask)

        if pipeline_meta is not None:
            fr_meta = pipeline_meta.get(frame_idx)
            center = ball_center_from_frame(fr_meta)
            rim = rim_observation_from_frame(fr_meta)
            pbox = (
                nearest_player_bbox(fr_meta, center)
                if fr_meta is not None and center is not None else None
            )
        else:
            raw = detector.detect(frame)
            center = _ball_center(raw, ball)
            rim = _rim_observation(raw)
            pbox = _nearest_player_box(raw, center) if center is not None else None

        if center is not None:
            n_ball += 1
        if P is not None:
            n_pose += 1
            P_by_frame[frame_idx] = P
        if center is not None and P is not None:
            samples[frame_idx] = (center, P)
        if rim is not None:
            rim_by_frame[frame_idx] = rim
            n_rim += 1

        if pose_est is not None and center is not None:
            wrists = pose_est.wrists(frame, pbox).wrists() if pbox is not None else []
            ev = release_det.update(frame_idx, wrists, center)
            if ev is not None:
                pose_releases.append((ev.frame_index, ev.confidence))
        frame_idx += 1
    cap.release()

    print(
        f"[INFO] {frame_idx} frames procesados | con balón: {n_ball} | "
        f"con pose PnP (P): {n_pose} | con ambos: {len(samples)} | con aro: {n_rim}"
    )
    if not samples:
        raise Shot3DError(
            "No se obtuvieron muestras con balón + cámara calibrada. "
            "Si 'con pose PnP' es 0, la focal no llegó a calibrarse."
        )

    if start_frame is not None and end_frame is not None:
        lo, hi = start_frame, end_frame
    else:
        arc = _best_arc_window(samples, fps, min_segment)
        if arc is None:
            raise Shot3DError(
                "No se detectó ningún arco balístico claro (balón que sube y baja)."
            )
        lo, hi = arc
        print(f"[INFO] Arco balístico autoseleccionado: frames {lo}–{hi}", flush=True)
        lo_heur = None
        if extend_to_release:
            lo2, _ = _extend_window_to_release(samples, lo, hi, fps)
            lo_heur = lo2
            if lo2 < lo:
                print(f"[INFO] Ventana extendida (heurística) hasta la suelta: frames {lo2}–{hi}", flush=True)
                lo = lo2
        if pose_releases:
            cand = [fr for fr, _ in pose_releases
                    if (hi - int(1.5 * fps)) <= fr <= hi and fr in samples]
            if cand:
                lo_pose = min(cand)
                cmp = "" if lo_heur is None else f" (heurística daba {lo_heur})"
                if _window_is_physical(samples, lo_pose, hi, fps):
                    print(f"[INFO] Suelta por POSE en frame {lo_pose}{cmp} → inicio de ventana", flush=True)
                    lo = lo_pose
                else:
                    print(f"[INFO] Suelta por POSE en frame {lo_pose}{cmp} pero el ajuste "
                          f"3D no es físico → se mantiene la heurística", flush=True)
            else:
                print(f"[INFO] Pose detectó sueltas en {[fr for fr,_ in pose_releases]} "
                      f"pero ninguna dentro del arco; se mantiene la heurística", flush=True)

    seg = [(f, *samples[f]) for f in sorted(samples) if lo <= f <= hi]
    if len(seg) < min_segment:
        raise Shot3DError(
            f"Tramo demasiado corto ({len(seg)} frames < {min_segment})."
        )

    frames = [f for f, _, _ in seg]
    uv = np.array([c for _, c, _ in seg])
    Ps = [P for _, _, P in seg]
    times = np.array([(f - frames[0]) / fps for f in frames])

    traj = solve_ballistic_trajectory(Ps, uv, times)

    # --- Informe (en metros; el solver trabaja internamente en pies) ---
    rx, ry = traj.release_point_ft * FT_TO_M
    apex_m = traj.apex_height_ft * FT_TO_M
    print("\n=== Trayectoria 3D reconstruida ===")
    print(f"detecciones usadas : {len(seg)}  (frames {frames[0]}–{frames[-1]})")
    print(f"RMSE reproyección  : {traj.reproj_rmse_px:.2f} px")
    print(f"punto de suelta    : X={rx:.1f} m, Y={ry:.1f} m  (Z={traj.points_3d[0,2]*FT_TO_M:.1f} m)")
    print(f"velocidad salida   : {traj.launch_speed_fps * FT_TO_M:.1f} m/s")
    print(f"ángulo de salida   : {traj.launch_angle_deg:.1f}°")
    print(f"ápice              : {apex_m:.2f} m  (t={traj.apex_time_s:.2f} s)")

    # Veredicto de cordura física frente al aro (3.05 m). Los umbrales se evalúan
    # sobre las magnitudes en pies y se reportan en metros.
    apex = traj.apex_height_ft
    plausible = (
        traj.reproj_rmse_px < 25.0
        and apex > RIM_HEIGHT_FT
        and apex < 30.0
        and 20.0 < traj.launch_angle_deg < 75.0
    )
    verdict = "PLAUSIBLE" if plausible else "DUDOSA (revisar calibración/tramo)"
    print(f"\nveredicto físico   : {verdict}")
    print(
        "  criterios: RMSE<25px, "
        f"ápice {apex_m:.2f}m {'>' if apex > RIM_HEIGHT_FT else '<='} aro(3.05m), "
        f"ángulo {traj.launch_angle_deg:.0f}° en [20,75]"
    )

    def oriented(P: np.ndarray) -> np.ndarray:
        if not traj.oriented:
            return P
        Pf = P.copy()
        Pf[:, 2] *= -1.0
        return Pf

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        ball_by_frame = {f: samples[f][0] for f in samples}
        overlay = _build_overlay_by_frame(
            traj, frames, P_by_frame, ball_by_frame, rim_by_frame, fps, oriented,
        )
        payload: dict[str, Any] = {
            "clip": input_video.name,
            "units": "meters",
            "fps": fps,
            "frames": frames,
            "params_X0_Vx_Y0_Vy_Z0_Vz_m": (traj.params * FT_TO_M).tolist(),
            "points_3d_m": (traj.points_3d * FT_TO_M).tolist(),
            "reproj_rmse_px": traj.reproj_rmse_px,
            "apex_height_m": apex_m,
            "release_xyz_m": [rx, ry, float(traj.points_3d[0, 2] * FT_TO_M)],
            "launch_speed_mps": traj.launch_speed_fps * FT_TO_M,
            "launch_angle_deg": traj.launch_angle_deg,
            "plausible": plausible,
            "overlay": overlay,
        }
        json_out.write_text(json.dumps(payload, indent=2))
        print(f"\n[INFO] Trayectoria 3D → {json_out}", flush=True)

    if video_out is not None:
        ball_by_frame = {f: samples[f][0] for f in samples}
        _render_overlay(
            input_video, video_out, traj, frames,
            P_by_frame, ball_by_frame, rim_by_frame, fps, (w, h),
        )

    return Shot3DResult(
        frames=frames,
        reproj_rmse_px=traj.reproj_rmse_px,
        apex_height_m=apex_m,
        launch_angle_deg=traj.launch_angle_deg,
        launch_speed_mps=traj.launch_speed_fps * FT_TO_M,
        plausible=plausible,
        video_path=video_out,
        json_path=json_out,
    )
