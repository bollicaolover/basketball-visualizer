"""Geometría auxiliar para el reconocimiento táctico: canastas y canasta
atacada.

Las dos canastas se leen de la geometría NBA del pipeline
(``vertices_ft()[LEFT_BASKET_INDEX]`` / ``[RIGHT_BASKET_INDEX]``) para que el
sistema de coordenadas coincida exactamente con el de ``players[*].x_ft/y_ft``.
"""

from __future__ import annotations

from typing import Iterable, Literal

import numpy as np

from pipeline.court.geometry import (
    LEFT_BASKET_INDEX,
    RIGHT_BASKET_INDEX,
    vertices_ft,
)

BasketSide = Literal["left", "right"]


def basket_xy(side: BasketSide) -> np.ndarray:
    """Posición (ft) de la canasta izquierda o derecha como (2,) float64."""
    verts = vertices_ft()
    idx = LEFT_BASKET_INDEX if side == "left" else RIGHT_BASKET_INDEX
    return verts[idx].astype(np.float64)


def attacking_basket(offensive_xy: Iterable[np.ndarray]) -> BasketSide:
    """Canasta que ataca el equipo ofensivo.

    En un sistema ofensivo de medio campo los atacantes se sitúan en la pista de
    ataque, cerca del aro que atacan. Se elige por tanto la canasta más próxima
    al centroide de los atacantes. Es el equivalente práctico, en pista completa,
    de la única canasta del modelo de medio campo del artículo.
    """
    pts = [np.asarray(p, dtype=np.float64) for p in offensive_xy]
    if not pts:
        # Sin atacantes no hay forma de decidir; por convenio, izquierda.
        return "left"
    centroid = np.mean(np.stack(pts), axis=0)
    d_left = float(np.linalg.norm(centroid - basket_xy("left")))
    d_right = float(np.linalg.norm(centroid - basket_xy("right")))
    return "left" if d_left <= d_right else "right"


__all__ = ["BasketSide", "basket_xy", "attacking_basket"]
