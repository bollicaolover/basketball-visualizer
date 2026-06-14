"""Resolutor de posesión: decide qué ``track_id`` tiene el balón cada frame.

Diseño (ver ``PossessionSettings`` para el porqué de cada parámetro):

  1. **Candidato por frame** combinando dos señales en espacio imagen:
       - *Primaria*: la detección ``player-in-possession`` (clase 5) de
         RF-DETR por encima de ``class5_score_threshold``, asociada al track
         con mayor IoU (``class5_iou``) y, si ``class5_requires_ball``, con el
         balón cerca del jugador. Manda cuando pasa todos los filtros.
       - *Secundaria*: distancia del centro del balón al bbox del jugador,
         normalizada por la altura del bbox (invariante a la perspectiva).
         Cubre los frames en que la clase 5 no aparece.
     Se trabaja en imagen y **no** sobre el balón proyectado al suelo: la
     homografía supone el punto sobre el plano y un balón en mano se desvía
     varios pies por parallax.

  2. **Máquina de estados temporal** sobre ese candidato:
       - Para arrebatar la posesión, el nuevo candidato debe ganar
         ``switch_frames`` frames seguidos (histéresis → sin parpadeo).
       - Si no hay candidato durante ``loose_frames`` frames, la posesión
         pasa a ``None`` (balón suelto: pase, tiro o rebote en vuelo).

El estado persiste entre frames (como ``BallTracker``); ``reset()`` lo limpia
al empezar un vídeo nuevo.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import supervision as sv

from pipeline.config import PossessionSettings
from pipeline.tracking.types import TrackedEntity


class PossessionResolver:
    def __init__(self, settings: Optional[PossessionSettings] = None) -> None:
        self._s = settings or PossessionSettings()
        self._possessor: Optional[int] = None
        self._last_possessor: Optional[int] = None  # para fast-return
        self._pending: Optional[int] = None
        self._pending_count: int = 0
        self._loose_count: int = 0
        # Frames de posesión acumulados por track (para el resumen de % posesión).
        self._frames_by_track: Dict[int, int] = {}

    def reset(self) -> None:
        self._possessor = None
        self._last_possessor = None
        self._pending = None
        self._pending_count = 0
        self._loose_count = 0
        self._frames_by_track.clear()

    # ------------------------------------------------------------------
    def update(
        self,
        ball_detections: Optional[sv.Detections],
        entities: List[TrackedEntity],
        in_possession_detections: Optional[sv.Detections] = None,
        hoop_detections: Optional[sv.Detections] = None,
    ) -> Optional[int]:
        """Devuelve el ``track_id`` poseedor de este frame (o ``None``)."""
        if not self._s.enabled or not entities:
            self._register_none()
            return self._possessor

        candidate = self._frame_candidate(
            ball_detections, entities, in_possession_detections, hoop_detections,
        )
        self._advance_state(candidate)
        if self._possessor is not None:
            self._frames_by_track[self._possessor] = (
                self._frames_by_track.get(self._possessor, 0) + 1
            )
        return self._possessor

    def possession_frames(self) -> Dict[int, int]:
        """Frames totales de posesión por track (para estadísticas)."""
        return dict(self._frames_by_track)

    # ------------------------------------------------------------------
    def _frame_candidate(
        self,
        ball_detections: Optional[sv.Detections],
        entities: List[TrackedEntity],
        in_possession_detections: Optional[sv.Detections],
        hoop_detections: Optional[sv.Detections] = None,
    ) -> Optional[int]:
        # (1) Señal primaria: clase 5 asociada por IoU al track.
        class5 = self._class5_candidate(
            ball_detections, in_possession_detections, entities,
        )
        if class5 is not None:
            return class5

        # (2) Señal secundaria: proximidad balón→jugador en imagen.
        return self._proximity_candidate(ball_detections, entities, hoop_detections)

    def _ball_near_rim(
        self,
        ball_c: np.ndarray,
        hoop_detections: Optional[sv.Detections],
    ) -> bool:
        if (
            not self._s.suppress_proximity_near_rim
            or hoop_detections is None
            or len(hoop_detections) == 0
        ):
            return False
        for box in hoop_detections.xyxy:
            x1, y1, x2, y2 = map(float, box)
            rcx = (x1 + x2) / 2.0
            rcy = (y1 + y2) / 2.0
            rh = max(y2 - y1, 1.0)
            dist = float(np.hypot(ball_c[0] - rcx, ball_c[1] - rcy))
            if dist <= self._s.rim_suppress_factor * rh:
                return True
        return False

    def _ball_center(
        self, ball_detections: Optional[sv.Detections],
    ) -> Optional[np.ndarray]:
        if ball_detections is None or len(ball_detections) == 0:
            return None
        bx = ball_detections.xyxy[0]
        return np.array(
            [(bx[0] + bx[2]) / 2.0, (bx[1] + bx[3]) / 2.0], dtype=np.float32,
        )

    def _ball_edge_distance_heights(
        self, ball_c: np.ndarray, bbox_xyxy: np.ndarray,
    ) -> float:
        x1, y1, x2, y2 = map(float, bbox_xyxy)
        height = max(y2 - y1, 1.0)
        m = self._s.bbox_margin_px
        dx = max(x1 - m - ball_c[0], 0.0, ball_c[0] - (x2 + m))
        dy = max(y1 - m - ball_c[1], 0.0, ball_c[1] - (y2 + m))
        return float(np.hypot(dx, dy)) / height

    def _ball_near_entity(
        self,
        ball_detections: Optional[sv.Detections],
        entity: TrackedEntity,
        max_heights: Optional[float] = None,
    ) -> bool:
        ball_c = self._ball_center(ball_detections)
        if ball_c is None:
            return False
        limit = (
            self._s.max_ball_distance_heights
            if max_heights is None
            else max_heights
        )
        return self._ball_edge_distance_heights(ball_c, entity.bbox_xyxy) <= limit

    def _class5_candidate(
        self,
        ball_detections: Optional[sv.Detections],
        in_possession_detections: Optional[sv.Detections],
        entities: List[TrackedEntity],
    ) -> Optional[int]:
        if in_possession_detections is None or len(in_possession_detections) == 0:
            return None
        player_boxes = np.stack([e.bbox_xyxy for e in entities]).astype(np.float32)
        det_boxes = in_possession_detections.xyxy.astype(np.float32)
        iou = sv.box_iou_batch(player_boxes, det_boxes)  # (n_players, n_dets)
        if iou.size == 0 or float(iou.max()) < self._s.class5_iou:
            return None
        best_player_idx, _ = np.unravel_index(int(np.argmax(iou)), iou.shape)
        entity = entities[best_player_idx]
        if self._s.class5_requires_ball and not self._ball_near_entity(
            ball_detections, entity, self._s.class5_max_ball_distance_heights,
        ):
            return None
        return int(entity.track_id)

    def _proximity_candidate(
        self,
        ball_detections: Optional[sv.Detections],
        entities: List[TrackedEntity],
        hoop_detections: Optional[sv.Detections] = None,
    ) -> Optional[int]:
        ball_c = self._ball_center(ball_detections)
        if ball_c is None:
            return None
        if self._ball_near_rim(ball_c, hoop_detections):
            return None

        best_tid: Optional[int] = None
        best_score = np.inf
        for e in entities:
            edge_norm = self._ball_edge_distance_heights(ball_c, e.bbox_xyxy)
            if edge_norm > self._s.max_ball_distance_heights:
                continue
            x1, y1, x2, y2 = e.bbox_xyxy
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            height = max(float(y2 - y1), 1.0)
            center_norm = float(np.hypot(ball_c[0] - cx, ball_c[1] - cy)) / height
            score = edge_norm + 1e-3 * center_norm
            if score < best_score:
                best_score = score
                best_tid = int(e.track_id)
        return best_tid

    # ------------------------------------------------------------------
    def _advance_state(self, candidate: Optional[int]) -> None:
        if candidate is not None:
            self._loose_count = 0
            if candidate == self._possessor:
                self._pending = None
                self._pending_count = 0
                return
            # Fast-return: el último poseedor recupera la posesión en 1 frame
            # (evita esperar switch_frames tras un pase corto o rebote propio).
            if candidate == self._last_possessor and self._possessor is None:
                self._possessor = candidate
                self._last_possessor = candidate
                self._pending = None
                self._pending_count = 0
                return
            # Candidato distinto del poseedor actual: acumula histéresis.
            if candidate == self._pending:
                self._pending_count += 1
            else:
                self._pending = candidate
                self._pending_count = 1
            if self._pending_count >= self._s.switch_frames:
                self._possessor = candidate
                self._last_possessor = candidate
                self._pending = None
                self._pending_count = 0
            return
        self._register_none()

    def _register_none(self) -> None:
        self._pending = None
        self._pending_count = 0
        self._loose_count += 1
        if self._loose_count >= self._s.loose_frames:
            if self._possessor is not None:
                self._last_possessor = self._possessor
            self._possessor = None
