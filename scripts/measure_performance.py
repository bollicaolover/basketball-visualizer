"""Medición de rendimiento del pipeline: VRAM pico y speedup multi-GPU.

Completa las dos cifras que `docs/datos-reales-tfg.md` marca como pendientes
(consumo de VRAM y aceleración multi-GPU) para el capítulo 7 de la memoria.

Qué hace:
  1. **Single-GPU**: lanza ``python -m pipeline.run`` sobre un clip en 1 GPU
     (igual que el backend), muestreando ``nvidia-smi`` para registrar el pico
     de VRAM, y cronometra el tiempo de pared.
  2. **Multi-GPU**: trocea el clip en N segmentos contiguos con
     ``backend.app.chunking`` (uno por GPU), los procesa en paralelo —cada
     subproceso fijado a su GPU vía ``CUDA_VISIBLE_DEVICES``— y recombina los
     overlays. Cronometra el tiempo de pared y calcula el speedup.

No inventa nada: todo sale de ejecuciones reales. Imprime un resumen y vuelca
un JSON con los resultados.

Uso:
    conda activate tfg-baloncesto
    python scripts/measure_performance.py \
        --clip data/test_videos/boston-celtics-new-york-knicks-game-1-q2-10.36-10.32.mp4 \
        --gpus 0,1 --out docs/perf-results.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.chunking import chunk_ranges, concat_videos, probe_video, split_video  # noqa: E402


# ---------------------------------------------------------------------------
# Muestreo de VRAM vía nvidia-smi
# ---------------------------------------------------------------------------
class VramSampler:
    """Muestrea ``memory.used`` de unas GPUs en un hilo y guarda el pico (MiB)."""

    def __init__(self, gpu_indices: List[int], interval_s: float = 0.5) -> None:
        self._gpus = gpu_indices
        self._interval = interval_s
        self._peak = {g: 0 for g in gpu_indices}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _sample_once(self) -> None:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,memory.used",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            return
        for line in out.strip().splitlines():
            try:
                idx, used = (int(x.strip()) for x in line.split(","))
            except ValueError:
                continue
            if idx in self._peak:
                self._peak[idx] = max(self._peak[idx], used)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(self._interval)

    def __enter__(self) -> "VramSampler":
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def peak_mib(self) -> dict:
        return dict(self._peak)


# ---------------------------------------------------------------------------
# Lanzamiento del pipeline (réplica del runner del backend)
# ---------------------------------------------------------------------------
def _run_pipeline(input_path: Path, output_path: Path, gpu: int) -> float:
    """Procesa *input_path* en una GPU. Devuelve el tiempo de pared (s)."""
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)}
    cmd = [
        sys.executable, "-m", "pipeline.run",
        "--input", str(input_path),
        "--output", str(output_path),
        "--metadata", "--no-map",
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                          capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-2000:])
        raise RuntimeError(f"pipeline.run falló en GPU {gpu} (rc={proc.returncode})")
    return elapsed


def measure_single(clip: Path, workdir: Path, gpu: int) -> dict:
    out = workdir / "single_overlay.mp4"
    print(f"[single-GPU] procesando en GPU {gpu} …", flush=True)
    with VramSampler([gpu]) as sampler:
        wall = _run_pipeline(clip, out, gpu)
    peak = sampler.peak_mib[gpu]
    print(f"[single-GPU] {wall:.1f}s pared · VRAM pico {peak} MiB", flush=True)
    return {"wall_s": round(wall, 2), "vram_peak_mib": peak, "gpu": gpu}


def measure_multi(clip: Path, workdir: Path, gpus: List[int]) -> dict:
    fps, total = probe_video(str(clip))
    ranges = chunk_ranges(total, len(gpus))
    n = len(ranges)
    if n < 2:
        print(f"[multi-GPU] clip demasiado corto para {len(gpus)} GPUs; omitido.")
        return {}

    chunk_inputs = [workdir / f"chunk_{i}.mp4" for i in range(n)]
    chunk_outputs = [workdir / f"chunk_{i}_overlay.mp4" for i in range(n)]
    split_video(str(clip), [str(p) for p in chunk_inputs], ranges, fps)

    print(f"[multi-GPU] {n} trozos en GPUs {gpus[:n]} (paralelo) …", flush=True)
    results: dict = {}
    errors: List[str] = []

    def _worker(i: int, gpu: int) -> None:
        try:
            results[i] = _run_pipeline(chunk_inputs[i], chunk_outputs[i], gpu)
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))

    with VramSampler(gpus[:n]) as sampler:
        t0 = time.perf_counter()
        threads = [threading.Thread(target=_worker, args=(i, gpus[i])) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall = time.perf_counter() - t0
    if errors:
        raise RuntimeError("; ".join(errors))

    concat_videos([str(p) for p in chunk_outputs], str(workdir / "multi_overlay.mp4"))
    print(f"[multi-GPU] {wall:.1f}s pared · pico/ GPU {sampler.peak_mib}", flush=True)
    return {
        "n_gpus": n,
        "wall_s": round(wall, 2),
        "vram_peak_mib": sampler.peak_mib,
        "per_chunk_wall_s": {i: round(v, 2) for i, v in sorted(results.items())},
        "frames": total,
        "ranges": ranges,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clip", required=True, help="vídeo de prueba (.mp4)")
    ap.add_argument("--gpus", default="0,1", help="índices de GPU separados por coma")
    ap.add_argument("--out", default="docs/perf-results.json", help="JSON de salida")
    ap.add_argument("--skip-multi", action="store_true", help="solo single-GPU")
    args = ap.parse_args()

    clip = Path(args.clip).resolve()
    if not clip.exists():
        ap.error(f"no existe el clip: {clip}")
    gpus = [int(g) for g in args.gpus.split(",") if g.strip() != ""]

    workdir = PROJECT_ROOT / "data" / "_perf_tmp"
    workdir.mkdir(parents=True, exist_ok=True)

    fps, total = probe_video(str(clip))
    report: dict = {
        "clip": clip.name,
        "frames": total,
        "fps": round(fps, 3),
        "gpu_name": _gpu_name(gpus[0]),
    }

    report["single"] = measure_single(clip, workdir, gpus[0])

    if not args.skip_multi and len(gpus) >= 2:
        multi = measure_multi(clip, workdir, gpus)
        if multi:
            report["multi"] = multi
            speedup = report["single"]["wall_s"] / multi["wall_s"]
            report["speedup"] = round(speedup, 2)
            report["efficiency"] = round(speedup / multi["n_gpus"], 3)

    out_path = PROJECT_ROOT / args.out
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n===== RESUMEN =====")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nGuardado en {out_path}")


def _gpu_name(idx: int) -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader", "-i", str(idx)],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return out or "desconocida"
    except Exception:
        return "desconocida"


if __name__ == "__main__":
    main()
