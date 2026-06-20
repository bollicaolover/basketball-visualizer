"""Pasada de reconocimiento de pantallas sobre el metadata del pipeline.

Lee ``{out}_metadata.json`` (trayectorias de jugadores en pies + poseedor por
frame) y escribe ``{out}_tactics.json`` con los eventos de pantalla
reconocidos. Invocable desde el pipeline principal (tras la pasada por vídeo,
como ``shot3d``), desde el backend web o por CLI:

    python -m pipeline.tactics.run {out}_metadata.json [--out {out}_tactics.json]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from pipeline.config import TacticsSettings
from pipeline.io.pipeline_metadata import load_pipeline_metadata
from pipeline.tactics.recognizer import FrameTactics, ScreenRecognizer
from pipeline.tactics.types import PlayerSnapshot


def _frame_tactics(frame: dict[str, Any]) -> FrameTactics:
    players: List[PlayerSnapshot] = []
    for p in frame.get("players") or []:
        x = p.get("x_ft")
        y = p.get("y_ft")
        if x is None or y is None:
            continue
        players.append(
            PlayerSnapshot(
                track_id=int(p["track_id"]),
                team=p.get("team"),
                xy=np.array([float(x), float(y)], dtype=np.float64),
            )
        )
    pid = frame.get("possessor_track_id")
    return FrameTactics(
        frame_index=int(frame["frame_index"]),
        players=players,
        possessor_track_id=int(pid) if pid is not None else None,
    )


def tactics_output_path(metadata_path: str | Path) -> Path:
    """``..._metadata.json`` → ``..._tactics.json`` (o sufijo ``_tactics``)."""
    p = Path(metadata_path)
    stem = p.stem
    if stem.endswith("_metadata"):
        stem = stem[: -len("_metadata")]
    return p.with_name(f"{stem}_tactics.json")


def run_tactics(
    metadata_path: str | Path,
    json_out: Optional[str | Path] = None,
    settings: Optional[TacticsSettings] = None,
) -> dict[str, Any]:
    """Reconoce las pantallas del vídeo y (opcionalmente) las vuelca a JSON.

    Devuelve el documento de resultados (también escrito a ``json_out``).
    """
    meta = load_pipeline_metadata(Path(metadata_path))
    frames = [
        _frame_tactics(meta.frames_by_index[i])
        for i in sorted(meta.frames_by_index)
    ]
    recognizer = ScreenRecognizer(settings or TacticsSettings())
    events = recognizer.recognize(frames)

    counts: dict[str, int] = {}
    for e in events:
        counts[e.screen_type] = counts.get(e.screen_type, 0) + 1

    doc = {
        "team_names": meta.team_names,
        "n_frames": len(frames),
        "screen_counts": counts,
        "screens": [e.to_dict() for e in events],
    }
    if json_out is not None:
        out = Path(json_out)
        if out.parent:
            out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        print(
            f"[INFO] Tácticas: {out} ({len(events)} pantallas: "
            f"{', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'ninguna'})",
            flush=True,
        )
    return doc


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Reconocimiento de pantallas (Chen et al. 2012) sobre el "
        "metadata del pipeline.",
    )
    parser.add_argument("metadata", help="Ruta a {out}_metadata.json")
    parser.add_argument(
        "--out", default=None,
        help="JSON de salida (por defecto {out}_tactics.json junto al metadata).",
    )
    parser.add_argument("--contact-ft", type=float, default=None, help="ds (ft)")
    parser.add_argument("--near-ft", type=float, default=None, help="Ds (ft)")
    parser.add_argument("--angle-deg", type=float, default=None, help="θs (grados)")
    args = parser.parse_args()

    settings = TacticsSettings()
    if args.contact_ft is not None:
        settings.contact_dist_ft = args.contact_ft
    if args.near_ft is not None:
        settings.near_dist_ft = args.near_ft
    if args.angle_deg is not None:
        settings.back_front_angle_deg = args.angle_deg

    out = args.out or tactics_output_path(args.metadata)
    run_tactics(args.metadata, json_out=out, settings=settings)


if __name__ == "__main__":
    main()
