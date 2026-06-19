"""CLI de reconstrucción 3D del tiro. Lógica en ``pipeline.shot3d.reconstruct``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.io.pipeline_metadata import resolve_metadata_path
from pipeline.shot3d.reconstruct import Shot3DError, run_shot3d


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reconstrucción 3D de un tiro (Pirotta cap. 5)")
    p.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/test_videos/boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4",
    )
    p.add_argument("--start-frame", type=int, default=None)
    p.add_argument("--end-frame", type=int, default=None)
    p.add_argument("--min-segment", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--json-out", type=Path, default=None)
    p.add_argument("--save-video", type=Path, default=None)
    p.add_argument("--no-extend", action="store_true")
    p.add_argument("--pose-release", action="store_true")
    p.add_argument("--require-parabola", action="store_true")
    p.add_argument(
        "--metadata", nargs="?", const="auto", default=None, metavar="PATH",
        help="JSON del pipeline; sin valor → auto junto al vídeo",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    meta_path = resolve_metadata_path(args.input, args.metadata)
    if args.metadata is not None and meta_path is None:
        hint = args.input.with_name(f"{args.input.stem}_metadata.json")
        raise SystemExit(
            f"Metadata no encontrada ({args.metadata!r}). "
            f"Genera con: python run.py {args.input} -o out.mp4 --metadata --no-map "
            f"o pasa --metadata {hint}"
        )
    try:
        run_shot3d(
            input_video=args.input,
            metadata_path=meta_path,
            video_out=args.save_video,
            json_out=args.json_out,
            start_frame=args.start_frame,
            end_frame=args.end_frame,
            min_segment=args.min_segment,
            pose_release=args.pose_release,
            require_parabola=args.require_parabola,
            extend_to_release=not args.no_extend,
            device=args.device,
        )
    except Shot3DError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
