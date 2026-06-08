"""Clasificación de equipos sin etiquetas (SigLIP + UMAP + K-means).

Envuelve `sports.TeamClassifier` (el mismo del cuaderno): se calibra una vez con
recortes centrales de jugador y luego asigna `team_id ∈ {0, 1}` por recorte. El
voto temporal (`ConsecutiveValueTracker`) fija el equipo por `track_id`, de modo
que el color/equipo es estable durante todo el clip.

SigLIP se descarga una sola vez de Hugging Face y corre local: no hay API en
runtime.
"""

from __future__ import annotations

import contextlib
import os
import warnings
from typing import List, Optional

import numpy as np
import supervision as sv

from pipeline.config import TeamSettings
from pipeline.tracking.types import TrackedEntity


class TeamClassifier:
    def __init__(self, settings: TeamSettings) -> None:
        from sports import ConsecutiveValueTracker
        from sports import TeamClassifier as SportsTeamClassifier

        self._s = settings
        self._tc = SportsTeamClassifier(device=settings.device)
        self._fitted = False
        self._votes = ConsecutiveValueTracker(n_consecutive=settings.votes_to_lock)
        # Cluster (0/1) correspondiente al equipo de camiseta clara. K-means
        # asigna el índice de cluster de forma arbitraria, así que tras `fit`
        # se orienta por luminancia para que 'white'/team_names[0] sea siempre
        # el equipo más claro (None = sin orientar → identidad).
        self._white_cluster: Optional[int] = None
        self._cluster_color: dict = {}   # cluster crudo → color medio BGR de camiseta

    @property
    def fitted(self) -> bool:
        return self._fitted

    # ------------------------------------------------------------------
    # Tamaño mínimo en píxeles (ancho y alto) para que el recorte sea útil para SigLIP.
    _MIN_CROP_PX: int = 16

    def _crop(self, frame_bgr: np.ndarray, box_xyxy: np.ndarray) -> np.ndarray:
        """Recorte central (factor `crop_scale`) — realza la camiseta."""
        scaled = sv.scale_boxes(np.asarray([box_xyxy], dtype=np.float32), factor=self._s.crop_scale)[0]
        crop = sv.crop_image(frame_bgr, scaled)
        if crop.shape[0] < self._MIN_CROP_PX or crop.shape[1] < self._MIN_CROP_PX:
            return np.empty((0,), dtype=np.uint8)
        return crop

    def collect_crops(self, frame_bgr: np.ndarray, entities: List[TrackedEntity]) -> List[np.ndarray]:
        crops = []
        for e in entities:
            c = self._crop(frame_bgr, e.bbox_xyxy)
            if c.size > 0:
                crops.append(c)
        return crops

    def fit(self, crops: List[np.ndarray]) -> None:
        if not crops:
            return
        with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull), \
                warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Kwargs passed to")
            warnings.filterwarnings("ignore", message="The channel dimension is ambiguous")
            self._tc.fit(crops)
        self._fitted = True
        self._orient_by_brightness(crops)

    def _orient_by_brightness(self, crops: List[np.ndarray]) -> None:
        """Fija qué cluster es el de camiseta clara comparando la luminancia
        media de los recortes. Hace determinista el mapeo cluster→'white'/'dark'
        (el más claro → 'white'), en vez de depender del índice de K-means."""
        if not self._fitted or not crops:
            return
        with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull), \
                warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Kwargs passed to")
            warnings.filterwarnings("ignore", message="The channel dimension is ambiguous")
            preds = self._tc.predict(crops)
        sums: dict = {}
        counts: dict = {}
        colsums: dict = {}   # tid -> np.array([B, G, R]) acumulado
        for crop, t in zip(crops, preds):
            tid = int(t)
            sums[tid] = sums.get(tid, 0.0) + float(crop.mean())
            counts[tid] = counts.get(tid, 0) + 1
            chan = crop.reshape(-1, 3).mean(axis=0)  # color medio BGR del recorte
            colsums[tid] = colsums.get(tid, np.zeros(3)) + chan
        means = {tid: sums[tid] / counts[tid] for tid in sums if counts[tid]}
        # Color medio de camiseta por cluster (BGR), para emparejar con el roster.
        self._cluster_color = {
            tid: (colsums[tid] / counts[tid]) for tid in colsums if counts[tid]
        }
        if len(means) < 2:
            return
        self._white_cluster = max(means, key=means.get)
        print(f"[INFO] equipos orientados por brillo: cluster {self._white_cluster} "
              f"= camiseta clara (luminancia {means})", flush=True)

    def _semantic_id(self, raw_tid: int) -> int:
        """Cluster crudo de K-means → índice semántico (0=clara, 1=oscura)."""
        if self._white_cluster is None:
            return raw_tid
        return 0 if raw_tid == self._white_cluster else 1

    def _raw_for_semantic(self, sid: int) -> int:
        """Índice semántico (0=clara, 1=oscura) → cluster crudo de K-means."""
        if self._white_cluster is None:
            return sid
        return self._white_cluster if sid == 0 else (1 - self._white_cluster)

    def semantic_mean_color(self, sid: int):
        """Color medio de camiseta (BGR) del equipo claro (sid=0)/oscuro (sid=1)."""
        return self._cluster_color.get(self._raw_for_semantic(sid))

    # ------------------------------------------------------------------
    def update(self, frame_bgr: np.ndarray, entities: List[TrackedEntity]) -> None:
        """Predice el equipo de cada entidad y acumula el voto por track_id."""
        if not self._fitted or not entities:
            return
        tids: List[int] = []
        crops: List[np.ndarray] = []
        for e in entities:
            c = self._crop(frame_bgr, e.bbox_xyxy)
            if c.size == 0:
                continue
            tids.append(int(e.track_id))
            crops.append(c)
        if not crops:
            return
        with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull), \
                warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Kwargs passed to")
            warnings.filterwarnings("ignore", message="The channel dimension is ambiguous")
            teams = self._tc.predict(crops)
        self._votes.update(tracker_ids=tids, values=[int(t) for t in teams])

    # ------------------------------------------------------------------
    def team_id(self, track_id: int) -> Optional[int]:
        v = self._votes.get_validated(int(track_id))
        return None if v is None else int(v)

    def color_name(self, track_id: int) -> Optional[str]:
        """Mapea el cluster a las etiquetas que entiende el renderer."""
        tid = self.team_id(track_id)
        if tid is None:
            return None
        return "white" if self._semantic_id(tid) == 0 else "dark"

    def team_name(self, track_id: int) -> Optional[str]:
        tid = self.team_id(track_id)
        if tid is None:
            return None
        names = self._s.team_names
        sid = self._semantic_id(tid)
        return names[sid] if 0 <= sid < len(names) else None
