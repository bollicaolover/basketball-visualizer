"""Contenedor mutable que viaja a través de las etapas del pipeline.

`Pipeline._process_frame` instancia un `FrameContext` con el frame de entrada
y lo pasa por la cadena de etapas (detección → cancha → tracking → equipos →
dorsal → proyección 2D → render), que van rellenando sus campos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np
import supervision as sv

if TYPE_CHECKING:
    from pipeline.tracking.types import TrackedEntity


@dataclass
class FrameContext:
    """Estado compartido entre etapas para un único frame."""

    # Entrada
    frame_index: int
    frame_bgr: np.ndarray
    frame_height: int
    frame_width: int

    # Detección + tracking
    detections: Optional[sv.Detections] = None        # jugadores + balón (overlay)
    player_detections: Optional[sv.Detections] = None  # subset PLAYER_CLASSES (RF-DETR)
    number_detections: Optional[sv.Detections] = None  # subset NUMBER_CLASS (RF-DETR)
    ball_detections: Optional[sv.Detections] = None     # subset BALL_CLASSES
    hoop_detections: Optional[sv.Detections] = None     # subset RIM_CLASS
    referee_detections: Optional[sv.Detections] = None  # subset REFEREE_CLASS
    # Entidades trackeadas por SAM (bbox + máscara + track_id estable).
    tracked_entities: List["TrackedEntity"] = field(default_factory=list)

    # Identidad
    team_by_track: Dict[int, str] = field(default_factory=dict)   # track_id -> "white"|"dark"
    player_numbers: Dict[int, int] = field(default_factory=dict)  # track_id -> dorsal 0-99
    player_names: Dict[int, str] = field(default_factory=dict)    # track_id -> nombre roster

    # Posesión (opcional, fase futura)
    possessor_track_id: Optional[int] = None

    # Cancha / homografía
    court_keypoints: Optional[np.ndarray] = None
    court_keypoint_confidences: Optional[np.ndarray] = None
    court_keypoint_valid_mask: Optional[np.ndarray] = None
    homography: Optional[np.ndarray] = None
    homography_confidence: float = 0.0

    # Proyecciones a la cancha 2D (pies)
    players_world: List[Dict] = field(default_factory=list)
    # cada item: {"track_id": int, "team": "white|dark|None", "xy_ft": (x, y)}
    possessor_world: Optional[np.ndarray] = None

    # Eventos: resultado del último tiro (resaltado durante varios frames)
    shot_side: Optional[str] = None   # "left" | "right"
    shot_made: Optional[bool] = None  # True = acierto, False = fallo, None = nada

    # Salidas
    overlay_frame: Optional[np.ndarray] = None
    map_frame: Optional[np.ndarray] = None
