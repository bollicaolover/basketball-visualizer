"""Estimación de pose del jugador en posesión con YOLOv8-pose.

Para detectar el instante de **suelta** del tiro (cuando el balón se separa de la
mano hacia arriba) necesitamos la posición de las muñecas del tirador. Por
eficiencia, la pose se infiere **solo sobre el recorte del bbox del poseedor**
—no sobre el frame completo— y solo cuando hay poseedor; así el coste añadido es
despreciable frente a RF-DETR/SAM del pipeline.

Modelo: YOLOv8-pose COCO (17 keypoints); muñeca izquierda = índice 9, derecha =
10. Se devuelven en coordenadas del **frame completo** (se deshace el recorte).

El import de ``ultralytics`` es perezoso para no penalizar a quien no use pose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from pipeline.config import PoseSettings


@dataclass
class WristEstimate:
    """Muñecas del poseedor en coordenadas de frame completo (px)."""

    left: Optional[np.ndarray]    # (x, y) o None si no es fiable
    right: Optional[np.ndarray]   # (x, y) o None si no es fiable
    left_conf: float = 0.0
    right_conf: float = 0.0

    def wrists(self) -> list[np.ndarray]:
        """Lista de muñecas válidas (0, 1 o 2)."""
        return [w for w in (self.left, self.right) if w is not None]


class PoseEstimator:
    """Wrapper ligero de YOLOv8-pose que infiere sobre el recorte del poseedor."""

    def __init__(self, settings: Optional[PoseSettings] = None) -> None:
        self._s = settings or PoseSettings()
        self._model = None  # carga perezosa

    def available(self) -> bool:
        return self._s.enabled

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from ultralytics import YOLO  # import perezoso

        self._model = YOLO(self._s.model_path)

    def wrists(self, frame_bgr: np.ndarray, bbox_xyxy: np.ndarray) -> WristEstimate:
        """Estima las muñecas del jugador contenido en ``bbox_xyxy``.

        Args:
            frame_bgr: frame completo BGR (H, W, 3).
            bbox_xyxy: caja del poseedor [x1, y1, x2, y2] en coords de frame.

        Returns:
            :class:`WristEstimate` con las muñecas en coords de frame completo.
            Muñecas por debajo de ``min_kpt_conf`` se devuelven como ``None``.
        """
        empty = WristEstimate(left=None, right=None)
        if not self._s.enabled or frame_bgr is None or bbox_xyxy is None:
            return empty

        h, w = frame_bgr.shape[:2]
        m = self._s.crop_margin_px
        x1 = max(0, int(bbox_xyxy[0]) - m)
        y1 = max(0, int(bbox_xyxy[1]) - m)
        x2 = min(w, int(bbox_xyxy[2]) + m)
        y2 = min(h, int(bbox_xyxy[3]) + m)
        if x2 - x1 < 4 or y2 - y1 < 4:
            return empty

        self._ensure_model()
        crop = frame_bgr[y1:y2, x1:x2]
        res = self._model.predict(
            crop, device=self._s.device, verbose=False, conf=0.25,
        )
        if not res or res[0].keypoints is None or len(res[0].keypoints) == 0:
            return empty

        # Persona dominante en su propio recorte = la de mayor confianza de caja.
        r = res[0]
        boxes_conf = r.boxes.conf.cpu().numpy() if r.boxes is not None else None
        idx = int(np.argmax(boxes_conf)) if boxes_conf is not None and len(boxes_conf) else 0

        kxy = r.keypoints.xy.cpu().numpy()[idx]      # (17, 2) en coords del crop
        kconf = (
            r.keypoints.conf.cpu().numpy()[idx]
            if r.keypoints.conf is not None
            else np.ones(len(kxy), dtype=np.float32)
        )

        def _wrist(i: int):
            if i >= len(kxy) or float(kconf[i]) < self._s.min_kpt_conf:
                return None, 0.0
            pt = np.array([kxy[i][0] + x1, kxy[i][1] + y1], dtype=np.float32)
            return pt, float(kconf[i])

        left, lc = _wrist(self._s.left_wrist_idx)
        right, rc = _wrist(self._s.right_wrist_idx)
        return WristEstimate(left=left, right=right, left_conf=lc, right_conf=rc)
