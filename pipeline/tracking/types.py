"""Dataclass unificada que produce el motor de tracking.

``TrackedEntity`` desacopla el resto del pipeline del backend de tracking:
en modo clásico ``mask`` es ``None`` y todo se decide por ``bbox_xyxy``; en
modo SAM 3 la máscara está presente en GPU y permite recortes con fondo
negro y el cálculo del punto de apoyo a partir del píxel inferior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    import torch


@dataclass
class TrackedEntity:
    track_id: int
    class_id: int
    confidence: float
    bbox_xyxy: np.ndarray
    mask: Optional["torch.Tensor"] = None
    embedding: Optional["torch.Tensor"] = None

    def has_mask(self) -> bool:
        return self.mask is not None
