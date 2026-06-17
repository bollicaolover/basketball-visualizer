"""Prueba posesión (config actual) en varios clips y detecta falsos positivos.

Recorre vídeos de test, ejecuta el pipeline con metadatos y reporta frames
sospechosos: poseedor asignado con el balón lejos o cerca del aro.

Uso:
    python scripts/batch_test_possession.py
    python scripts/batch_test_possession.py --videos data/test_videos/foo.mp4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/home/gdfraile/miniconda3/envs/tfg-baloncesto/bin/python"
DEFAULT_VIDEOS = sorted((ROOT / "data/test_videos").glob("*.mp4"))
OUT_DIR = ROOT / "data/batch_possession_test"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--videos", nargs="*", type=Path, default=None)
    p.add_argument("--skip-run", action="store_true", help="solo analizar metadatos ya generados")
    return p.parse_args()


def edge_dist(ball_xy, bbox, margin: float = 15.0) -> float:
    bx, by = ball_xy
    x1, y1, x2, y2 = bbox
    h = max(y2 - y1, 1.0)
    dx = max(x1 - margin - bx, 0.0, bx - (x2 + margin))
    dy = max(y1 - margin - by, 0.0, by - (y2 + margin))
    return float(np.hypot(dx, dy)) / h


def ball_center(frame: dict) -> tuple[float, float] | None:
    ball = frame.get("ball")
    if not ball or not ball.get("bbox"):
        return None
    x1, y1, x2, y2 = ball["bbox"]
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def rim_near(ball_xy, rims: list, factor: float = 2.5) -> bool:
    if not rims:
        return False
    bx, by = ball_xy
    for rim in rims:
        x1, y1, x2, y2 = rim["bbox"]
        rcx = (x1 + x2) / 2.0
        rcy = (y1 + y2) / 2.0
        rh = max(y2 - y1, 1.0)
        if float(np.hypot(bx - rcx, by - rcy)) <= factor * rh:
            return True
    return False


def analyze(metadata_path: Path, max_edge: float = 0.35) -> dict:
    frames = json.loads(metadata_path.read_text())["frames"]
    total = len(frames)
    with_poss = 0
    switches = 0
    prev = None
    suspicious: list[dict] = []

    for f in frames:
        poss = f.get("possessor_track_id")
        bc = ball_center(f)
        if poss is not None:
            with_poss += 1
            if prev is not None and poss != prev:
                switches += 1
            if bc is not None:
                player = next(
                    (p for p in f.get("players", []) if p["track_id"] == poss), None,
                )
                if player and player.get("bbox"):
                    dist = edge_dist(bc, player["bbox"])
                    near_rim = rim_near(bc, f.get("rims", []))
                    if dist > max_edge or (near_rim and dist > 0.25):
                        suspicious.append(
                            {
                                "frame": f["frame_index"],
                                "possessor": poss,
                                "edge_heights": round(dist, 3),
                                "near_rim": near_rim,
                                "shot_made": f.get("shot_made"),
                            }
                        )
        prev = poss if poss is not None else prev

    return {
        "frames": total,
        "with_possessor": with_poss,
        "coverage_pct": round(100.0 * with_poss / total, 1) if total else 0.0,
        "switches": switches,
        "suspicious_frames": suspicious,
    }


def run_pipeline(video: Path, out_video: Path, meta: Path) -> None:
    out_video.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        PYTHON, str(ROOT / "run.py"), str(video),
        "-o", str(out_video),
        "--no-numbers", "--no-map", "--metadata",
        "--progress-every", "9999",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)


def main() -> None:
    args = parse_args()
    videos = args.videos or DEFAULT_VIDEOS
    if not videos:
        raise SystemExit("No hay vídeos en data/test_videos")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    print(f"[INFO] Probando {len(videos)} vídeo(s)\n")
    for video in videos:
        stem = video.stem
        out_video = OUT_DIR / f"{stem}_overlay.mp4"
        meta = OUT_DIR / f"{stem}_metadata.json"

        if not args.skip_run:
            print(f"[RUN] {video.name} ...", flush=True)
            try:
                run_pipeline(video, out_video, meta)
            except subprocess.CalledProcessError as exc:
                print(f"[ERROR] {video.name}: {exc.stderr[-500:]}")
                rows.append({"video": video.name, "error": "pipeline failed"})
                continue
            # run.py writes metadata next to output path
            generated = Path(str(out_video).replace(".mp4", "_metadata.json"))
            if generated.is_file():
                generated.replace(meta)

        if not meta.is_file():
            print(f"[SKIP] sin metadatos: {video.name}")
            continue

        stats = analyze(meta)
        stats["video"] = video.name
        rows.append(stats)
        susp = len(stats["suspicious_frames"])
        print(
            f"  {video.name}: {stats['with_possessor']}/{stats['frames']} "
            f"({stats['coverage_pct']}%) poseedor, {stats['switches']} cambios, "
            f"{susp} frames sospechosos",
        )
        if susp:
            for s in stats["suspicious_frames"][:5]:
                print(
                    f"    frame {s['frame']}: track {s['possessor']} "
                    f"edge={s['edge_heights']} rim={s['near_rim']} shot={s['shot_made']}",
                )
            if susp > 5:
                print(f"    ... y {susp - 5} más")

    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    total_susp = sum(len(r.get("suspicious_frames", [])) for r in rows)
    print(f"\n[INFO] Resumen en {summary_path}")
    print(f"[INFO] Total frames sospechosos: {total_susp} en {len(rows)} vídeos")


if __name__ == "__main__":
    main()
