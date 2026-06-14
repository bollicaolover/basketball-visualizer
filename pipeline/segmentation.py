"""Segmentación del vídeo en tramos cortos para reiniciar la sesión SAM.

Procesar un vídeo largo de una sola sesión SAM falla de dos formas: el tracking
se degrada (jugadores que salen de cámara no se recuperan) y la sesión acumula
estado por frame hasta agotar la VRAM. La solución es quedarse siempre en el
régimen "vídeo corto": trocear en segmentos y reiniciar SAM en cada límite.

El límite se decide con tres señales **fiables** (ninguna depende de la posesión
a nivel de jugador, que es ruidosa):

  * **Cambio de posesión de equipo** (`TeamPossessionTracker`) — histéresis
    fuerte a nivel equipo: solo cambia de bando cuando el rival mantiene el balón
    N frames seguidos, filtrando desvíos, robos fallidos y rebotes sueltos.
  * **Corte de cámara** (`SceneCutDetector`) — caída brusca de correlación de
    histograma entre frames; tras un corte el memory bank de SAM ya no sirve.
  * **Tope de longitud** — red de seguridad que acota la memoria aunque no haya
    corte ni cambio de equipo (posesión muy larga, balón perdido mucho rato).

`SegmentController` reúne las tres. El orquestador llama a ``pre_frame`` antes de
procesar cada frame (cortes/longitud) y a ``post_frame`` después (cambio de
equipo, que solo se conoce tras resolver la posesión del frame).
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from pipeline.config import SegmentationSettings


class SceneCutDetector:
    """Detecta cortes de cámara por correlación de histograma BGR."""

    def __init__(self, min_correlation: float) -> None:
        self._thr = min_correlation
        self._prev: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._prev = None

    def update(self, frame_bgr: np.ndarray) -> bool:
        small = cv2.resize(frame_bgr, (64, 36))
        hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8],
                            [0, 256, 0, 256, 0, 256])
        cv2.normalize(hist, hist)
        hist = hist.flatten()
        cut = False
        if self._prev is not None:
            corr = cv2.compareHist(self._prev, hist, cv2.HISTCMP_CORREL)
            cut = corr < self._thr
        self._prev = hist
        return cut


class TeamPossessionTracker:
    """Posesión a nivel equipo con histéresis fuerte (punto 3 de la lógica)."""

    def __init__(self, switch_frames: int) -> None:
        self._n = max(1, switch_frames)
        self._team: Optional[str] = None
        self._pending: Optional[str] = None
        self._count = 0

    def reset(self) -> None:
        self._team = None
        self._pending = None
        self._count = 0

    @property
    def team(self) -> Optional[str]:
        return self._team

    def update(self, possessor_team: Optional[str]) -> Tuple[Optional[str], bool]:
        """Avanza el estado con el equipo poseedor de este frame.

        ``possessor_team`` es ``'white'``/``'dark'`` o ``None`` (balón suelto/en
        vuelo). Devuelve ``(equipo_actual, cambió)``. La primera adquisición fija
        el equipo sin marcar cambio; un cambio de bando exige que el rival
        mantenga el balón ``switch_frames`` frames seguidos.
        """
        if possessor_team is None:
            # Balón suelto o en vuelo (pase/tiro): se mantiene el último equipo,
            # sin avanzar la histéresis. Un desvío momentáneo no cuenta.
            return self._team, False
        if possessor_team == self._team:
            self._pending = None
            self._count = 0
            return self._team, False
        # Equipo distinto del actual (o primer poseedor): acumula histéresis.
        if possessor_team == self._pending:
            self._count += 1
        else:
            self._pending = possessor_team
            self._count = 1
        if self._team is None or self._count >= self._n:
            changed = self._team is not None
            self._team = possessor_team
            self._pending = None
            self._count = 0
            return self._team, changed
        return self._team, False


class SegmentController:
    """Decide cuándo reiniciar la sesión SAM combinando las tres señales."""

    def __init__(self, settings: SegmentationSettings) -> None:
        self._s = settings
        self._cut = SceneCutDetector(settings.scene_cut_correlation)
        self._team = TeamPossessionTracker(settings.team_switch_frames)
        self._frames_in_segment = 0
        self._team_change_pending = False
        self.segment_index = 0

    def reset(self) -> None:
        self._cut.reset()
        self._team.reset()
        self._frames_in_segment = 0
        self._team_change_pending = False
        self.segment_index = 0

    def pre_frame(self, frame_bgr: np.ndarray, frame_index: int) -> Optional[str]:
        """Antes de procesar el frame: ¿hay que reiniciar SAM aquí?

        Devuelve el motivo (str) si toca reiniciar, o ``None``. El cambio de
        posesión se detecta en ``post_frame`` (queda pendiente para el siguiente
        frame); el corte de cámara y el tope se evalúan aquí.
        """
        cut = self._cut.update(frame_bgr)
        self._frames_in_segment += 1
        if frame_index == 0:
            return None

        # Corte de cámara: siempre reinicia (tras un corte el tracking es basura),
        # tenga la longitud que tenga el segmento.
        if cut:
            return self._fire("corte de cámara")
        # Cambio de posesión: respeta la longitud mínima para no trocear en las
        # ráfagas de posesión disputada.
        if self._team_change_pending:
            if self._frames_in_segment < self._s.min_segment_frames:
                self._team_change_pending = False  # se descarta este límite
                return None
            return self._fire("cambio de posesión")
        if self._frames_in_segment >= self._s.max_segment_frames:
            return self._fire("longitud máxima")
        return None

    def _fire(self, reason: str) -> str:
        self._frames_in_segment = 0
        self._team_change_pending = False
        self.segment_index += 1
        return reason

    def post_frame(self, possessor_team: Optional[str]) -> None:
        """Tras resolver la posesión del frame: actualiza la posesión de equipo."""
        _, changed = self._team.update(possessor_team)
        if changed:
            self._team_change_pending = True
