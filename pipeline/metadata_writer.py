"""Serializa los metadatos tácticos por frame a JSON.

Al final de cada frame se llama a `write(ctx)`, que acumula una entrada en
memoria. Al terminar el vídeo, `close()` vuelca el array completo al disco.
El JSON resultante se usa en el frontend para sincronizar el mapa 2D con el
reproductor de vídeo.
"""

from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

from pipeline.context import FrameContext


class MetadataWriter:
    def __init__(
        self,
        output_path: str,
        fps: float,
        team_names: Optional[Tuple[str, str]] = None,
    ) -> None:
        self._path = output_path
        self._fps = fps
        # Nombres de equipo (white→[0], dark→[1]) provistos por el usuario, o
        # None si no se pasaron (el frontend usará "Equipo 1/2" por defecto).
        self._team_names = list(team_names) if team_names else None
        self._frames: List[dict] = []

    @staticmethod
    def _bbox_list(dets) -> List[list]:
        """Lista de bboxes [x1,y1,x2,y2] (px del vídeo) de un ``sv.Detections``."""
        if dets is None or len(dets) == 0:
            return []
        return [[round(float(v)) for v in box] for box in dets.xyxy]

    def write(self, ctx: FrameContext) -> None:
        bbox_by_id: dict = {}
        for e in ctx.tracked_entities:
            bbox_by_id[e.track_id] = [round(float(v)) for v in e.bbox_xyxy]

        players = [
            {
                "track_id": int(p["track_id"]),
                "team": p.get("team"),
                "x_ft": round(float(p["xy_ft"][0]), 3),
                "y_ft": round(float(p["xy_ft"][1]), 3),
                "bbox": bbox_by_id.get(int(p["track_id"])),
                "number": ctx.player_numbers.get(int(p["track_id"])),
                "name": ctx.player_names.get(int(p["track_id"])),
            }
            for p in ctx.players_world
        ]
        # Detecciones por frame (sin track_id estable) para la capa interactiva
        # del frontend: balón, árbitros y aro(s). Permiten filtrar/seleccionar.
        ball_boxes = self._bbox_list(ctx.ball_detections)
        ball = {"bbox": ball_boxes[0]} if ball_boxes else None
        referees = [{"bbox": b} for b in self._bbox_list(ctx.referee_detections)]
        rims = [{"bbox": b} for b in self._bbox_list(ctx.hoop_detections)]
        self._frames.append(
            {
                "frame_index": ctx.frame_index,
                "timestamp": round(ctx.frame_index / self._fps, 4),
                "players": players,
                "ball": ball,
                "referees": referees,
                "rims": rims,
                "possessor_track_id": (
                    int(ctx.possessor_track_id) if ctx.possessor_track_id is not None else None
                ),
                "shot_side": ctx.shot_side,
                "shot_made": ctx.shot_made,
                "homography_confidence": round(float(ctx.homography_confidence), 4),
            }
        )

    def close(self) -> None:
        out_dir = os.path.dirname(self._path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        # Documento con metadatos a nivel de análisis (team_names) + frames. El
        # frontend acepta también el formato antiguo (array plano) por compat.
        doc = {"team_names": self._team_names, "frames": self._frames}
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(doc, f, separators=(",", ":"))
        print(f"[INFO] Metadatos: {self._path} ({len(self._frames)} frames)")
