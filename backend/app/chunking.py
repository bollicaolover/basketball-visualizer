"""Utilidades para procesar un vídeo repartido en trozos entre varias GPUs.

El backend parte el vídeo en N segmentos contiguos (uno por GPU), procesa cada
uno en un subproceso aislado (``CUDA_VISIBLE_DEVICES``) y luego concatena los
overlays y fusiona los metadatos. Aquí viven las funciones puras (reparto de
frames y fusión de metadatos) y los helpers de ffmpeg/ffprobe, separados de
``main.py`` para poder testearlos sin levantar FastAPI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Tuple

from pipeline.io.video import _find_ffmpeg


def chunk_ranges(total_frames: int, n: int) -> List[Tuple[int, int]]:
    """Reparte ``total_frames`` en hasta ``n`` trozos contiguos.

    Devuelve ``[(start_frame, num_frames), ...]`` que cubren ``[0, total)`` sin
    solapes ni huecos. Los primeros ``total % n`` trozos llevan un frame extra
    para repartir el resto. Se omiten los trozos vacíos (cuando ``n`` > frames).
    """
    if total_frames <= 0 or n <= 0:
        return []
    n = min(n, total_frames)
    base, rem = divmod(total_frames, n)
    ranges: List[Tuple[int, int]] = []
    start = 0
    for i in range(n):
        count = base + (1 if i < rem else 0)
        if count <= 0:
            continue
        ranges.append((start, count))
        start += count
    return ranges


def merge_metadata(
    chunks: List[List[dict]], frame_offsets: List[int], fps: float,
) -> List[dict]:
    """Fusiona los metadatos por-frame de cada trozo en una única lista.

    Cada trozo procesó su propio segmento, así que sus ``frame_index`` empiezan
    en 0; se desplazan por el offset de frames del trozo y se recalcula el
    ``timestamp``. El resultado se ordena por ``frame_index`` global.
    """
    merged: List[dict] = []
    safe_fps = fps if fps and fps > 0 else 30.0
    for frames, offset in zip(chunks, frame_offsets):
        for fr in frames:
            entry = dict(fr)
            new_index = int(entry.get("frame_index", 0)) + offset
            entry["frame_index"] = new_index
            entry["timestamp"] = round(new_index / safe_fps, 4)
            merged.append(entry)
    merged.sort(key=lambda f: f["frame_index"])
    return merged


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe helpers
# ---------------------------------------------------------------------------

def probe_video(path: str) -> Tuple[float, int]:
    """Devuelve ``(fps, total_frames)`` del vídeo usando OpenCV."""
    import cv2  # noqa: PLC0415

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"No se pudo abrir el vídeo: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return float(fps), total


def split_video(
    input_path: str,
    out_paths: List[str],
    ranges: List[Tuple[int, int]],
    fps: float,
) -> None:
    """Parte ``input_path`` en segmentos exactos (re-encode) según ``ranges``.

    Cada trozo se recorta por tiempo (``-ss``/``-t`` derivados de los frames y
    el fps). El último trozo omite ``-t`` para leer hasta EOF y garantizar que
    no se pierde ningún frame por redondeo.
    """
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg no encontrado; no se puede partir el vídeo")
    safe_fps = fps if fps and fps > 0 else 30.0
    n = len(ranges)
    for i, ((start, count), out_path) in enumerate(zip(ranges, out_paths)):
        start_t = start / safe_fps
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-ss", f"{start_t:.6f}", "-i", str(input_path),
        ]
        if i < n - 1:
            cmd += ["-t", f"{count / safe_fps:.6f}"]
        cmd += [
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", str(out_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            err = (res.stderr or res.stdout or "").strip()[-800:]
            raise RuntimeError(f"ffmpeg split falló (trozo {i}): {err}")


def concat_videos(in_paths: List[str], out_path: str) -> None:
    """Concatena varios MP4 H.264 en uno solo con el demuxer concat (-c copy)."""
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg no encontrado; no se puede concatenar")
    out_dir = Path(out_path).resolve().parent
    list_file = out_dir / "_concat_list.txt"
    list_file.write_text(
        "".join(f"file '{Path(p).resolve()}'\n" for p in in_paths),
        encoding="utf-8",
    )
    try:
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", "-movflags", "+faststart", str(out_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            err = (res.stderr or res.stdout or "").strip()[-800:]
            raise RuntimeError(f"ffmpeg concat falló: {err}")
    finally:
        if list_file.exists():
            list_file.unlink()


# Intervalo de keyframes (GOP) del vídeo limpio. ``1`` = all-intra (cada frame
# es keyframe) → el seek a cualquier instante es casi instantáneo, de modo que
# el vídeo sigue al slider sin tirones. Sube el tamaño del fichero ~5-8×; para
# vídeos largos donde el almacenamiento importe, usar p.ej. el fps (1 keyframe
# por segundo) como compromiso entre fluidez de scrub y tamaño.
CLEAN_GOP = 1


def transcode_clean(input_path: str, out_path: str) -> None:
    """Transcodifica el vídeo original a H.264 web (sin overlay) para reproducción.

    Conserva la resolución exacta (sin escalado) para que los bbox de los
    metadatos —en píxeles del vídeo— alineen con la capa de cajas del frontend.
    All-intra (``-g 1``, ``CLEAN_GOP``) hace el *seek* casi instantáneo para que
    el scrub siga al slider. ``+faststart`` permite el streaming progresivo;
    ``-an`` descarta el audio.
    """
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg no encontrado; no se puede generar el vídeo limpio")
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(input_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-g", str(CLEAN_GOP), "-keyint_min", str(CLEAN_GOP), "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()[-800:]
        raise RuntimeError(f"ffmpeg transcode limpio falló: {err}")
