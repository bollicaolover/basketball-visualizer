"""Interfaz de tracking + adaptador desde ``sv.Detections``.

En esta iteración el orquestador sigue invocando :class:`YOLODetector` y
:class:`PlayerTracker` directamente; :func:`tracked_entities_from_detections`
materializa la lista de :class:`TrackedEntity` que consumirán las estrategias
de cropping y de punto de apoyo. Cuando se integre SAM 3 sustituiremos esta
cadena por :class:`SAMTracker` y haremos que produzca entidades con máscara.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import numpy as np
import supervision as sv

from pipeline.tracking.types import TrackedEntity


class ITracker(ABC):
    """Motor de tracking de jugadores con identidad temporal estable."""

    def prepare_video(self, video_path: str) -> None:
        """Hook opcional llamado una vez antes del primer ``update``.

        Necesario para backends que requieren cargar el vídeo entero (SAM 2/3
        video predictor). Los trackers streaming (BoT-SORT) ignoran este hook.
        """

    @abstractmethod
    def update(self, frame_bgr: np.ndarray, frame_idx: int) -> List[TrackedEntity]:
        """Devuelve la lista de entidades rastreadas para este frame."""

    @abstractmethod
    def reset(self) -> None:
        """Reinicia el estado interno (cambio de clip, fin de vídeo, etc.)."""


def tracked_entities_from_detections(detections: sv.Detections) -> List[TrackedEntity]:
    """Construye ``List[TrackedEntity]`` a partir de un ``sv.Detections``.

    Adaptador puente para la primera iteración: el orquestador sigue usando
    el pipeline clásico (YOLO + BoT-SORT) y, justo después del tracking,
    materializa las entidades para que las downstream strategies puedan
    operar sobre ellas. ``mask`` queda en ``None`` por construcción.
    """

    if detections is None or len(detections) == 0:
        return []

    track_ids = detections.tracker_id
    class_ids = detections.class_id
    confidences = detections.confidence
    boxes = detections.xyxy

    out: List[TrackedEntity] = []
    for i in range(len(detections)):
        tid = track_ids[i] if track_ids is not None else None
        if tid is None:
            continue
        conf = float(confidences[i]) if confidences is not None else 0.0
        cls = int(class_ids[i]) if class_ids is not None else -1
        bbox = boxes[i].astype(np.float32)
        out.append(
            TrackedEntity(
                track_id=int(tid),
                class_id=cls,
                confidence=conf,
                bbox_xyxy=bbox,
                mask=None,
                embedding=None,
            )
        )
    return out
