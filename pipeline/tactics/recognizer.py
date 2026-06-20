"""Reconocimiento de pantallas (*screens*) a partir de trayectorias de cancha.

Implementa las etapas §4.2 y §5 de Chen et al. 2012 (ver
``docs/tacticas-screen-recognition.md``):

  - Discriminación ataque/defensa (§4.2). El artículo usa la distancia media al
    aro; aquí se prefiere la **posesión** ya resuelta por el pipeline (el equipo
    del poseedor es el atacante) y se cae a la heurística de distancia solo
    cuando no hay poseedor.
  - Detección de pantalla por frame (Algoritmo 2).
  - Clasificación front/back/down por trayectoria (Ec. 9).

El reconocedor consume la salida ya proyectada del pipeline (posiciones en pies
por frame), de modo que no vuelve a ejecutar ningún modelo: es CPU puro y
testeable con trayectorias sintéticas.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from pipeline.config import TacticsSettings
from pipeline.tactics.geometry import BasketSide, attacking_basket, basket_xy
from pipeline.tactics.types import FrameDetection, PlayerSnapshot, ScreenEvent


class FrameTactics:
    """Vista por frame: jugadores en pies + poseedor + equipo atacante."""

    def __init__(
        self,
        frame_index: int,
        players: List[PlayerSnapshot],
        possessor_track_id: Optional[int],
    ) -> None:
        self.frame_index = frame_index
        self.players = players
        self.possessor_track_id = possessor_track_id
        self._by_track: Dict[int, PlayerSnapshot] = {p.track_id: p for p in players}

    def position(self, track_id: int) -> Optional[np.ndarray]:
        snap = self._by_track.get(track_id)
        return None if snap is None else snap.xy


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


class ScreenRecognizer:
    def __init__(self, settings: Optional[TacticsSettings] = None) -> None:
        self._s = settings or TacticsSettings()

    # ------------------------------------------------------------------
    # §4.2 — discriminación ataque / defensa
    # ------------------------------------------------------------------
    def split_teams(
        self, frame: FrameTactics,
    ) -> Optional[Tuple[str, List[PlayerSnapshot], List[PlayerSnapshot], BasketSide]]:
        """Devuelve ``(equipo_atacante, atacantes, defensores, canasta)``.

        ``None`` si no hay dos equipos con jugadores en el frame.
        """
        teams: Dict[str, List[PlayerSnapshot]] = {}
        for p in frame.players:
            if p.team is None:
                continue
            teams.setdefault(p.team, []).append(p)
        if len(teams) < 2:
            return None

        off_team = self._offensive_team(frame, teams)
        if off_team is None:
            return None
        offense = teams[off_team]
        defense = [p for t, ps in teams.items() if t != off_team for p in ps]
        if not offense or not defense:
            return None
        basket = attacking_basket([p.xy for p in offense])
        return off_team, offense, defense, basket

    def _offensive_team(
        self, frame: FrameTactics, teams: Dict[str, List[PlayerSnapshot]],
    ) -> Optional[str]:
        # Señal primaria: el equipo del poseedor es el atacante (RF-DETR clase 5
        # + PossessionResolver). Mucho más fiable que la heurística de distancia.
        pid = frame.possessor_track_id
        if pid is not None:
            for team, players in teams.items():
                if any(p.track_id == pid for p in players):
                    return team

        # Fallback (artículo, §4.2): el equipo cuyos jugadores están de media más
        # lejos de "su" canasta es el atacante. Se evalúa cada equipo contra la
        # canasta más cercana a su centroide.
        best_team: Optional[str] = None
        best_mean = -1.0
        for team, players in teams.items():
            side = attacking_basket([p.xy for p in players])
            bxy = basket_xy(side)
            mean_d = float(np.mean([_dist(p.xy, bxy) for p in players]))
            if mean_d > best_mean:
                best_mean = mean_d
                best_team = team
        return best_team

    # ------------------------------------------------------------------
    # §5.1 — detección de pantalla por frame (Algoritmo 2)
    # ------------------------------------------------------------------
    def detect_frame(
        self, offense: List[PlayerSnapshot], defense: List[PlayerSnapshot],
    ) -> FrameDetection:
        """Algoritmo 2: par de atacantes juntos con un defensor en contacto.

        Devuelve ``(screener_track, screenee_track)`` o ``None``.
        """
        ds = self._s.contact_dist_ft
        Ds = self._s.near_dist_ft

        best: Optional[Tuple[int, int]] = None
        best_gap = float("inf")  # ante varios pares, el más "apretado" gana
        n = len(offense)
        for i in range(n):
            for j in range(i + 1, n):
                pi, pj = offense[i], offense[j]
                d = _dist(pi.xy, pj.xy)
                if not (ds < d < Ds):
                    continue
                # Defensor que (a) contacta (<ds) a uno de los dos y (b) cae ENTRE
                # ambos. (b) es el filtro anti-FP de §5.1 que el Algoritmo 2 omite.
                blocker = self._defender_between(pi.xy, pj.xy, defense, ds)
                if blocker is None:
                    continue
                # El screener es el atacante más cercano al defensor que bloquea
                # (contacta el bloqueo); el screenee es el otro.
                if _dist(blocker.xy, pi.xy) <= _dist(blocker.xy, pj.xy):
                    screener, screenee = pi, pj
                else:
                    screener, screenee = pj, pi
                if d < best_gap:
                    best_gap = d
                    best = (screener.track_id, screenee.track_id)
        return best

    def _defender_between(
        self,
        a: np.ndarray,
        b: np.ndarray,
        defense: List[PlayerSnapshot],
        ds: float,
    ) -> Optional[PlayerSnapshot]:
        """Defensor en contacto (<``ds``) con ``a`` o ``b`` y situado dentro del
        corredor que los une: su proyección sobre el segmento cae en el interior
        (no en los extremos) y su distancia perpendicular es < la semi-anchura del
        carril. Devuelve el más centrado, o ``None`` (§5.1, "defensor entre los
        dos atacantes")."""
        seg = b - a
        L2 = float(seg @ seg)
        if L2 < 1e-9:
            return None
        half = self._s.defender_lane_halfwidth_ft
        best_def: Optional[PlayerSnapshot] = None
        best_perp = float("inf")
        for de in defense:
            if _dist(de.xy, a) >= ds and _dist(de.xy, b) >= ds:
                continue
            t = float((de.xy - a) @ seg) / L2
            if not (0.15 < t < 0.85):  # debe caer claramente entre ambos, no al lado
                continue
            perp = _dist(de.xy, a + t * seg)
            if perp < half and perp < best_perp:
                best_perp = perp
                best_def = de
        return best_def

    # ------------------------------------------------------------------
    # §5 — pasada completa: detección por frame + agregación + clasificación
    # ------------------------------------------------------------------
    def recognize(self, frames: List[FrameTactics]) -> List[ScreenEvent]:
        """Reconoce y clasifica todas las pantallas de una secuencia."""
        detections: List[Tuple[FrameDetection, BasketSide]] = []
        for fr in frames:
            split = self.split_teams(fr)
            if split is None:
                detections.append((None, "left"))
                continue
            _, offense, defense, basket = split
            det = self.detect_frame(offense, defense)
            detections.append((det, basket))

        events: List[ScreenEvent] = []
        for run in self._group_runs(detections):
            event = self._build_event(frames, run)
            if event is not None:
                events.append(event)
        return events

    def _group_runs(
        self,
        detections: List[Tuple[FrameDetection, BasketSide]],
    ) -> List[List[Tuple[int, Tuple[int, int], BasketSide]]]:
        """Agrupa detecciones del **mismo par no ordenado** de atacantes en
        rachas, tolerando huecos de hasta ``max_gap_frames`` (oclusiones).

        Cada elemento de una racha es ``(idx_global, par_ordenado, canasta)``.
        """
        runs: List[List[Tuple[int, Tuple[int, int], BasketSide]]] = []
        active: Dict[frozenset, dict] = {}  # par -> {"run":[...], "last_idx":int}
        max_gap = self._s.max_gap_frames

        for idx, (det, basket) in enumerate(detections):
            # Cierra rachas cuyo hueco ya supera el máximo.
            for key in list(active.keys()):
                if idx - active[key]["last_idx"] > max_gap:
                    runs.append(active.pop(key)["run"])
            if det is None:
                continue
            key = frozenset(det)
            entry = active.get(key)
            if entry is None:
                active[key] = {"run": [(idx, det, basket)], "last_idx": idx}
            else:
                entry["run"].append((idx, det, basket))
                entry["last_idx"] = idx

        runs.extend(entry["run"] for entry in active.values())
        return runs

    def _build_event(
        self,
        frames: List[FrameTactics],
        run: List[Tuple[int, Tuple[int, int], BasketSide]],
    ) -> Optional[ScreenEvent]:
        if len(run) < self._s.min_event_frames:
            return None

        # Roles: el screener/screenee puede alternar entre frames; se decide por
        # el voto mayoritario del par ordenado a lo largo de la racha.
        order_votes: Dict[Tuple[int, int], int] = {}
        for _, det, _ in run:
            order_votes[det] = order_votes.get(det, 0) + 1
        screener_track, screenee_track = max(order_votes, key=order_votes.get)

        first_idx = run[0][0]
        last_idx = run[-1][0]
        start_fr = frames[first_idx]
        end_fr = frames[last_idx]

        # "Bloqueo puesto" = frame de máxima proximidad entre los dos atacantes
        # (contacto del screen). Es el ``p_screen`` del artículo.
        screen_idx = first_idx
        screen_basket = run[0][2]
        best_gap = float("inf")
        for idx, _, basket in run:
            a = frames[idx].position(screener_track)
            b = frames[idx].position(screenee_track)
            if a is None or b is None:
                continue
            gap = _dist(a, b)
            if gap < best_gap:
                best_gap = gap
                screen_idx = idx
                screen_basket = basket
        screen_fr = frames[screen_idx]

        # ``p_init`` desde el lead-in (screener aproximándose) y ``p_last`` desde
        # el lag-out (screenee completando el corte). Ver Ec. 9.
        sc_init = self._lookback(frames, first_idx, self._s.lead_in_frames, screener_track)
        se_init = self._lookback(frames, first_idx, self._s.lead_in_frames, screenee_track)
        sc_last = self._lookahead(frames, last_idx, self._s.lag_out_frames, screener_track)
        se_last = self._lookahead(frames, last_idx, self._s.lag_out_frames, screenee_track)
        sc_screen = screen_fr.position(screener_track)
        se_screen = screen_fr.position(screenee_track)
        if any(v is None for v in (sc_init, sc_screen, sc_last, se_init, se_screen, se_last)):
            return None

        screen_type = self._classify(
            screen_basket, sc_init, sc_screen, se_screen, se_last,
        )
        team = self._team_of(start_fr, screener_track)
        return ScreenEvent(
            screener_track=screener_track,
            screenee_track=screenee_track,
            team=team,
            screen_type=screen_type,
            basket=screen_basket,
            start_frame=start_fr.frame_index,
            screen_frame=screen_fr.frame_index,
            end_frame=end_fr.frame_index,
            screener_init=(float(sc_init[0]), float(sc_init[1])),
            screener_screen=(float(sc_screen[0]), float(sc_screen[1])),
            screener_last=(float(sc_last[0]), float(sc_last[1])),
            screenee_init=(float(se_init[0]), float(se_init[1])),
            screenee_screen=(float(se_screen[0]), float(se_screen[1])),
            screenee_last=(float(se_last[0]), float(se_last[1])),
        )

    @staticmethod
    def _lookback(
        frames: List[FrameTactics], idx: int, window: int, track_id: int,
    ) -> Optional[np.ndarray]:
        """Posición del track en el frame más antiguo dentro de
        ``[idx-window, idx]`` en que aparece (captura su aproximación)."""
        start = max(0, idx - window)
        for i in range(start, idx + 1):
            pos = frames[i].position(track_id)
            if pos is not None:
                return pos
        return None

    @staticmethod
    def _lookahead(
        frames: List[FrameTactics], idx: int, window: int, track_id: int,
    ) -> Optional[np.ndarray]:
        """Posición del track en el frame más reciente dentro de
        ``[idx, idx+window]`` en que aparece (captura el final del corte)."""
        end = min(len(frames) - 1, idx + window)
        for i in range(end, idx - 1, -1):
            pos = frames[i].position(track_id)
            if pos is not None:
                return pos
        return None

    @staticmethod
    def _team_of(frame: FrameTactics, track_id: int) -> Optional[str]:
        snap = frame._by_track.get(track_id)
        return None if snap is None else snap.team

    # ------------------------------------------------------------------
    # Ec. 9 — clasificación de la pantalla
    # ------------------------------------------------------------------
    def _classify(
        self,
        basket: BasketSide,
        screener_init: np.ndarray,
        screener_screen: np.ndarray,
        screenee_screen: np.ndarray,
        screenee_last: np.ndarray,
    ) -> str:
        pbasket = basket_xy(basket)
        # Down-screen: el screener baja hacia el aro al poner el bloqueo, es
        # decir, está más cerca del aro al fijarlo que al empezar. Se exige un
        # acercamiento mínimo (no una deriva cualquiera) para no etiquetar como
        # down un front/back con leve drift al aro (Fig. 18a del artículo).
        approach = _dist(pbasket, screener_init) - _dist(pbasket, screener_screen)
        if approach > self._s.down_approach_margin_ft:
            return "down"

        # Back vs Front según el corte del screenee respecto a la canasta.
        d_moving = screenee_last - screenee_screen
        d_basket = pbasket - screenee_screen
        nm = float(np.linalg.norm(d_moving))
        nb = float(np.linalg.norm(d_basket))
        if nm < 1e-6 or nb < 1e-6:
            return "undefined"
        cos = float(np.clip(np.dot(d_moving, d_basket) / (nm * nb), -1.0, 1.0))
        angle_deg = math.degrees(math.acos(cos))
        if angle_deg < self._s.back_front_angle_deg:
            return "back"   # el screenee corta hacia la canasta
        return "front"      # el screenee sale a espacio abierto


__all__ = ["FrameTactics", "ScreenRecognizer"]
