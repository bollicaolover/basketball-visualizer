"""Detección de tiro **acertado vs. fallado** y conteo.

A diferencia de un simple contador de canastas, este módulo decide el
*resultado* de cada tiro que llega al aro usando tres señales del detector
RF-DETR:

  - ``ball`` / ``basketball`` (clases 0/1): posición del balón.
  - ``rim`` (clase 10): posición del aro.
  - ``ball-in-basket`` (clase 2): balón atravesando la red (señal de acierto).

Además de balón+aro, las acciones ``player-jump-shot``/``player-layup-dunk``
(clases 6/7) abren también la ventana: en una entrada o un mate el balón va
pegado al cuerpo y a menudo está ocluido, así que sin esta señal los
intentos fallados de ese tipo no se detectarían.

Máquina de estados por tiro:

  1. **IDLE → PENDING**: el balón entra en la vecindad de un aro (distancia al
     centro del aro < ``rim_dist_factor`` × alto del aro), aparece
     ``ball-in-basket``, o el detector marca una acción de tiro (clase 6/7). Se
     memoriza el equipo tirador (último poseedor) y, si se conoce, el lado.
  2. **PENDING → resolución**:
       - *ACIERTO* si ``ball-in-basket`` se confirma ``confirm_frames`` frames.
       - *FALLO* si, **tras llegar el balón al aro**, se aleja ``clear_frames``
         frames sin canasta; o si expira la ventana ``resolve_frames`` (cubre
         entradas/mates ocluidos que nunca dan una lectura limpia en el aro).
  3. **Cooldown** tras resolver para no recontar el mismo rebote.

El resultado se mantiene ``display_frames`` frames para alimentar el resalte
del vídeo y del mapa. El estado persiste entre frames; ``reset()`` lo limpia
al empezar un vídeo nuevo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import supervision as sv

from pipeline.config import ScoreSettings
from pipeline.court.geometry import COURT
from pipeline.court.homography import project_image_points

UNKNOWN_TEAM = "desconocido"


@dataclass
class ShotResult:
    """Resultado de un tiro, para visualización en el frame actual."""

    side: Optional[str]   # "left" | "right" | None
    made: bool            # True = acierto, False = fallo
    team: str             # color del equipo tirador o UNKNOWN_TEAM


@dataclass
class ShotEvent:
    """Un tiro resuelto (registro histórico)."""

    frame_index: int
    side: Optional[str]
    made: bool
    team: str


class ShotTracker:
    def __init__(self, settings: Optional[ScoreSettings] = None, debug: bool = False) -> None:
        self._s = settings or ScoreSettings()
        self._debug = debug
        self.reset()

    def reset(self) -> None:
        self._phase = "idle"            # "idle" | "pending"
        self._timer = 0                 # frames restantes de la ventana
        self._away = 0                  # frames del balón lejos del aro
        self._reached_rim = False       # el balón ya llegó al aro en este tiro
        self._make_streak = 0           # frames consecutivos de ball-in-basket
        self._bib_ever_seen = False     # ball-in-basket detectado al menos 1 vez
        self._cooldown = 0
        self._display_left = 0
        self._shot_side: Optional[str] = None
        self._shot_team: str = UNKNOWN_TEAM
        self._last_team: str = UNKNOWN_TEAM
        self._last_result: Optional[ShotResult] = None

        self._events: List[ShotEvent] = []
        self._by_team: Dict[str, Dict[str, int]] = {}
        self._by_side: Dict[str, Dict[str, int]] = {
            "left": {"made": 0, "missed": 0},
            "right": {"made": 0, "missed": 0},
        }

    # ------------------------------------------------------------------
    def update(
        self,
        ball: Optional[sv.Detections],
        rims: Optional[sv.Detections],
        ball_in_basket: Optional[sv.Detections],
        homography: Optional[np.ndarray],
        frame_index: int,
        possessor_team: Optional[str],
        frame_width: int,
        shot_actions: Optional[sv.Detections] = None,
    ) -> Optional[ShotResult]:
        """Procesa un frame; devuelve el ``ShotResult`` a mostrar (o ``None``)."""
        if not self._s.enabled:
            return None

        if possessor_team is not None:
            self._last_team = possessor_team
        if self._cooldown > 0:
            self._cooldown -= 1
        if self._display_left > 0:
            self._display_left -= 1

        # Señal de acierto: ball-in-basket por encima del umbral, confirmada.
        bib_box = self._best_box(ball_in_basket)
        if bib_box is not None:
            self._make_streak += 1
            self._bib_ever_seen = True
        else:
            self._make_streak = 0
        make_now = self._make_streak >= self._s.confirm_frames

        at_rim, rim_side = self._ball_at_rim(ball, rims, homography, frame_width)
        action_box = self._action_box(shot_actions)
        ball_at_basket = at_rim or bib_box is not None

        # Lado del aro: el aro y `ball-in-basket` son autoritativos (balón en la
        # canasta); la caja de acción es solo un proxy débil (posición del
        # tirador), usado únicamente si no hay nada mejor.
        auth_side = rim_side
        if auth_side is None and bib_box is not None:
            auth_side = self._side_from_box(bib_box, homography, frame_width)
        weak_side = (
            self._side_from_box(action_box, homography, frame_width)
            if action_box is not None else None
        )

        if self._phase == "idle":
            if self._cooldown == 0 and (ball_at_basket or action_box is not None):
                trigger = "ball_at_rim" if ball_at_basket else "action"
                if self._debug:
                    print(f"  [SHOT] frame={frame_index} IDLE→PENDING  trigger={trigger} "
                          f"at_rim={at_rim} bib={bib_box is not None} "
                          f"action={action_box is not None} rim_side={rim_side}", flush=True)
                self._phase = "pending"
                self._timer = self._s.resolve_frames
                self._away = 0
                self._reached_rim = ball_at_basket
                self._bib_ever_seen = bib_box is not None
                self._shot_team = self._last_team
                self._shot_side = auth_side if auth_side is not None else weak_side

        if self._phase == "pending":
            self._timer -= 1
            if ball_at_basket:
                self._reached_rim = True
            # Una pista autoritativa sobrescribe siempre; la débil solo rellena.
            if auth_side is not None:
                self._shot_side = auth_side
            elif self._shot_side is None and weak_side is not None:
                self._shot_side = weak_side

            if self._debug:
                print(f"  [SHOT] frame={frame_index} PENDING  timer={self._timer} "
                      f"ball_at_basket={ball_at_basket} reached_rim={self._reached_rim} "
                      f"away={self._away} make_now={make_now} bib_ever={self._bib_ever_seen}",
                      flush=True)

            if make_now:
                self._resolve(frame_index, made=True)
            elif self._reached_rim:
                # El balón ya tocó el aro: si se aleja sin canasta, es FALLO.
                # Excepción: si ball-in-basket se detectó al menos una vez en
                # esta ventana, el tiro ya entró aunque la streak no se complete.
                if ball_at_basket:
                    self._away = 0
                else:
                    self._away += 1
                if self._away >= self._s.clear_frames or self._timer <= 0:
                    self._resolve(frame_index, made=self._bib_ever_seen)
            elif self._timer <= 0:
                if self._reached_rim or self._bib_ever_seen:
                    # Acción que llegó al aro (o entró directo): sin canasta = FALLO.
                    self._resolve(frame_index, made=self._bib_ever_seen)
                else:
                    # El balón nunca llegó al aro ni entró: falso positivo del detector.
                    # Cancelar la ventana sin registrar ningún tiro.
                    if self._debug:
                        print(f"  [SHOT] frame={frame_index} CANCEL (action trigger, ball never at rim)",
                              flush=True)
                    self._phase = "idle"
                    self._timer = 0
                    self._away = 0
                    self._bib_ever_seen = False
                    self._make_streak = 0

        return self._last_result if self._display_left > 0 else None

    # ------------------------------------------------------------------
    def _resolve(self, frame_index: int, made: bool) -> None:
        if self._debug:
            print(f"  [SHOT] frame={frame_index} RESOLVE  made={made} "
                  f"reached_rim={self._reached_rim} bib_ever={self._bib_ever_seen} "
                  f"side={self._shot_side} team={self._shot_team}", flush=True)
        side = self._shot_side
        team = self._shot_team
        self._events.append(
            ShotEvent(frame_index=frame_index, side=side, made=made, team=team)
        )
        key = "made" if made else "missed"
        self._by_team.setdefault(team, {"made": 0, "missed": 0})[key] += 1
        if side in self._by_side:
            self._by_side[side][key] += 1

        self._last_result = ShotResult(side=side, made=made, team=team)
        self._display_left = self._s.display_frames
        self._cooldown = self._s.cooldown_frames
        self._phase = "idle"
        self._timer = 0
        self._away = 0
        self._reached_rim = False
        self._make_streak = 0
        self._bib_ever_seen = False
        self._shot_side = None

    # ------------------------------------------------------------------
    def _best_box(self, dets: Optional[sv.Detections]) -> Optional[np.ndarray]:
        """Caja de mayor confianza por encima del umbral (o ``None``)."""
        if dets is None or len(dets) == 0:
            return None
        conf = dets.confidence
        if conf is not None:
            keep = conf >= self._s.min_confidence
            if not keep.any():
                return None
            idx = int(np.argmax(np.where(keep, conf, -1.0)))
        else:
            idx = 0
        return dets.xyxy[idx].astype(np.float32)

    def _action_box(self, dets: Optional[sv.Detections]) -> Optional[np.ndarray]:
        """Caja de acción de tiro (jump-shot/layup-dunk) de mayor confianza."""
        if not self._s.use_action_trigger or dets is None or len(dets) == 0:
            return None
        conf = dets.confidence
        if conf is not None:
            keep = conf >= self._s.action_min_confidence
            if not keep.any():
                return None
            idx = int(np.argmax(np.where(keep, conf, -1.0)))
        else:
            idx = 0
        return dets.xyxy[idx].astype(np.float32)

    def _ball_at_rim(
        self,
        ball: Optional[sv.Detections],
        rims: Optional[sv.Detections],
        H: Optional[np.ndarray],
        frame_width: int,
    ) -> Tuple[bool, Optional[str]]:
        """¿Está el balón en la vecindad de algún aro? Devuelve (bool, lado)."""
        if ball is None or len(ball) == 0 or rims is None or len(rims) == 0:
            return False, None
        b = ball.xyxy[0]
        bc = np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0], dtype=np.float32)

        best_norm = np.inf
        best_side: Optional[str] = None
        rconf = rims.confidence
        for i in range(len(rims)):
            if rconf is not None and float(rconf[i]) < self._s.rim_min_confidence:
                continue
            r = rims.xyxy[i]
            rc = np.array([(r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0], dtype=np.float32)
            rh = max(float(r[3] - r[1]), 1.0)
            norm = float(np.hypot(bc[0] - rc[0], bc[1] - rc[1])) / rh
            if norm < best_norm:
                best_norm = norm
                best_side = self._side_from_point(float(rc[0]), float(rc[1]), H, frame_width)
        if best_norm <= self._s.rim_dist_factor:
            return True, best_side
        return False, None

    def _side_from_box(
        self,
        box: np.ndarray,
        H: Optional[np.ndarray],
        frame_width: int,
    ) -> Optional[str]:
        cx = float((box[0] + box[2]) / 2.0)
        cy = float((box[1] + box[3]) / 2.0)
        return self._side_from_point(cx, cy, H, frame_width)

    def _side_from_point(
        self,
        x: float,
        y: float,
        H: Optional[np.ndarray],
        frame_width: int,
    ) -> Optional[str]:
        if H is not None:
            world = project_image_points(H, np.array([[x, y]], dtype=np.float32))[0]
            return "left" if float(world[0]) < COURT.length_ft / 2.0 else "right"
        if frame_width > 0:
            return "left" if x < frame_width / 2.0 else "right"
        return None

    # ------------------------------------------------------------------
    @property
    def attempts(self) -> int:
        return len(self._events)

    @property
    def makes(self) -> int:
        return sum(1 for e in self._events if e.made)

    @property
    def misses(self) -> int:
        return sum(1 for e in self._events if not e.made)

    def counts_by_team(self) -> Dict[str, Dict[str, int]]:
        """Por color de equipo: ``{team: {"made": x, "missed": y}}``."""
        return {k: dict(v) for k, v in self._by_team.items()}

    def counts_by_side(self) -> Dict[str, Dict[str, int]]:
        """Por lado de la cancha: ``{side: {"made": x, "missed": y}}``."""
        return {k: dict(v) for k, v in self._by_side.items()}

    def events(self) -> List[ShotEvent]:
        return list(self._events)
