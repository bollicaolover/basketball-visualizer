"""Punto de apoyo a partir de la máscara binaria de SAM.

Frente al ``BBoxFootPoint`` clásico, este estimador encuentra el píxel real
del contacto con el suelo: el bbox YOLO suele recortar las puntas de los
pies y, en oclusiones parciales, infla la altura hacia arriba sin acercar
el borde inferior al suelo real.

La implementación es íntegramente GPU‑friendly (``torch.where``,
``argmax``, ``median``) y evita transferir la máscara a CPU. El coste por
jugador en 1080p es del orden del milisegundo en A100.
"""

from __future__ import annotations

import numpy as np
import torch

from pipeline.tracking.foot_point import IFootPointEstimator
from pipeline.tracking.types import TrackedEntity


class MaskFootPoint(IFootPointEstimator):
    """Mediana de los píxeles inferiores visibles de la máscara, sobre la banda central.

    Algoritmo:
      1. Detecta columnas con al menos un píxel ``True``.
      2. Restringe a la banda central (``central_band_frac``) para descartar
         brazos extendidos que oscilan más que las piernas.
      3. Por cada columna activa, encuentra la fila más baja con ``True``
         (``argmax`` sobre el flip vertical → conversión a y_max por columna).
      4. Devuelve la mediana de esos y_max. La mediana es robusta a artefactos
         de máscara (píxeles sueltos lejos del cuerpo) sin necesidad de
         morfología extra.

    Si la máscara es ``None`` o está vacía, cae al ``(x_center, y_bottom)``
    del bbox para preservar el contrato con ``project_image_points``.
    """

    def __init__(self, central_band_frac: float = 0.60) -> None:
        if not 0.0 < central_band_frac <= 1.0:
            raise ValueError("central_band_frac debe estar en (0, 1].")
        self.central_band_frac = central_band_frac

    def _fallback_bbox(self, entity: TrackedEntity) -> np.ndarray:
        x1, _, x2, y2 = entity.bbox_xyxy
        return np.array([(x1 + x2) / 2.0, y2], dtype=np.float32)

    def estimate(self, entity: TrackedEntity) -> np.ndarray:
        mask = entity.mask
        if mask is None:
            return self._fallback_bbox(entity)
        if mask.dtype != torch.bool:
            mask = mask.bool()

        col_any = mask.any(dim=0)
        col_idxs = torch.where(col_any)[0]
        if col_idxs.numel() == 0:
            return self._fallback_bbox(entity)

        x_min = int(col_idxs.min().item())
        x_max = int(col_idxs.max().item())
        w = x_max - x_min
        side = int(w * (1.0 - self.central_band_frac) / 2.0)
        keep = (col_idxs >= x_min + side) & (col_idxs <= x_max - side)
        xs_central = col_idxs[keep]
        if xs_central.numel() == 0:
            xs_central = col_idxs

        H = mask.shape[0]
        sub = mask[:, xs_central]                          # (H, K) bool
        # Posición del primer True desde abajo en cada columna activa.
        # Por construcción cada columna en xs_central tiene >=1 True.
        y_from_bottom = sub.flip(0).int().argmax(dim=0)    # (K,)
        y_bot_per_col = (H - 1) - y_from_bottom.float()    # (K,)

        y_foot = float(y_bot_per_col.median().item())
        x_foot = float(xs_central.float().median().item())
        return np.array([x_foot, y_foot], dtype=np.float32)
