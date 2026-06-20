"""Genera el mapa 2D cenital usando KaliCalib como estimador de homografía.

Subclasea el orquestador del proyecto y reemplaza SOLO el paso de
homografía (línea 407-408 del orchestrator) con KaliCalib, dejando
intactos detección, tracking, posesión y renderizado.

Ejecutar:
    python scripts/map_kali.py --video data/test_possession_new_q1.mp4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from pipeline.config import Settings, CourtSettings
from pipeline.context import FrameContext
from pipeline.orchestrator import Pipeline
from pipeline.court.kali_detector import KaliCalibDetector


class KaliPipeline(Pipeline):
    """Pipeline idéntico al original excepto que usa KaliCalib para la H."""

    def __init__(self, settings: Settings, kali_checkpoint: str, device: str) -> None:
        super().__init__(settings)
        print("[INFO] KaliPipeline: cargando KaliCalib …")
        self._kali = KaliCalibDetector(checkpoint=kali_checkpoint, device=device)
        print("[INFO] KaliPipeline: listo", flush=True)

    def _process_frame(self, ctx: FrameContext) -> None:
        # Ejecuta TODO el pipeline del padre…
        super()._process_frame(ctx)
        # …y luego sobreescribe SOLO la homografía con KaliCalib.
        est = self._kali.update_from_frame(ctx.frame_bgr)
        ctx.homography = est.H
        ctx.homography_confidence = est.confidence


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--out",   default=None, help="Ruta del vídeo de salida")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--checkpoint",
        default="third_party/KaliCalib/models/model_challenge.pth",
    )
    p.add_argument("--tracker", default="botsort", choices=["botsort", "sam"])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    video_path = Path(args.video)

    out_base = args.out or str(
        Path("docs/results") / f"kali_map_{video_path.stem}.mp4"
    )
    Path(out_base).parent.mkdir(parents=True, exist_ok=True)

    settings = Settings.default()
    settings.tracker_mode   = args.tracker
    settings.write_map_video     = True
    settings.write_overlay_video = False   # solo el mapa, sin overlay
    settings.write_metadata      = False

    pipeline = KaliPipeline(settings, kali_checkpoint=args.checkpoint, device=args.device)
    pipeline.process_video(str(video_path), out_base)


if __name__ == "__main__":
    main()
