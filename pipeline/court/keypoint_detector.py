"""Detección de los 33 keypoints de la cancha con un modelo YOLO‑pose.

Se mantiene como wrapper fino para poder cambiar de backend (DEKR,
HRNet, etc.) en el futuro sin tocar el resto del pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from ultralytics import YOLO

from pipeline.config import CourtSettings


@dataclass
class KeypointPrediction:
    """Salida cruda del detector para un frame."""

    xy: np.ndarray              # (33, 2) coordenadas en píxeles
    confidence: np.ndarray      # (33,)  confianza [0, 1]

    def is_empty(self) -> bool:
        return self.xy.size == 0


class CourtKeypointDetector:
    """Wrapper sobre `ultralytics.YOLO` para inferencia de keypoints.

    Usa el engine TensorRT FP16 si está disponible (``settings.engine_path``),
    con PyTorch FP16 como fallback. El engine TRT se exporta con:
        python scripts/export_yolo_tensorrt.py --model court-keypoints
    """

    def __init__(self, settings: CourtSettings, device: Optional[str] = None) -> None:
        self._settings = settings
        self._device = device or "0"
        self._half = False

        engine = Path(settings.engine_path)
        if settings.prefer_tensorrt and engine.is_file():
            model_path = str(engine)
            # El engine TRT ya corre en la precisión con la que fue exportado.
            self._half = False
            backend = "tensorrt"
        else:
            model_path = settings.model_path
            self._half = True   # FP16 en PyTorch cuando no hay engine
            backend = "pytorch (fp16)"
            if settings.prefer_tensorrt:
                print(
                    f"[INFO] CourtKeypointDetector: engine TRT no encontrado "
                    f"({engine}); usando {model_path} ({backend})"
                )

        print(f"[INFO] CourtKeypointDetector: {model_path} ({backend}, device={self._device})")
        self._model = YOLO(model_path)

    def predict(self, frame_bgr: np.ndarray) -> KeypointPrediction:
        """Devuelve la predicción de los 33 keypoints para el frame."""
        results = self._model.predict(
            source=frame_bgr,
            imgsz=self._settings.input_resolution,
            device=self._device,
            half=self._half,
            verbose=False,
        )[0]
        n = self._settings.num_keypoints

        if results.keypoints is None or results.keypoints.xy is None or len(results.keypoints.xy) == 0:
            return KeypointPrediction(
                xy=np.zeros((n, 2), dtype=np.float32),
                confidence=np.zeros(n, dtype=np.float32),
            )

        xy = results.keypoints.xy[0].detach().cpu().numpy().astype(np.float32)
        if results.keypoints.conf is not None:
            conf = results.keypoints.conf[0].detach().cpu().numpy().astype(np.float32)
        else:
            conf = np.ones(n, dtype=np.float32)

        if xy.shape[0] != n:
            padded = np.zeros((n, 2), dtype=np.float32)
            padded_conf = np.zeros(n, dtype=np.float32)
            k = min(n, xy.shape[0])
            padded[:k] = xy[:k]
            padded_conf[:k] = conf[:k]
            return KeypointPrediction(xy=padded, confidence=padded_conf)

        return KeypointPrediction(xy=xy, confidence=conf)
