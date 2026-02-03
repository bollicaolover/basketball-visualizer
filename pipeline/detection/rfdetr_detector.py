"""Detector RF-DETR local (11 clases del dataset `basketball-player-detection`).

Carga el checkpoint entrenado por el usuario (`checkpoint_best_ema.pth`) con el
paquete `rfdetr` y devuelve `sv.Detections`, igual que `inference.get_model` en
el cuaderno pero **sin inferencia alojada**: todo corre local sobre el pesos
propio. El orquestador reparte las detecciones por class-id.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import supervision as sv

from pipeline.config import DetectionSettings

_VARIANTS = {
    "base": "RFDETRBase",
    "nano": "RFDETRNano",
    "medium": "RFDETRMedium",
    "small": "RFDETRSmall",
    "large": "RFDETRLarge",
}

# El dataset `basketball-player-detection` tiene 11 categorías (ids 0-10).
NUM_CLASSES = 11


class RFDETRDetector:
    """Wrapper sobre `rfdetr.RFDETR*` cargando un checkpoint local."""

    def __init__(self, settings: DetectionSettings) -> None:
        self._s = settings
        ckpt = Path(settings.checkpoint_path)
        if not ckpt.is_file():
            raise FileNotFoundError(
                f"Checkpoint RF-DETR no encontrado: {ckpt}\n"
                "Ejecuta `python scripts/fetch_models.py` para enlazarlo, o "
                "entrena con `python scripts/train_rfdetr.py`."
            )

        import rfdetr

        cls_name = _VARIANTS.get(settings.variant, "RFDETRBase")
        model_cls = getattr(rfdetr, cls_name)
        print(f"[INFO] RFDETRDetector: {cls_name} <- {ckpt}")
        self._model = model_cls(
            pretrain_weights=str(ckpt),
            num_classes=NUM_CLASSES,
            resolution=settings.resolution,
            device=settings.device,
        )
        # Acelera la inferencia (compila/optimiza) si el backend lo soporta.
        try:
            self._model.optimize_for_inference()
        except Exception:  # noqa: BLE001
            pass

    def detect(self, frame_bgr: np.ndarray) -> sv.Detections:
        """Devuelve todas las detecciones del frame (RGB internamente)."""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        detections = self._model.predict(
            frame_rgb, threshold=self._s.score_threshold,
        )
        if detections is None or len(detections) == 0:
            return sv.Detections.empty()
        return detections
