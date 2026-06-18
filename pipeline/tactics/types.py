"""Estructuras del reconocedor de pantallas (``pipeline/tactics``).

Las posiciones son siempre en **pies** sobre la geometría NBA de
``pipeline/court/geometry.py`` (mismo sistema que ``players[*].x_ft/y_ft`` del
metadata del pipeline).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class PlayerSnapshot:
    """Posición de un jugador en un frame, en coordenadas de cancha (ft)."""

    track_id: int
    team: Optional[str]  # "white" | "dark" | None
    xy: np.ndarray  # (2,) float64 en pies

    @property
    def x(self) -> float:
        return float(self.xy[0])

    @property
    def y(self) -> float:
        return float(self.xy[1])


@dataclass(frozen=True)
class ScreenEvent:
    """Una pantalla reconocida y clasificada.

    Agrega una racha de detecciones frame-a-frame del mismo par de atacantes.
    """

    screener_track: int
    screenee_track: int
    team: Optional[str]            # equipo atacante ("white"/"dark")
    screen_type: str              # "front" | "back" | "down" | "undefined"
    basket: str                   # canasta atacada: "left" | "right"
    start_frame: int
    screen_frame: int             # frame en que el bloqueo está "puesto"
    end_frame: int
    # Trayectoria muestreada en los 3 instantes clave (ft) para trazabilidad.
    screener_init: Tuple[float, float]
    screener_screen: Tuple[float, float]
    screener_last: Tuple[float, float]
    screenee_init: Tuple[float, float]
    screenee_screen: Tuple[float, float]
    screenee_last: Tuple[float, float]

    def to_dict(self) -> dict:
        return {
            "screener_track": int(self.screener_track),
            "screenee_track": int(self.screenee_track),
            "team": self.team,
            "screen_type": self.screen_type,
            "basket": self.basket,
            "start_frame": int(self.start_frame),
            "screen_frame": int(self.screen_frame),
            "end_frame": int(self.end_frame),
            "screener_trajectory": {
                "init": [round(self.screener_init[0], 3), round(self.screener_init[1], 3)],
                "screen": [round(self.screener_screen[0], 3), round(self.screener_screen[1], 3)],
                "last": [round(self.screener_last[0], 3), round(self.screener_last[1], 3)],
            },
            "screenee_trajectory": {
                "init": [round(self.screenee_init[0], 3), round(self.screenee_init[1], 3)],
                "screen": [round(self.screenee_screen[0], 3), round(self.screenee_screen[1], 3)],
                "last": [round(self.screenee_last[0], 3), round(self.screenee_last[1], 3)],
            },
        }


# Detección cruda por frame: (screener_track, screenee_track) o None.
FrameDetection = Optional[Tuple[int, int]]

__all__ = ["PlayerSnapshot", "ScreenEvent", "FrameDetection"]
