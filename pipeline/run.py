"""Punto de entrada del pipeline como módulo ejecutable.

Permite lanzarlo como ``python -m pipeline.run`` (usado por el backend FastAPI).
Acepta los mismos flags que ``run.py`` en la raíz, más ``--mem-fraction`` para
compatibilidad con el runner del backend multi-GPU.

Uso:
    python -m pipeline.run --input video.mp4 --output out.mp4 --metadata --no-map
"""

from __future__ import annotations

import argparse

from pipeline.config import Settings
from pipeline.orchestrator import Pipeline


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Pipeline baloncesto: detección + tracking + mapa 2D"
    )
    ap.add_argument("--input", required=True, help="vídeo de entrada (.mp4)")
    ap.add_argument("--output", default="data/out.mp4", help="vídeo anotado de salida")
    ap.add_argument("--no-overlay", action="store_true", help="no escribir el vídeo anotado")
    ap.add_argument("--no-map", action="store_true", help="no escribir el mapa 2D")
    ap.add_argument("--metadata", action="store_true", help="escribir metadatos JSON por frame")
    ap.add_argument("--no-numbers", action="store_true", help="desactivar OCR de dorsal")
    ap.add_argument("--progress-every", type=int, default=None, help="avisar cada N frames")
    ap.add_argument("--roster", default=None, help="JSON con rosters (dorsal→nombre). Opcional.")
    ap.add_argument(
        "--team-names", default=None,
        help="Nombres de los dos equipos separados por coma, p.ej. 'Lakers,Warriors'.",
    )
    ap.add_argument(
        "--tracker",
        choices=("sam", "botsort"),
        default="sam",
        help="backend de tracking: sam (máscaras) o botsort (BoT-SORT)",
    )
    ap.add_argument(
        "--ball-tracker",
        choices=("ema", "kalman"),
        default=None,
        help="seguimiento del balón: ema (suavizado original) o kalman (método Pirotta)",
    )
    ap.add_argument(
        "--shot3d", action="store_true",
        help="reconstrucción 3D del tiro tras el análisis (requiere --metadata)",
    )
    ap.add_argument(
        "--no-shot3d", action="store_true",
        help="desactivar reconstrucción 3D aunque esté --metadata",
    )
    ap.add_argument(
        "--no-shot3d-pose", action="store_true",
        help="sin detección de suelta por pose en la 3D",
    )
    ap.add_argument(
        "--tactics", action="store_true",
        help="reconocer pantallas (screens) tras el análisis (requiere --metadata)",
    )
    # Ignorado en esta implementación (sin partición multi-GPU); se acepta por
    # compatibilidad con el runner del backend que lo pasa siempre.
    ap.add_argument("--mem-fraction", type=float, default=1.0, help=argparse.SUPPRESS)
    args = ap.parse_args()

    settings = Settings.default()
    if args.no_overlay:
        settings.write_overlay_video = False
    if args.no_map:
        settings.write_map_video = False
    if args.metadata:
        settings.write_metadata = True
    if args.no_numbers:
        settings.identity.enabled = False
    if args.progress_every is not None:
        settings.progress_every = args.progress_every
    if args.roster is not None:
        settings.identity.roster_path = args.roster
    if args.team_names is not None:
        parts = [p.strip() for p in args.team_names.split(",", 1)]
        if len(parts) == 2:
            settings.teams.team_names = (parts[0], parts[1])
            settings.metadata_team_names = (parts[0], parts[1])
        else:
            ap.error("--team-names requiere exactamente dos nombres separados por coma")
    settings.tracker_mode = args.tracker
    if args.ball_tracker is not None:
        settings.ball_tracking.method = args.ball_tracker
    if args.shot3d:
        settings.shot3d.enabled = True
    if args.no_shot3d:
        settings.shot3d.enabled = False
    if args.no_shot3d_pose:
        settings.shot3d.pose_release = False
    if args.tactics:
        settings.tactics.enabled = True

    Pipeline(settings).process_video(args.input, args.output)


if __name__ == "__main__":
    main()
