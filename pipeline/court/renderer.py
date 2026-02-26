"""Render de la cancha NBA en vista cenital usando OpenCV.

Dibuja una cancha "limpia" desde la geometría definida en
`pipeline.court.geometry` (sin depender de paquetes externos). El
fondo se cachea entre frames porque sólo cambian las posiciones de los
jugadores y el balón.

Sistema de coordenadas:
    - El render recibe posiciones en el sistema mundial (pies) y las
      transforma a píxeles con `world_to_canvas`.
    - El canvas tiene un padding configurable alrededor de la cancha
      para que las anotaciones cercanas a la banda no queden cortadas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Tuple

import cv2
import numpy as np

from pipeline.config import RenderSettings
from pipeline.court.geometry import (
    COURT,
    COURT_CORNER_INDEXES,
    EDGES,
    LEFT_BASKET_INDEX,
    LEFT_FREE_THROW_CENTER_INDEX,
    RIGHT_BASKET_INDEX,
    RIGHT_FREE_THROW_CENTER_INDEX,
    vertices_ft,
)


@dataclass
class PlayerDot:
    xy_ft: Tuple[float, float]
    team: Optional[str]              # "white" | "dark" | None
    track_id: Optional[int] = None
    is_possessor: bool = False
    number: Optional[int] = None     # dorsal reconocido (0-99), si lo hay


class CourtRenderer:
    """Dibuja la cancha y superpone jugadores / balón."""

    def __init__(self, settings: RenderSettings) -> None:
        self._s = settings
        self._scale: float = self._compute_scale()
        self._origin_px: Tuple[float, float] = (
            self._s.padding_ft * self._scale,
            self._s.padding_ft * self._scale,
        )
        self._background: np.ndarray = self._render_background()

    # ---------------------------------------------------------------
    # Transformación mundo (pies) -> canvas (píxeles)
    # ---------------------------------------------------------------
    def _compute_scale(self) -> float:
        """Calcula los px/ft de modo que la cancha quepa en el canvas
        manteniendo proporción y respetando el padding."""
        usable_w = self._s.map_width_px - 2 * self._s.padding_ft * 1.0
        usable_h = self._s.map_height_px - 2 * self._s.padding_ft * 1.0
        # En pies, la cancha mide length x width; el render orienta la
        # longitud horizontalmente.
        scale_x = self._s.map_width_px / (COURT.length_ft + 2 * self._s.padding_ft)
        scale_y = self._s.map_height_px / (COURT.width_ft + 2 * self._s.padding_ft)
        return float(min(scale_x, scale_y))

    def world_to_canvas(self, xy_ft: Iterable[float]) -> Tuple[int, int]:
        x_ft, y_ft = float(xy_ft[0]), float(xy_ft[1])
        px = self._origin_px[0] + x_ft * self._scale
        py = self._origin_px[1] + y_ft * self._scale
        return int(round(px)), int(round(py))

    # ---------------------------------------------------------------
    # Render del fondo (cacheado, sólo se calcula una vez)
    # ---------------------------------------------------------------
    def _render_background(self) -> np.ndarray:
        s = self._s
        canvas = np.full(
            (s.map_height_px, s.map_width_px, 3),
            fill_value=s.background_bgr,
            dtype=np.uint8,
        )
        verts = vertices_ft()
        verts_px = np.array([self.world_to_canvas(v) for v in verts], dtype=np.int32)

        self._fill_court_surfaces(canvas, verts)
        self._draw_floor_planks(canvas, verts)

        line_color = s.line_bgr
        t = s.line_thickness
        line_aa = cv2.LINE_AA

        # Aristas rectas
        for i, j in EDGES:
            cv2.line(canvas, tuple(verts_px[i]), tuple(verts_px[j]), line_color, t, line_aa)

        # Arco de 3 puntos izquierdo / derecho
        self._draw_three_point_arc(canvas, side="left", color=line_color, thickness=t)
        self._draw_three_point_arc(canvas, side="right", color=line_color, thickness=t)

        # Círculo central
        center_px = self.world_to_canvas(verts[16])
        cv2.circle(
            canvas, center_px,
            radius=int(round(COURT.center_circle_radius_ft * self._scale)),
            color=line_color, thickness=t, lineType=line_aa,
        )

        # Free-throw circles (los dos)
        left_ft_px = self.world_to_canvas(verts[LEFT_FREE_THROW_CENTER_INDEX])
        right_ft_px = self.world_to_canvas(verts[RIGHT_FREE_THROW_CENTER_INDEX])
        ft_radius_px = int(round((COURT.paint_width_ft / 2) * self._scale))
        cv2.circle(canvas, left_ft_px, ft_radius_px, line_color, t, line_aa)
        cv2.circle(canvas, right_ft_px, ft_radius_px, line_color, t, line_aa)

        # Aros (pequeños círculos rellenos)
        rim_radius_px = max(2, int(round((COURT.rim_diameter_ft / 2) * self._scale)))
        rim_color = s.rim_bgr
        cv2.circle(canvas, self.world_to_canvas(verts[LEFT_BASKET_INDEX]),
                   rim_radius_px, rim_color, thickness=-1, lineType=line_aa)
        cv2.circle(canvas, self.world_to_canvas(verts[RIGHT_BASKET_INDEX]),
                   rim_radius_px, rim_color, thickness=-1, lineType=line_aa)

        # Restricted area (semicírculo bajo el aro)
        self._draw_restricted_area(canvas, side="left", color=line_color, thickness=t)
        self._draw_restricted_area(canvas, side="right", color=line_color, thickness=t)

        return canvas

    def _fill_court_surfaces(self, canvas: np.ndarray, verts: np.ndarray) -> None:
        """Rellena el parquet y las zonas pintadas antes de dibujar las líneas."""
        s = self._s
        court_poly = np.array(
            [
                self.world_to_canvas(verts[i])
                for i in COURT_CORNER_INDEXES
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(canvas, [court_poly], s.floor_bgr)

        left_key = np.array(
            [
                self.world_to_canvas(verts[2]),
                self.world_to_canvas(verts[3]),
                self.world_to_canvas(verts[11]),
                self.world_to_canvas(verts[9]),
            ],
            dtype=np.int32,
        )
        right_key = np.array(
            [
                self.world_to_canvas(verts[29]),
                self.world_to_canvas(verts[30]),
                self.world_to_canvas(verts[23]),
                self.world_to_canvas(verts[21]),
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(canvas, [left_key, right_key], s.key_bgr)

    def _draw_floor_planks(self, canvas: np.ndarray, verts: np.ndarray) -> None:
        """Vetas sutiles de parquet paralelas a las bandas laterales."""
        spacing = self._s.floor_plank_spacing_px
        if spacing <= 0:
            return

        corners = [self.world_to_canvas(verts[i]) for i in COURT_CORNER_INDEXES]
        xs = [p[0] for p in corners]
        ys = [p[1] for p in corners]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        shade = self._s.floor_plank_shade_bgr
        for x in range(x_min + spacing, x_max, spacing):
            cv2.line(
                canvas, (x, y_min), (x, y_max),
                shade, 1, cv2.LINE_AA,
            )

    def _draw_three_point_arc(self, canvas: np.ndarray, side: str, color, thickness: int) -> None:
        verts = vertices_ft()
        if side == "left":
            rim_world = verts[LEFT_BASKET_INDEX]
            corner_low = verts[7]
            corner_high = verts[8]
            top_arc = verts[13]
        else:
            rim_world = verts[RIGHT_BASKET_INDEX]
            corner_low = verts[24]
            corner_high = verts[25]
            top_arc = verts[19]

        center_px = self.world_to_canvas(rim_world)
        radius_px = int(round(COURT.three_point_radius_ft * self._scale))

        # Ángulos en grados (0..360, CCW en el sistema canvas, donde y crece
        # hacia abajo). cv2.ellipse barre desde startAngle hasta endAngle
        # asumiendo end > start, así que necesitamos elegir qué semicírculo
        # cubre realmente el "top" del arco de tres puntos (el punto 13 / 19).
        def _angle_deg(target_world) -> float:
            t_px = np.array(self.world_to_canvas(target_world), dtype=np.float64)
            ang = math.degrees(math.atan2(t_px[1] - center_px[1], t_px[0] - center_px[0]))
            return ang % 360.0

        ang_low = _angle_deg(corner_low)
        ang_high = _angle_deg(corner_high)
        ang_top = _angle_deg(top_arc)

        a, b = sorted([ang_low, ang_high])
        # Determinamos si el "top" del arco está en el barrido corto [a, b]
        # o en su complemento; usamos el que contenga al top.
        if a <= ang_top <= b:
            start, end = a, b
        else:
            start, end = b, a + 360.0

        cv2.ellipse(
            canvas, center_px, (radius_px, radius_px),
            angle=0, startAngle=start, endAngle=end,
            color=color, thickness=thickness, lineType=cv2.LINE_AA,
        )

    def _draw_restricted_area(self, canvas: np.ndarray, side: str, color, thickness: int) -> None:
        verts = vertices_ft()
        if side == "left":
            rim_world = verts[LEFT_BASKET_INDEX]
            sweep_dir = +1
        else:
            rim_world = verts[RIGHT_BASKET_INDEX]
            sweep_dir = -1

        center_px = self.world_to_canvas(rim_world)
        radius_px = int(round(COURT.restricted_area_radius_ft * self._scale))

        # Semicírculo de 180º orientado hacia el centro de la cancha.
        if sweep_dir == +1:   # mirando hacia +X (izquierda → mitad)
            start, end = -90, 90
        else:
            start, end = 90, 270
        cv2.ellipse(
            canvas, center_px, (radius_px, radius_px),
            angle=0, startAngle=start, endAngle=end,
            color=color, thickness=thickness, lineType=cv2.LINE_AA,
        )

    # ---------------------------------------------------------------
    # Render por frame
    # ---------------------------------------------------------------
    def draw(
        self,
        players: Iterable[PlayerDot],
        possessor_xy_ft: Optional[Tuple[float, float]] = None,
        basket_side: Optional[Literal["left", "right"]] = None,
        basket_made: Optional[bool] = None,
    ) -> np.ndarray:
        canvas = self._background.copy()
        s = self._s

        if basket_side is not None:
            self._draw_basket_highlight(canvas, basket_side, bool(basket_made))

        for p in players:
            color = self._team_color(p.team)
            xy = self.world_to_canvas(p.xy_ft)
            if p.is_possessor:
                cv2.circle(
                    canvas, xy,
                    s.player_radius_px + 5,
                    s.possessor_ring_bgr,
                    thickness=s.possessor_ring_thickness,
                )
            cv2.circle(canvas, xy, s.player_radius_px, color, thickness=-1)
            cv2.circle(canvas, xy, s.player_radius_px, s.player_outline_bgr, thickness=1)
            self._draw_player_label(canvas, xy, p)

        if possessor_xy_ft is not None:
            ball_xy = self.world_to_canvas(possessor_xy_ft)
            cv2.circle(
                canvas, ball_xy,
                s.possession_ball_radius_px,
                s.possession_ball_bgr,
                thickness=-1,
            )
            cv2.circle(
                canvas, ball_xy,
                s.possession_ball_radius_px,
                s.player_outline_bgr,
                thickness=1,
            )

        return canvas

    def _draw_player_label(
        self,
        canvas: np.ndarray,
        xy: Tuple[int, int],
        p: PlayerDot,
    ) -> None:
        """Dibuja el dorsal centrado en el punto; si no hay, el track_id al lado."""
        s = self._s
        if p.number is not None:
            txt = str(int(p.number))
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            org = (xy[0] - tw // 2, xy[1] + th // 2)
            cv2.putText(canvas, txt, org, cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                        s.player_outline_bgr, 3, cv2.LINE_AA)
            cv2.putText(canvas, txt, org, cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                        (255, 255, 255), 1, cv2.LINE_AA)
        elif p.track_id is not None:
            cv2.putText(canvas, str(int(p.track_id)),
                        (xy[0] + s.player_radius_px + 2, xy[1] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        s.player_outline_bgr, 1, cv2.LINE_AA)

    def _draw_basket_highlight(
        self,
        canvas: np.ndarray,
        side: Literal["left", "right"],
        made: bool,
    ) -> None:
        s = self._s
        color = s.made_rim_highlight_bgr if made else s.missed_rim_highlight_bgr
        label = s.made_label if made else s.missed_label
        verts = vertices_ft()
        rim_idx = LEFT_BASKET_INDEX if side == "left" else RIGHT_BASKET_INDEX
        rim_px = self.world_to_canvas(verts[rim_idx])
        cv2.circle(
            canvas, rim_px,
            s.score_rim_highlight_radius_px,
            color,
            thickness=-1,
        )
        (tw, th), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2,
        )
        tx = rim_px[0] - tw // 2
        ty = max(th + 8, rim_px[1] - s.score_rim_highlight_radius_px - 8)
        cv2.putText(
            canvas, label, (tx, ty),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            color, 2, cv2.LINE_AA,
        )

    def _team_color(self, team: Optional[str]) -> Tuple[int, int, int]:
        if team == "white":
            return self._s.team_white_fill_bgr
        if team == "dark":
            return self._s.team_dark_fill_bgr
        return self._s.team_unknown_fill_bgr

    # ---------------------------------------------------------------
    @property
    def canvas_size(self) -> Tuple[int, int]:
        return self._s.map_width_px, self._s.map_height_px

    def export_court_png(self, path: str) -> None:
        """Exporta la cancha vacía (sin jugadores) como imagen PNG."""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        cv2.imwrite(path, self.draw([], None, None))
        print(f"[INFO] Cancha PNG:        {path}")
