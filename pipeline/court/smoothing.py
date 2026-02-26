"""Suavizado temporal de las posiciones proyectadas a la cancha.

La homografía estabilizada (ver `pipeline.court.homography`) es ya muy
estable frame a frame, pero el **bounding box** del detector aún oscila
unos cuantos píxeles por jugador, y esa oscilación se amplifica al
proyectar al sistema de la cancha: 10 px en la imagen pueden ser 2‑3 ft
en pies. Sin suavizado, los puntos del mapa táctico tiemblan y
"desaparecen" cuando el tracker pierde la identidad un frame.

Aquí se gestionan dos clases:

* :class:`WorldTrackSmoother` aplica EMA por ``track_id`` para los
  jugadores y mantiene un *holdover* de unos frames cuando un track
  desaparece transitoriamente (oclusión, miss del detector, etc.).

* :class:`BallSmoother` es análogo pero para el balón, que no tiene
  track_id estable: se eligen el candidato más cercano al estado previo
  y se filtran saltos disparatados.

Ambos rechazan **outliers**: cualquier observación que implique un salto
mayor a un umbral configurable (en pies, escala humana) se ignora y se
mantiene la última posición suavizada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
def _teams_compatible(t1: Optional[str], t2: Optional[str]) -> bool:
    """True si los equipos son compatibles (igual, o alguno desconocido)."""
    return t1 is None or t2 is None or t1 == t2


@dataclass
class SmoothingSettings:
    """Parámetros del suavizado posterior a la proyección."""

    # Jugadores
    player_ema_alpha: float = 0.35           # peso del frame actual en el EMA
    # Salto máx tolerado entre frames (en coordenadas EMA, no en posición real).
    # Con EMA α=0.35 el estado suavizado se retrasa v·(1-α)/α ≈ 1.86·v respecto
    # a la posición real, de modo que la distancia estado→observación en régimen
    # permanente es v/α.  Para tolerar sprint NBA (~22 mph a 30fps ≈ 1 ft/frame):
    # salto = 1/0.35 ≈ 2.86 ft → threshold ≥ 3.2.  Usamos 4.0 para dejar margen
    # de ruido proyectivo (~0.5 ft) sin comprometer la detección de outliers reales.
    player_max_jump_ft: float = 4.0
    # Margen adicional por frame de holdover: si el jugador lleva N frames sin
    # detectarse, puede haberse alejado legítimamente hasta N · max_speed ft.
    player_max_speed_ft_per_frame: float = 1.0   # ≈ 20 mph a 30fps
    player_holdover_frames: int = 20         # frames que mantenemos un track sin verlo
    # Distancia máxima (ft) para deduplicar un track en holdover cuando el tracker
    # base asigna un ID nuevo al mismo jugador al reemerger de una oclusión.
    # A 15 mph durante 11 frames ≈ 8 ft; 10 ft da un margen razonable.
    player_holdover_dedup_ft: float = 10.0

    # Balón (mapa 2D, tras homografía)
    ball_ema_alpha: float = 0.5
    ball_max_jump_ft: float = 45.0
    ball_holdover_frames: int = 15

    # Filtrado por ubicación: la cancha NBA mide 94 × 50 ft. Permitimos un
    # margen pequeño fuera de las líneas (bancos, banquillos, etc.), pero
    # cualquier proyección muy fuera del rectángulo es ruido (balón en el
    # aire, falso positivo, etc.).
    in_bounds_margin_ft: float = 6.0


# ---------------------------------------------------------------------------
# Jugadores: EMA por track_id + holdover
# ---------------------------------------------------------------------------
@dataclass
class _TrackState:
    xy_ft: np.ndarray                # (2,) posición suavizada
    team: Optional[str] = None
    frames_missing: int = 0
    last_seen_frame: int = -1


class WorldTrackSmoother:
    """Suaviza posiciones por ``track_id`` con EMA, holdover y outlier reject."""

    def __init__(self, settings: SmoothingSettings) -> None:
        self._s = settings
        self._states: Dict[int, _TrackState] = {}

    def reset(self) -> None:
        self._states.clear()

    def update(
        self,
        frame_index: int,
        observations: Dict[int, Dict],
    ) -> List[Dict]:
        """Actualiza el estado y devuelve la lista de jugadores activos.

        ``observations`` mapea ``track_id`` -> ``{"xy_ft": np.ndarray (2,),
        "team": Optional[str]}``. La salida es la lista a renderizar en
        este frame (jugadores observados + los que estamos manteniendo
        durante el holdover).
        """
        # 1. Procesar tracks observados
        for track_id, obs in observations.items():
            xy_new = np.asarray(obs["xy_ft"], dtype=np.float32)
            team_new = obs.get("team")
            if track_id in self._states:
                prev = self._states[track_id]
                jump = float(np.linalg.norm(xy_new - prev.xy_ft))
                # Umbral efectivo: el umbral base cubre el sprint máximo en un
                # frame; el término adicional escala con los frames de holdover
                # porque un jugador puede haberse alejado legítimamente
                # N * max_speed ft durante N frames sin detección.
                effective_max_jump = (
                    self._s.player_max_jump_ft
                    + prev.frames_missing * self._s.player_max_speed_ft_per_frame
                )
                if jump > effective_max_jump:
                    # Outlier: mantenemos posición previa, contamos como missing.
                    # Si el track lleva demasiados frames rechazados consecutivos
                    # (p. ej. el zoom cambió la homografía y todas las proyecciones
                    # saltan respecto a la posición anclada), lo eliminamos para
                    # que se reinicialice en la posición correcta en el siguiente
                    # frame. Sin esta comprobación el track queda atascado
                    # indefinidamente porque el bucle de eliminación del paso 2
                    # solo actúa sobre tracks *ausentes* de observations.
                    prev.frames_missing += 1
                    if team_new is not None:
                        prev.team = team_new
                    if prev.frames_missing > self._s.player_holdover_frames:
                        del self._states[track_id]
                    continue
                a = self._s.player_ema_alpha
                ema = a * xy_new + (1.0 - a) * prev.xy_ft
                prev.xy_ft = ema
                prev.frames_missing = 0
                prev.last_seen_frame = frame_index
                if team_new is not None:
                    prev.team = team_new
            else:
                self._states[track_id] = _TrackState(
                    xy_ft=xy_new.copy(),
                    team=team_new,
                    frames_missing=0,
                    last_seen_frame=frame_index,
                )
                # Dedup: cuando el tracker base asigna un ID nuevo al mismo
                # jugador (re-ID tras oclusión), el ID anterior queda en
                # holdover y el nuevo aparece en la misma zona. Eliminamos el
                # holdover más cercano compatible para evitar dos puntos en el
                # mapa por el mismo jugador físico.
                if self._s.player_holdover_dedup_ft > 0:
                    best: Optional[tuple] = None   # (dist, holdover_id)
                    for h_id, h_st in self._states.items():
                        if h_id == track_id or h_st.frames_missing == 0:
                            continue
                        if not _teams_compatible(team_new, h_st.team):
                            continue
                        dist = float(np.linalg.norm(xy_new - h_st.xy_ft))
                        if dist <= self._s.player_holdover_dedup_ft:
                            if best is None or dist < best[0]:
                                best = (dist, h_id)
                    if best is not None:
                        del self._states[best[1]]

        # 2. Incrementar contador a los tracks NO observados este frame
        for track_id in list(self._states.keys()):
            if track_id not in observations:
                self._states[track_id].frames_missing += 1
                if self._states[track_id].frames_missing > self._s.player_holdover_frames:
                    del self._states[track_id]

        # 3. Exportar estado actual
        return [
            {
                "track_id": tid,
                "team": st.team,
                "xy_ft": (float(st.xy_ft[0]), float(st.xy_ft[1])),
                "frames_missing": st.frames_missing,
            }
            for tid, st in self._states.items()
        ]


# ---------------------------------------------------------------------------
# Balón: estado único, candidato más cercano al previo
# ---------------------------------------------------------------------------
class BallSmoother:
    """Mantiene la posición del balón con EMA + outlier rejection."""

    def __init__(self, settings: SmoothingSettings) -> None:
        self._s = settings
        self._xy: Optional[np.ndarray] = None
        self._frames_missing: int = 0

    def reset(self) -> None:
        self._xy = None
        self._frames_missing = 0

    def set_position(self, xy_ft: Optional[Sequence[float]]) -> None:
        """Fuerza la posición del balón (usado cuando hay posesor confirmado).

        Resetea el contador de holdover; el smoother queda "atado" al
        nuevo punto y no rechazará el siguiente movimiento por outlier.
        """
        if xy_ft is None:
            self._xy = None
        else:
            self._xy = np.asarray(xy_ft, dtype=np.float32)
        self._frames_missing = 0

    def update(
        self,
        candidates_ft: Sequence[Sequence[float]],
    ) -> Optional[np.ndarray]:
        """Actualiza el estado del balón con los candidatos proyectados.

        ``candidates_ft`` puede contener 0..N posiciones en pies; se elige
        la más cercana al estado previo y se filtran saltos mayores a
        ``ball_max_jump_ft``.
        """
        # Sin candidatos: holdover
        if len(candidates_ft) == 0:
            return self._handle_missing()

        candidates = [np.asarray(c, dtype=np.float32) for c in candidates_ft]

        if self._xy is None:
            # Primer avistamiento: nos quedamos con el primero (sin contexto)
            self._xy = candidates[0].copy()
            self._frames_missing = 0
            return self._xy.copy()

        prev = self._xy
        best_idx = int(
            np.argmin([float(np.linalg.norm(c - prev)) for c in candidates])
        )
        best = candidates[best_idx]
        jump = float(np.linalg.norm(best - prev))

        if jump > self._s.ball_max_jump_ft:
            return self._handle_missing()

        a = self._s.ball_ema_alpha
        ema = a * best + (1.0 - a) * prev
        self._xy = ema
        self._frames_missing = 0
        return self._xy.copy()

    def _handle_missing(self) -> Optional[np.ndarray]:
        self._frames_missing += 1
        if self._xy is None or self._frames_missing > self._s.ball_holdover_frames:
            return None
        return self._xy.copy()


# ---------------------------------------------------------------------------
# Filtros de ubicación
# ---------------------------------------------------------------------------
def is_in_bounds_ft(
    xy_ft: Sequence[float],
    length_ft: float,
    width_ft: float,
    margin_ft: float,
) -> bool:
    """¿La posición proyectada cae dentro de la cancha + un margen?"""
    return (
        -margin_ft <= xy_ft[0] <= length_ft + margin_ft
        and -margin_ft <= xy_ft[1] <= width_ft + margin_ft
    )


def filter_in_bounds(
    positions_ft: Iterable[Sequence[float]],
    length_ft: float,
    width_ft: float,
    margin_ft: float,
) -> List[np.ndarray]:
    """Filtra las posiciones que caigan dentro del rectángulo de la cancha."""
    out: List[np.ndarray] = []
    for xy in positions_ft:
        if is_in_bounds_ft(xy, length_ft, width_ft, margin_ft):
            out.append(np.asarray(xy, dtype=np.float32))
    return out
