"""Estimación robusta de la homografía imagen ↔ cancha 2D.

El reto en vídeo en directo es que los keypoints detectados fluctúan en
qué puntos sobreviven, qué confianza tienen y dónde caen exactamente.
Recalcular `cv2.findHomography` cuadro a cuadro produce un mapa táctico
que "vibra" porque la H cambia mucho con pequeñas variaciones del
conjunto de inliers.

Aquí encadenamos varias estrategias para conseguir estabilidad:

1.  **Filtrado por confianza y validez temporal** (lo hace el
    `KeypointStabilizer` corriente arriba). Llegan aquí sólo los
    keypoints "fiables" del frame.
2.  **Cobertura mínima**: exigimos un nº mínimo de inliers y que estén
    distribuidos en ambos ejes de la cancha. Evita H degeneradas por
    puntos casi colineales en una mitad.
3.  **Pooling de keypoints entre frames** (modo buffer): cuando la cámara
    lleva varios frames estática, acumulamos los pares (imagen, cancha)
    de todos ellos y corremos UN solo RANSAC sobre el conjunto completo.
    Con 6-25 frames × 15-25 keypoints por frame se pasan al RANSAC
    90-600 pares; la varianza del estimador cae drásticamente.
    `CameraSegmentTracker` detecta panes/cortes y vacía el buffer para
    que el estimador no mezcle frames de dos posiciones de cámara.
4.  **RANSAC por frame** (modo single): durante el calentamiento del
    buffer (primeros `h_min_buffer_frames` frames tras un corte) se
    usa el RANSAC tradicional frame a frame con suavizado EMA de H.
5.  **Suavizado temporal de H**: en modo single, `H_t = lerp(H_{t-1},
    H_new, α)` para amortiguar el ruido residual.  En modo buffer, la
    propia acumulación ya promedia, por lo que no se aplica EMA.
6.  **Holdover**: si el fit falla, se reutiliza `H_{t-1}` hasta
    `h_max_holdover_frames` frames con confianza decreciente.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Tuple

import cv2
import numpy as np

from pipeline.config import CourtSettings
from pipeline.court.geometry import vertices_ft
from pipeline.court.segments import CameraSegmentTracker


@dataclass
class HomographyEstimate:
    H: Optional[np.ndarray]      # 3x3 imagen -> cancha (pies), o None
    confidence: float            # 0..1, calidad del fit (1 = nuevo fit perfecto)
    num_inliers: int             # nº puntos usados en el último fit válido
    residual_px: float           # mediana del error de reproyección
    used_cached: bool            # True si reutilizamos H del frame anterior
    reject_reason: Optional[str] = None  # motivo de rechazo del nuevo fit (si aplica)


class HomographyEstimator:
    """Mantiene una H estabilizada a lo largo del vídeo.

    Usa `CameraSegmentTracker` para detectar panes y conmutar entre:
    - **Modo buffer** (cámara estable): RANSAC sobre keypoints acumulados
      de los últimos ``h_buffer_frames`` frames → H muy estable.
    - **Modo single** (buffer frío/cámara en movimiento): RANSAC por frame
      + EMA suave, igual que la implementación anterior.
    """

    def __init__(self, settings: CourtSettings) -> None:
        self._s = settings
        self._world_ft = vertices_ft()          # (33, 2)
        self._H_prev: Optional[np.ndarray] = None
        self._frames_since_fit: int = 0
        self._last_confidence: float = 0.0
        self._last_num_inliers: int = 0
        self._last_residual: float = float("inf")

        # Sliding buffer of (src_pts, dst_pts) from recent stable frames.
        self._kp_buffer: Deque[Tuple[np.ndarray, np.ndarray]] = deque(
            maxlen=settings.h_buffer_frames
        )
        self._seg_tracker = CameraSegmentTracker(settings)

    # ---------------------------------------------------------------
    def reset(self) -> None:
        self._H_prev = None
        self._frames_since_fit = 0
        self._last_confidence = 0.0
        self._last_num_inliers = 0
        self._last_residual = float("inf")
        self._kp_buffer.clear()
        self._seg_tracker.reset()

    # ---------------------------------------------------------------
    def update(
        self,
        kp_xy: np.ndarray,         # (33, 2) keypoints en imagen
        valid_mask: np.ndarray,    # (33,) bool, qué keypoints usar
    ) -> HomographyEstimate:
        """Intenta encajar H en este frame y devuelve la estimación final."""

        # 1. Detect camera pan → clear buffer if detected.
        if self._seg_tracker.update(kp_xy, valid_mask):
            self._kp_buffer.clear()
            # Resetear el baseline del EMA: si no se hace, _smooth() mezclaría
            # la nueva H (posición post-paneo) con la H pre-paneo, produciendo
            # un sesgo sistemático que dura varios frames y hace que todos los
            # jugadores proyectados parezcan desplazarse en el mapa 2D.
            self._H_prev = None

        # 2. Accumulate this frame's keypoints into the buffer.
        if valid_mask.any():
            src = kp_xy[valid_mask].astype(np.float32)
            dst = self._world_ft[valid_mask].astype(np.float32)
            self._kp_buffer.append((src, dst))

        # 3. Choose fit strategy based on buffer warmth.  Si el modo buffer
        # falla, caemos a single-frame: cuando el buffer está "envenenado"
        # con keypoints incompatibles (un pan que el tracker no detectó,
        # estado heredado de otra sesión, etc.), un fit single-frame sí
        # puede tener éxito; si lo tiene, vaciamos el buffer para que se
        # reconstruya desde cero — comportamiento auto-curativo.
        use_buffer = len(self._kp_buffer) >= self._s.h_min_buffer_frames
        if use_buffer:
            new_H, new_inliers, new_residual, reject_reason = self._fit_buffered()
            if new_H is None:
                new_H, new_inliers, new_residual, reject_reason = self._fit(
                    kp_xy, valid_mask,
                )
                if new_H is not None:
                    # Single-frame works, buffered didn't → buffer envenenado.
                    self._kp_buffer.clear()
                    if valid_mask.any():
                        src = kp_xy[valid_mask].astype(np.float32)
                        dst = self._world_ft[valid_mask].astype(np.float32)
                        self._kp_buffer.append((src, dst))
                    use_buffer = False
        else:
            new_H, new_inliers, new_residual, reject_reason = self._fit(kp_xy, valid_mask)

        if new_H is not None:
            if use_buffer:
                # Buffer already averages across frames — skip EMA.
                H_final = new_H / new_H[2, 2]
            else:
                H_final = self._smooth(new_H)
            self._H_prev = H_final
            self._frames_since_fit = 0
            self._last_confidence = self._fit_confidence(new_inliers, new_residual)
            self._last_num_inliers = new_inliers
            self._last_residual = new_residual
            return HomographyEstimate(
                H=H_final.copy(),
                confidence=self._last_confidence,
                num_inliers=new_inliers,
                residual_px=new_residual,
                used_cached=False,
                reject_reason=None,
            )

        # Fit failed: reuse cached H within holdover window.
        if self._H_prev is not None and self._frames_since_fit < self._s.h_max_holdover_frames:
            self._frames_since_fit += 1
            decay = 1.0 - (self._frames_since_fit / max(1, self._s.h_max_holdover_frames))
            conf = self._last_confidence * decay
            return HomographyEstimate(
                H=self._H_prev.copy(),
                confidence=conf,
                num_inliers=self._last_num_inliers,
                residual_px=self._last_residual,
                used_cached=True,
                reject_reason=reject_reason,
            )

        # Neither a new fit nor a valid cache: no H.
        self._H_prev = None
        self._last_confidence = 0.0
        return HomographyEstimate(
            H=None,
            confidence=0.0,
            num_inliers=int(valid_mask.sum()),
            residual_px=float("inf"),
            used_cached=False,
            reject_reason=reject_reason,
        )

    # ---------------------------------------------------------------
    def _fit_buffered(
        self,
    ) -> Tuple[Optional[np.ndarray], int, float, Optional[str]]:
        """RANSAC sobre el pool de keypoints de los últimos N frames estables.

        Al acumular 6-25 frames × 15-25 keypoints cada uno se pasan al
        RANSAC 90-600 pares en lugar de 15-25. El estimador promedia el
        ruido de detección y la varianza de la H resultante cae en un
        orden de magnitud respecto al modo single-frame.
        """
        all_src = np.concatenate([s for s, _ in self._kp_buffer], axis=0)
        all_dst = np.concatenate([d for _, d in self._kp_buffer], axis=0)

        x_span = float(all_dst[:, 0].max() - all_dst[:, 0].min())
        y_span = float(all_dst[:, 1].max() - all_dst[:, 1].min())
        if x_span < self._s.min_world_x_span_ft or y_span < self._s.min_world_y_span_ft:
            return None, len(all_src), float("inf"), f"low_span(x={x_span:.1f}ft,y={y_span:.1f}ft)"

        H, mask = cv2.findHomography(
            all_src, all_dst,
            method=cv2.RANSAC,
            ransacReprojThreshold=self._s.ransac_reproj_threshold,
        )
        if H is None or mask is None:
            return None, len(all_src), float("inf"), "ransac_failed"

        inlier_mask = mask.ravel().astype(bool)
        num_inliers = int(inlier_mask.sum())
        if num_inliers < self._s.min_inliers:
            return None, num_inliers, float("inf"), f"few_inliers({num_inliers}/{self._s.min_inliers})"

        residual_px = _reprojection_residual_px(
            H=H,
            src_pts=all_src[inlier_mask],
            dst_pts=all_dst[inlier_mask],
        )
        if residual_px > self._s.max_residual_px:
            return (
                None, num_inliers, residual_px,
                f"residual({residual_px:.1f}>{self._s.max_residual_px:.1f}px)",
            )

        return H, num_inliers, residual_px, None

    # ---------------------------------------------------------------
    def _fit(
        self,
        kp_xy: np.ndarray,
        valid_mask: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], int, float, Optional[str]]:
        """RANSAC sobre los keypoints de un único frame (modo single).

        Devuelve `(H, num_inliers, median_residual_px, reject_reason)`.
        Si el fit no cumple los requisitos, `H` es `None`.
        """
        n_valid = int(valid_mask.sum())
        if n_valid < self._s.min_inliers:
            return None, n_valid, float("inf"), f"few_kps({n_valid}/{self._s.min_inliers})"

        src = kp_xy[valid_mask].astype(np.float32)
        dst = self._world_ft[valid_mask].astype(np.float32)

        x_span = float(dst[:, 0].max() - dst[:, 0].min())
        y_span = float(dst[:, 1].max() - dst[:, 1].min())
        if x_span < self._s.min_world_x_span_ft or y_span < self._s.min_world_y_span_ft:
            return None, n_valid, float("inf"), f"low_span(x={x_span:.1f}ft,y={y_span:.1f}ft)"

        H, mask = cv2.findHomography(
            src, dst,
            method=cv2.RANSAC,
            ransacReprojThreshold=self._s.ransac_reproj_threshold,
        )
        if H is None or mask is None:
            return None, n_valid, float("inf"), "ransac_failed"

        inlier_mask = mask.ravel().astype(bool)
        num_inliers = int(inlier_mask.sum())
        if num_inliers < self._s.min_inliers:
            return None, num_inliers, float("inf"), f"few_inliers({num_inliers}/{self._s.min_inliers})"

        residual_px = _reprojection_residual_px(
            H=H,
            src_pts=src[inlier_mask],
            dst_pts=dst[inlier_mask],
        )
        if residual_px > self._s.max_residual_px:
            return (
                None, num_inliers, residual_px,
                f"residual({residual_px:.1f}>{self._s.max_residual_px:.1f}px)",
            )

        return H, num_inliers, residual_px, None

    # ---------------------------------------------------------------
    def _smooth(self, H_new: np.ndarray) -> np.ndarray:
        """EMA de H normalizada por su componente [2,2] (modo single)."""
        H_new = H_new / H_new[2, 2]
        if self._H_prev is None:
            return H_new
        a = self._s.h_ema_alpha
        H_blend = a * H_new + (1.0 - a) * self._H_prev
        return H_blend / H_blend[2, 2]

    # ---------------------------------------------------------------
    def _fit_confidence(self, num_inliers: int, residual_px: float) -> float:
        """Confianza ∈ [0, 1] combinando nº de inliers y residual."""
        max_kps = self._world_ft.shape[0]
        ratio = min(num_inliers / max_kps, 1.0)
        res_term = max(0.0, 1.0 - residual_px / max(1e-6, self._s.max_residual_px))
        return 0.6 * ratio + 0.4 * res_term


# ---------------------------------------------------------------------------
# Helpers públicos
# ---------------------------------------------------------------------------
def _reprojection_residual_px(
    H: np.ndarray,
    src_pts: np.ndarray,
    dst_pts: np.ndarray,
) -> float:
    """Mediana del error en píxeles entre src y la reproyección de dst.

    Una H degenerada (p.ej. keypoints casi colineales) puede ser singular:
    en ese caso devolvemos ``inf`` para que el llamador la rechace como un
    fit malo más, en vez de propagar ``LinAlgError``.
    """
    try:
        H_inv = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        return float("inf")
    dst_h = np.hstack([dst_pts, np.ones((dst_pts.shape[0], 1), dtype=dst_pts.dtype)])
    back = (H_inv @ dst_h.T).T
    w = back[:, 2:3]
    if not np.all(np.isfinite(w)) or np.any(np.abs(w) < 1e-12):
        return float("inf")
    back = back[:, :2] / w
    diffs = np.linalg.norm(back - src_pts, axis=1)
    residual = float(np.median(diffs))
    return residual if np.isfinite(residual) else float("inf")


def project_image_points(H: np.ndarray, pts_xy: np.ndarray) -> np.ndarray:
    """Proyecta puntos (N, 2) de la imagen al sistema mundial via H."""
    if pts_xy.size == 0:
        return np.zeros((0, 2), dtype=np.float32)
    pts = pts_xy.reshape(-1, 1, 2).astype(np.float32)
    out = cv2.perspectiveTransform(pts, H).reshape(-1, 2)
    return out
