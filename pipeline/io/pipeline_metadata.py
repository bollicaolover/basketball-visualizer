"""Lectura del JSON táctico generado por ``MetadataWriter`` (pipeline principal).

Formato (``{out}_metadata.json`` o ``overlay_metadata.json`` en jobs web):

    {"team_names": [...], "frames": [{"frame_index", "ball", "rims", "players", ...}]}

El script de reconstrucción 3D reutiliza balón, aro(s) y bboxes de jugadores
sin volver a ejecutar RF-DETR.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PipelineMetadata:
    """Índice por ``frame_index`` del JSON del pipeline."""

    path: Path
    frames_by_index: dict[int, dict[str, Any]]
    team_names: list[str] | None = None

    def get(self, frame_index: int) -> dict[str, Any] | None:
        return self.frames_by_index.get(frame_index)


def resolve_metadata_path(input_video: Path, explicit: str | Path | None) -> Path | None:
    """Resuelve la ruta al JSON del pipeline.

    ``explicit`` puede ser una ruta concreta o ``"auto"`` (``--metadata`` sin
    argumento) para buscar candidatos habituales.
    """
    if explicit is None:
        return None
    if str(explicit).strip().lower() != "auto":
        path = Path(explicit)
        return path if path.is_file() else None

    names = (
        f"{input_video.stem}_metadata.json",
        f"{input_video.stem}_pipeline_metadata.json",
    )
    search_dirs = [input_video.parent]
    for parent in input_video.resolve().parents:
        results = parent / "docs" / "results"
        if results.is_dir():
            search_dirs.append(results)
            break
    for directory in search_dirs:
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def load_pipeline_metadata(path: Path) -> PipelineMetadata:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        frames = doc
        team_names = None
    elif isinstance(doc, dict):
        frames = doc.get("frames", [])
        raw_names = doc.get("team_names")
        team_names = list(raw_names) if raw_names else None
    else:
        raise ValueError(f"metadata no válida: {path}")
    by_idx = {int(f["frame_index"]): f for f in frames}
    return PipelineMetadata(path=path, frames_by_index=by_idx, team_names=team_names)


def bbox_center(box: list | np.ndarray) -> np.ndarray:
    b = np.asarray(box, dtype=np.float64)
    return np.array([(b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0], dtype=np.float64)


def rim_observation_from_bbox(box: list | np.ndarray) -> tuple[np.ndarray, float]:
    """Centro del aro y radio ≈ mitad de la altura del bbox (px)."""
    b = np.asarray(box, dtype=np.float64)
    center = bbox_center(b)
    radius = max(float(b[3] - b[1]) / 2.0, 8.0)
    return center, radius


def ball_center_from_frame(frame: dict[str, Any] | None) -> np.ndarray | None:
    if not frame:
        return None
    ball = frame.get("ball")
    if not ball or not ball.get("bbox"):
        return None
    return bbox_center(ball["bbox"])


def rim_observation_from_frame(
    frame: dict[str, Any] | None,
) -> tuple[np.ndarray, float] | None:
    if not frame:
        return None
    rims = frame.get("rims") or []
    if not rims:
        return None
    return rim_observation_from_bbox(rims[0]["bbox"])


def nearest_player_bbox(
    frame: dict[str, Any] | None, ball_xy: np.ndarray,
) -> np.ndarray | None:
    """Bbox del jugador más cercano al balón (para pose-release)."""
    if not frame:
        return None
    players = frame.get("players") or []
    best_box = None
    best_d = float("inf")
    for p in players:
        box = p.get("bbox")
        if not box:
            continue
        c = bbox_center(box)
        d = float(np.hypot(c[0] - ball_xy[0], c[1] - ball_xy[1]))
        if d < best_d:
            best_d = d
            best_box = np.asarray(box, dtype=np.float64)
    return best_box
