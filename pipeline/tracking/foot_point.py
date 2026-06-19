"""Estrategia para calcular el punto de apoyo (pie del jugador) en imagen.

El resultado se proyecta con la homografía a coordenadas de cancha (pies).
Existen dos implementaciones:

* :class:`BBoxFootPoint` — centro horizontal + borde inferior del bbox.
  Es la lógica histórica (anteriormente ``Pipeline._feet_from_boxes``) y se
  usa en modo ``botsort``.
* :class:`MaskFootPoint` (en :mod:`pipeline.tracking.foot_point_mask`) —
  mediana de los píxeles inferiores de la máscara sobre la banda central.
  Pendiente de la integración de SAM 3.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from pipeline.tracking.types import TrackedEntity


class IFootPointEstimator(ABC):
    """Devuelve la coordenada ``(x, y)`` en píxeles imagen del contacto con el suelo."""

    @abstractmethod
    def estimate(self, entity: TrackedEntity) -> np.ndarray:
        """``(2,) float32``. La proyecta ``project_image_points(H, pts)``."""


class BBoxFootPoint(IFootPointEstimator):
    """``(x_center, y_bottom)`` del bbox — paridad bit a bit con el pipeline previo."""

    def estimate(self, entity: TrackedEntity) -> np.ndarray:
        x1, _, x2, y2 = entity.bbox_xyxy
        return np.array([(x1 + x2) / 2.0, y2], dtype=np.float32)
