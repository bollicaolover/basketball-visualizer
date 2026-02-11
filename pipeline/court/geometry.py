"""Geometría oficial de una cancha NBA con la numeración de 33 keypoints
usada por el dataset `basketball-court-detection-2` (Roboflow).

Reproduce la convención de `sports.basketball.CourtConfiguration` para
preset NBA sin depender del paquete `sports`. Las dimensiones internas se
mantienen en centímetros (idénticas al preset original, de modo que los
índices de keypoints coinciden uno a uno con los del modelo entrenado), y
se exponen los vértices en pies como sistema de coordenadas mundial del
pipeline.

Sistema de coordenadas mundial (cancha):
    - Origen en la esquina inferior‑izquierda de la cancha (baseline ‑ sideline).
    - Eje X recorre la longitud de la cancha (banda lateral hacia la opuesta).
    - Eje Y recorre la anchura (de banda inferior a banda superior).
    - Unidades: pies (ft).

Para dibujar este sistema en un canvas de imagen basta con elegir la
escala (px / ft) y aplicar `world_to_canvas` (ver `renderer.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Dimensiones NBA (centímetros, idénticas al preset `sports.basketball`)
# ---------------------------------------------------------------------------
NBA_COURT_LENGTH_CM: int = 2865
NBA_COURT_WIDTH_CM: int = 1524
NBA_THREE_POINT_ARC_RADIUS_CM: int = 724
NBA_STRAIGHT_SECTION_THREE_POINT_LINE_CM: int = 424
NBA_SIDELINE_TO_THREE_POINT_LINE_CM: int = 91
NBA_PAINT_WIDTH_CM: int = 488
NBA_PAINT_LENGTH_CM: int = 579
NBA_FREE_THROW_LINE_DISTANCE_CM: int = 457
NBA_CENTER_CIRCLE_RADIUS_CM: int = 183
NBA_RESTRICTED_AREA_RADIUS_CM: int = 122
NBA_RIM_DIAMETER_CM: int = 46
NBA_BASELINE_TO_RIM_CENTER_CM: int = 160
NBA_BASELINE_TO_THROW_LINE_CM: int = 835

NUM_KEYPOINTS: int = 33
CM_PER_FOOT: float = 30.48


def _raw_vertices_cm() -> List[Tuple[int, int]]:
    """Devuelve los 33 vértices de la cancha NBA en centímetros.

    Reproduce literalmente la función equivalente del preset NBA de
    `sports.basketball.CourtConfiguration`, manteniendo el orden de índices
    con el que está etiquetado el dataset de keypoints.
    """
    cw = NBA_COURT_WIDTH_CM
    cl = NBA_COURT_LENGTH_CM
    tpr = NBA_THREE_POINT_ARC_RADIUS_CM
    sstp = NBA_STRAIGHT_SECTION_THREE_POINT_LINE_CM
    s23 = NBA_SIDELINE_TO_THREE_POINT_LINE_CM
    pw = NBA_PAINT_WIDTH_CM
    pl = NBA_PAINT_LENGTH_CM
    rim = NBA_BASELINE_TO_RIM_CENTER_CM
    throw = NBA_BASELINE_TO_THROW_LINE_CM

    paint_start = (cw - pw) // 2
    middle = cw // 2

    return [
        (0, 0),                              # 00 corner abajo-izda
        (0, s23),                            # 01
        (0, paint_start),                    # 02
        (0, paint_start + pw),               # 03
        (0, cw - s23),                       # 04
        (0, cw),                             # 05 corner arriba-izda
        (rim, middle),                       # 06 aro izquierdo
        (sstp, s23),                         # 07
        (sstp, cw - s23),                    # 08
        (pl, paint_start),                   # 09
        (pl, paint_start + pw // 2),         # 10 free-throw line center (izq)
        (pl, paint_start + pw),              # 11
        (throw, 0),                          # 12
        (rim + tpr, middle),                 # 13 top del arco 3pts (izq)
        (throw, cw),                         # 14
        (cl // 2, 0),                        # 15 mitad cancha, banda abajo
        (cl // 2, middle),                   # 16 centro cancha
        (cl // 2, cw),                       # 17 mitad cancha, banda arriba
        (cl - throw, 0),                     # 18
        (cl - rim - tpr, middle),            # 19 top del arco 3pts (dcha)
        (cl - throw, cw),                    # 20
        (cl - pl, paint_start),              # 21
        (cl - pl, paint_start + pw // 2),    # 22 free-throw line center (dcha)
        (cl - pl, paint_start + pw),         # 23
        (cl - sstp, s23),                    # 24
        (cl - sstp, cw - s23),               # 25
        (cl - rim, middle),                  # 26 aro derecho
        (cl, 0),                             # 27 corner abajo-dcha
        (cl, s23),                           # 28
        (cl, paint_start),                   # 29
        (cl, paint_start + pw),              # 30
        (cl, cw - s23),                      # 31
        (cl, cw),                            # 32 corner arriba-dcha
    ]


def _cm_to_ft(cm: float) -> float:
    """Conversión exacta cm -> pies (sin redondeo)."""
    return float(cm) / CM_PER_FOOT


# Cache lazy de los vértices en pies (no cambian en runtime).
_VERTICES_FT_CACHE: "np.ndarray | None" = None


def vertices_ft() -> np.ndarray:
    """Devuelve los 33 vértices en pies como array (33, 2) float64.

    Orden de los keypoints idéntico al del modelo YOLO entrenado sobre el
    dataset Roboflow `basketball-court-detection-2`.
    """
    global _VERTICES_FT_CACHE
    if _VERTICES_FT_CACHE is None:
        raw = _raw_vertices_cm()
        arr = np.asarray(raw, dtype=np.float64)
        _VERTICES_FT_CACHE = arr / CM_PER_FOOT
    return _VERTICES_FT_CACHE.copy()


def vertices_ft_3d() -> np.ndarray:
    """Devuelve los 33 vértices como array (33, 3) float64 con Z=0.

    La cancha es plana, así que la coordenada mundial Z es siempre 0. Esta
    forma es la que espera ``cv2.solvePnP`` como ``objectPoints``.
    """
    xy = vertices_ft()
    z = np.zeros((xy.shape[0], 1), dtype=xy.dtype)
    return np.hstack([xy, z])


# ---------------------------------------------------------------------------
# Conexiones (líneas rectas) para el render del mapa táctico
# ---------------------------------------------------------------------------
# Sólo se incluyen aristas que de verdad son rectas en la cancha. Las
# curvas (arco de tres puntos, círculo central, área restringida, círculo
# del free throw) se dibujan aparte en el renderer.
EDGES: Tuple[Tuple[int, int], ...] = (
    # Banda lateral izquierda (baseline izquierda)
    (0, 1), (1, 2), (2, 3), (3, 4), (4, 5),
    # Banda inferior (sideline largo de arriba a abajo, izda)
    (0, 12), (12, 15), (15, 18), (18, 27),
    # Banda superior
    (5, 14), (14, 17), (17, 20), (20, 32),
    # Línea central
    (15, 17),
    # Paint izquierdo
    (2, 9), (9, 11), (11, 3),
    # Paint derecho
    (29, 21), (21, 23), (23, 30),
    # Tramo recto del triple (izq + dcha)
    (1, 7), (4, 8),
    (28, 24), (31, 25),
    # Banda lateral derecha
    (27, 28), (28, 29), (29, 30), (30, 31), (31, 32),
    # Free-throw line (cierre del paint)
    (9, 10), (10, 11),
    (21, 22), (22, 23),
)


# ---------------------------------------------------------------------------
# Índices semánticos importantes
# ---------------------------------------------------------------------------
LEFT_BASKET_INDEX: int = 6
RIGHT_BASKET_INDEX: int = 26
CENTER_INDEX: int = 16
LEFT_FREE_THROW_CENTER_INDEX: int = 10
RIGHT_FREE_THROW_CENTER_INDEX: int = 22
COURT_CORNER_INDEXES: Tuple[int, int, int, int] = (0, 5, 32, 27)


@dataclass(frozen=True)
class CourtGeometry:
    """Vista pública y cacheada de la geometría en pies."""

    length_ft: float = _cm_to_ft(NBA_COURT_LENGTH_CM)
    width_ft: float = _cm_to_ft(NBA_COURT_WIDTH_CM)
    paint_width_ft: float = _cm_to_ft(NBA_PAINT_WIDTH_CM)
    paint_length_ft: float = _cm_to_ft(NBA_PAINT_LENGTH_CM)
    three_point_radius_ft: float = _cm_to_ft(NBA_THREE_POINT_ARC_RADIUS_CM)
    straight_section_three_point_ft: float = _cm_to_ft(NBA_STRAIGHT_SECTION_THREE_POINT_LINE_CM)
    sideline_to_three_point_ft: float = _cm_to_ft(NBA_SIDELINE_TO_THREE_POINT_LINE_CM)
    free_throw_line_distance_ft: float = _cm_to_ft(NBA_FREE_THROW_LINE_DISTANCE_CM)
    center_circle_radius_ft: float = _cm_to_ft(NBA_CENTER_CIRCLE_RADIUS_CM)
    restricted_area_radius_ft: float = _cm_to_ft(NBA_RESTRICTED_AREA_RADIUS_CM)
    rim_diameter_ft: float = _cm_to_ft(NBA_RIM_DIAMETER_CM)
    baseline_to_rim_ft: float = _cm_to_ft(NBA_BASELINE_TO_RIM_CENTER_CM)
    baseline_to_throw_line_ft: float = _cm_to_ft(NBA_BASELINE_TO_THROW_LINE_CM)


COURT: CourtGeometry = CourtGeometry()
