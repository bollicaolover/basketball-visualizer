"""Escritura de vídeo web: pipe directo a H.264 o fallback cv2 + remux."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np


def _find_ffmpeg() -> Optional[str]:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    candidate = Path(sys.executable).resolve().parent / "ffmpeg"
    if candidate.is_file():
        return str(candidate)
    return None


# ---------------------------------------------------------------------------
# Pipe writer (sin doble I/O)
# ---------------------------------------------------------------------------

class FFmpegPipeWriter:
    """Codifica frames BGR directamente a H.264 vía stdin de ffmpeg.

    Elimina el doble I/O de cv2.VideoWriter (mp4v) + remux posterior:
    los frames van al encoder sin pasar por disco como archivo temporal.
    """

    def __init__(
        self, path: str, fps: float, width: int, height: int,
        preset: str = "fast", crf: int = 23,
    ) -> None:
        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            raise RuntimeError("ffmpeg no encontrado")

        cmd = [
            ffmpeg, "-y",
            "-loglevel", "error",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-g", "15",          # keyframe cada 0.5 s → scrubbing fluido
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            path,
        ]
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self._path = path
        self._closed = False

    def write(self, frame_bgr: np.ndarray) -> None:
        if self._closed or self._proc.stdin is None:
            return
        try:
            self._proc.stdin.write(frame_bgr.tobytes())
        except (BrokenPipeError, OSError):
            self._closed = True

    def release(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            _, stderr = self._proc.communicate()
        except (OSError, ValueError):
            self._proc.wait()
            stderr = b""
        if self._proc.returncode != 0:
            err = (stderr or b"").decode(errors="replace").strip()[-600:]
            print(f"[WARN] ffmpeg pipe error ({self._path}): {err}")
        else:
            print(f"[INFO] Vídeo web (H.264 pipe): {self._path}")


# ---------------------------------------------------------------------------
# Fallback cv2 + remux (cuando ffmpeg no está disponible como pipe)
# ---------------------------------------------------------------------------

class _OpenCVFallbackWriter:
    """cv2.VideoWriter (mp4v) + remux H.264 en release(). Mismo interfaz que FFmpegPipeWriter."""

    def __init__(self, path: str, fps: float, width: int, height: int) -> None:
        import cv2
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
        self._path = path

    def write(self, frame_bgr: np.ndarray) -> None:
        self._writer.write(frame_bgr)

    def release(self) -> None:
        self._writer.release()
        remux_for_browser(self._path)


def open_video_writer(
    path: str, fps: float, width: int, height: int,
    preset: str = "fast", crf: int = 23,
):
    """Devuelve el writer más eficiente disponible.

    Preferencia: FFmpegPipeWriter (sin doble I/O) → _OpenCVFallbackWriter.
    Ambos exponen write(frame) / release().
    """
    if _find_ffmpeg() is not None:
        try:
            return FFmpegPipeWriter(path, fps, width, height, preset=preset, crf=crf)
        except Exception as exc:
            print(f"[WARN] FFmpegPipeWriter falló ({exc}); usando cv2 + remux")
    return _OpenCVFallbackWriter(path, fps, width, height)


# ---------------------------------------------------------------------------
# Remux standalone (conservado para compatibilidad con código externo)
# ---------------------------------------------------------------------------

def remux_for_browser(path: str) -> bool:
    """Recodifica *path* en H.264 + faststart in-place. Devuelve True si lo consigue."""
    if not path or not os.path.isfile(path):
        return False

    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        print("[WARN] ffmpeg no encontrado; el vídeo puede no reproducirse en el navegador")
        return False

    out_dir = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(suffix=".mp4", dir=out_dir)
    os.close(fd)
    try:
        result = subprocess.run(
            [
                ffmpeg, "-y", "-loglevel", "error",
                "-i", path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-g", "15",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                tmp,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()[-800:]
            print(f"[WARN] ffmpeg remux falló ({path}): {err}")
            return False
        os.replace(tmp, path)
        print(f"[INFO] Vídeo web (H.264): {path}")
        return True
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
