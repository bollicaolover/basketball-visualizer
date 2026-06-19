"""CLI del pipeline tfg-junio.

Uso:
    conda activate tfg-baloncesto
    python run.py data/clip.mp4 -o data/out.mp4
    python run.py data/clip.mp4 -o data/out.mp4 --no-numbers   # sin OCR de dorsal
"""

from __future__ import annotations

import argparse

from pipeline.config import Settings
from pipeline.orchestrator import Pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="Pipeline baloncesto: detección + tracking + mapa 2D")
    ap.add_argument("input", help="vídeo de entrada (.mp4)")
    ap.add_argument("-o", "--output", default="data/out.mp4", help="vídeo anotado de salida")
    ap.add_argument("--no-overlay", action="store_true", help="no escribir el vídeo anotado")
    ap.add_argument("--no-map", action="store_true", help="no escribir el mapa 2D")
    ap.add_argument("--metadata", action="store_true", help="escribir metadatos JSON por frame")
    ap.add_argument("--no-numbers", action="store_true", help="desactivar OCR de dorsal")
    ap.add_argument("--clean-paths", action="store_true", help="suavizar trayectorias (sports.clean_paths)")
    ap.add_argument("--progress-every", type=int, default=None, help="avisar cada N frames (por defecto 50)")
    ap.add_argument("--roster", default=None, help="JSON con rosters (dorsal→nombre). Opcional.")
    ap.add_argument(
        "--team-names", default=None,
        help="Nombres de los dos equipos separados por coma, p.ej. 'Lakers,Warriors'. "
             "Necesario para que el lookup del roster funcione.",
    )
    ap.add_argument(
        "--tracker",
        choices=("sam", "botsort"),
        default="sam",
        help="backend de tracking de jugadores: sam (máscaras) o botsort (BoT-SORT, más rápido)",
    )
    ap.add_argument(
        "--ball-tracker",
        choices=("ema", "kalman"),
        default=None,
        help="seguimiento del balón: ema (suavizado original) o kalman (Kalman + "
             "validación de trayectoria, método Pirotta)",
    )
    ap.add_argument("--shot3d", action="store_true", help="reconstrucción 3D del tiro (requiere --metadata)")
    ap.add_argument("--no-shot3d", action="store_true", help="desactivar reconstrucción 3D")
    ap.add_argument("--no-shot3d-pose", action="store_true", help="sin suelta por pose en la 3D")
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
    if args.clean_paths:
        settings.clean_paths = True
    if args.progress_every is not None:
        settings.progress_every = args.progress_every
    if args.roster is not None:
        settings.identity.roster_path = args.roster
    if args.team_names is not None:
        parts = [p.strip() for p in args.team_names.split(",", 1)]
        if len(parts) == 2:
            settings.teams.team_names = (parts[0], parts[1])
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

    Pipeline(settings).process_video(args.input, args.output)


if __name__ == "__main__":
    main()
