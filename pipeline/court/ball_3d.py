"""Reconstrucción de la trayectoria 3D del balón (método de física, Pirotta 5.2).

Una sola cámara no permite recuperar la profundidad de un punto aislado: la
ecuación de proyección ``λ·m = P·W`` (eq. 5.1) tiene la P de 3x4 no invertible.
Pirotta lo resuelve imponiendo que, durante un tiro, el balón sigue un **movimiento
balístico** conocido (eq. 5.3):

    X(t) = X0 + Vx·t
    Y(t) = Y0 + Vy·t
    Z(t) = Z0 + Vz·t − ½·g·t²

Con esto, cada detección 2D ``(xₜ, yₜ)`` en el instante ``t`` y la matriz de
proyección calibrada ``Pₜ`` aportan dos ecuaciones lineales en las 6 incógnitas
``B = (X0, Vx, Y0, Vy, Z0, Vz)`` (eq. 5.6). Con N≥3 detecciones el sistema queda
sobredeterminado y se resuelve por mínimos cuadrados (DLT).

Unidades: el mundo está en **pies** (modelo de cancha de ``geometry.vertices_ft``),
así que ``g = 32.174 ft/s²`` y ``t`` en segundos; las posiciones salen en pies.
La cota de validación natural es el aro: **10 ft** de altura.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

# Aceleración de la gravedad en pies/s² (mundo de cancha en pies).
GRAVITY_FT_S2: float = 32.174
# Altura del aro NBA en pies (referencia de validación física).
RIM_HEIGHT_FT: float = 10.0
# Conversión a metros (el solver trabaja en pies; las salidas se muestran en m).
FT_TO_M: float = 0.3048
RIM_HEIGHT_M: float = RIM_HEIGHT_FT * FT_TO_M   # 3.05 m


@dataclass
class Trajectory3D:
    """Resultado de la reconstrucción balística de un tiro."""

    params: np.ndarray          # [X0, Vx, Y0, Vy, Z0, Vz] (pies, pies/s)
    times: np.ndarray           # (N,) instantes de las detecciones (s)
    points_3d: np.ndarray       # (N, 3) posición 3D reconstruida en cada t (pies)
    reproj_rmse_px: float       # RMSE al reproyectar los puntos 3D a imagen
    gravity: float              # g empleada (pies/s²)
    oriented: bool = False      # True si se negó la 3ª col. de P (Z→arriba)

    # --- Métricas derivadas del arco ---
    def position(self, t: float) -> np.ndarray:
        x0, vx, y0, vy, z0, vz = self.params
        return np.array(
            [x0 + vx * t, y0 + vy * t, z0 + vz * t - 0.5 * self.gravity * t * t],
            dtype=np.float64,
        )

    @property
    def release_point_ft(self) -> np.ndarray:
        """Posición (X, Y) en pista en el primer instante observado."""
        return self.points_3d[0, :2].copy()

    @property
    def launch_speed_fps(self) -> float:
        _, vx, _, vy, _, vz = self.params
        return float(np.sqrt(vx * vx + vy * vy + vz * vz))

    @property
    def launch_angle_deg(self) -> float:
        """Ángulo de salida respecto a la horizontal en el primer instante."""
        _, vx, _, vy, _, vz = self.params
        horiz = float(np.hypot(vx, vy))
        return float(np.degrees(np.arctan2(vz, horiz)))

    @property
    def apex_time_s(self) -> float:
        """Instante del punto más alto (vértice de la parábola en Z)."""
        _, _, _, _, _, vz = self.params
        return float(vz / self.gravity) if self.gravity > 0 else 0.0

    @property
    def apex_height_ft(self) -> float:
        _, _, _, _, z0, vz = self.params
        if vz <= 0 or self.gravity <= 0:
            return float(self.points_3d[:, 2].max())
        return float(z0 + vz * vz / (2.0 * self.gravity))

    def times_at_height(self, z_ft: float) -> list[float]:
        """Instantes en los que ``Z(t)`` alcanza ``z_ft`` (0, 1 o 2 raíces reales)."""
        _, _, _, _, z0, vz = self.params
        g = self.gravity
        if g <= 0:
            return []
        disc = vz * vz + 2.0 * g * (z0 - z_ft)
        if disc < -1e-9:
            return []
        disc = max(0.0, disc)
        s = float(np.sqrt(disc))
        return [(vz - s) / g, (vz + s) / g]

    def extrapolation_end(self, after_t: float | None = None) -> tuple[float, str]:
        """Hasta cuándo extrapolar el arco tras las observaciones.

        Devuelve ``(t_end, motivo)`` con ``motivo`` en ``{"rim", "floor", "observed"}``.
        Tras ``after_t``, el primer evento es el cruce de la altura del aro en
        bajada o, si no aplica, el impacto en el suelo (Z=0).
        """
        after_t = float(self.times[-1]) if after_t is None else float(after_t)
        apex = self.apex_time_s
        hits: list[tuple[float, str]] = []
        for z_ft, label in ((RIM_HEIGHT_FT, "rim"), (0.0, "floor")):
            for t in self.times_at_height(z_ft):
                if t > max(after_t, apex) + 1e-9:
                    hits.append((t, label))
        if hits:
            t_end, label = min(hits, key=lambda x: x[0])
            return t_end, label
        for t in self.times_at_height(0.0):
            if t > after_t + 1e-9:
                return t, "floor"
        return after_t, "observed"


def _project(P: np.ndarray, world_xyz: np.ndarray) -> np.ndarray:
    """Proyecta un punto mundo (pies) a imagen (px) con la matriz P de 3x4."""
    w = np.array([world_xyz[0], world_xyz[1], world_xyz[2], 1.0], dtype=np.float64)
    uvw = P @ w
    if abs(uvw[2]) < 1e-9:
        return np.array([np.nan, np.nan])
    return uvw[:2] / uvw[2]


def _camera_center_z(P: np.ndarray) -> float:
    """Coordenada Z (mundo) del centro óptico de la cámara: C = −M⁻¹·p₄."""
    M, p4 = P[:, :3], P[:, 3]
    try:
        return float(-np.linalg.solve(M, p4)[2])
    except np.linalg.LinAlgError:
        return 0.0


def _orient_projections_z_up(projections: list) -> tuple[list, bool]:
    """Garantiza un marco con Z hacia arriba (cancha en Z=0, balón en Z>0).

    El PnP planar tiene una ambigüedad de signo en la normal: a menudo recupera
    una pose con +Z hacia el suelo (cámara en grada ⇒ centro óptico en Z<0). Si
    se detecta ese caso, se niega la 3ª columna de P (equivale a redefinir
    Z' = −Z), de modo que aguas abajo la gravedad estándar (−½g) y las métricas
    de altura tengan el signo correcto sin depender del clip."""
    z_cam = np.median([_camera_center_z(P) for P in projections])
    if z_cam < 0:
        flipped = []
        for P in projections:
            Pf = P.copy()
            Pf[:, 2] *= -1.0
            flipped.append(Pf)
        return flipped, True
    return projections, False


def solve_ballistic_trajectory(
    projections: Sequence[np.ndarray],
    image_points: np.ndarray,
    times: Sequence[float],
    gravity: float = GRAVITY_FT_S2,
    auto_orient: bool = True,
) -> Trajectory3D:
    """Resuelve la trayectoria 3D del balón a partir de detecciones 2D calibradas.

    Args:
        projections: N matrices de proyección 3x4 (una por detección; la pose de
            la cámara puede variar entre frames).
        image_points: (N, 2) centros del balón en imagen (px).
        times: N instantes en segundos (un origen arbitrario común es válido).
        gravity: aceleración de la gravedad en las unidades del mundo (pies/s²).
        auto_orient: si True, corrige la ambigüedad de signo de la normal del
            PnP planar para trabajar siempre con Z hacia arriba (recomendado).

    Returns:
        :class:`Trajectory3D` con los parámetros balísticos y métricas del arco.
        ``points_3d[:, 2]`` es la altura sobre la cancha (pies, Z hacia arriba).

    Raises:
        ValueError: si hay menos de 3 detecciones o las dimensiones no cuadran.
    """
    uv = np.asarray(image_points, dtype=np.float64)
    t = np.asarray(times, dtype=np.float64)
    n = uv.shape[0]
    if n < 3:
        raise ValueError(f"se requieren ≥3 detecciones para 6 incógnitas (hay {n})")
    if len(projections) != n or t.shape[0] != n:
        raise ValueError("projections, image_points y times deben tener igual longitud")

    proj = [np.asarray(P, dtype=np.float64) for P in projections]
    oriented = False
    if auto_orient:
        proj, oriented = _orient_projections_z_up(proj)
    projections = proj

    # Sistema M_A · B = M_C (2N x 6). Para cada detección, con
    # a = P1 − x·P3 y b = P2 − y·P3 (filas de P), la restricción de proyección
    # a·W = 0 y b·W = 0 se vuelve lineal en B al sustituir el modelo balístico.
    A = np.zeros((2 * n, 6), dtype=np.float64)
    c = np.zeros(2 * n, dtype=np.float64)
    for i in range(n):
        P = np.asarray(projections[i], dtype=np.float64)
        if P.shape != (3, 4):
            raise ValueError(f"projection[{i}] debe ser 3x4, es {P.shape}")
        x, y = uv[i]
        ti = t[i]
        g_t = -0.5 * gravity * ti * ti  # desplazamiento conocido de Z por gravedad
        a = P[0] - x * P[2]             # [a1, a2, a3, a4]
        b = P[1] - y * P[2]             # [b1, b2, b3, b4]
        # Coeficientes de B = [X0, Vx, Y0, Vy, Z0, Vz].
        A[2 * i] = [a[0], a[0] * ti, a[1], a[1] * ti, a[2], a[2] * ti]
        c[2 * i] = -(a[2] * g_t + a[3])
        A[2 * i + 1] = [b[0], b[0] * ti, b[1], b[1] * ti, b[2], b[2] * ti]
        c[2 * i + 1] = -(b[2] * g_t + b[3])

    params, _, _, _ = np.linalg.lstsq(A, c, rcond=None)

    x0, vx, y0, vy, z0, vz = params
    pts = np.column_stack(
        [
            x0 + vx * t,
            y0 + vy * t,
            z0 + vz * t - 0.5 * gravity * t * t,
        ]
    )

    # Error de reproyección: vuelve a proyectar los puntos 3D y compara con la
    # medición 2D. Es la prueba de consistencia del ajuste (redundante a la
    # validación del cap. 4).
    sq = 0.0
    for i in range(n):
        pred = _project(np.asarray(projections[i], dtype=np.float64), pts[i])
        if np.all(np.isfinite(pred)):
            sq += float(np.sum((pred - uv[i]) ** 2))
    reproj_rmse = float(np.sqrt(sq / n))

    return Trajectory3D(
        params=params,
        times=t,
        points_3d=pts,
        reproj_rmse_px=reproj_rmse,
        gravity=gravity,
        oriented=oriented,
    )
