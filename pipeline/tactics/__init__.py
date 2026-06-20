"""Reconocimiento de patrones tácticos (pantallas) a partir de trayectorias.

Implementa el bloque táctico de Chen et al. 2012 (`docs/references/main.pdf`,
ver `docs/tacticas-screen-recognition.md`) sobre las trayectorias en pies que
el pipeline ya escribe en `{out}_metadata.json`.
"""

from pipeline.tactics.recognizer import FrameTactics, ScreenRecognizer
from pipeline.tactics.run import run_tactics, tactics_output_path
from pipeline.tactics.types import PlayerSnapshot, ScreenEvent

__all__ = [
    "FrameTactics",
    "ScreenRecognizer",
    "PlayerSnapshot",
    "ScreenEvent",
    "run_tactics",
    "tactics_output_path",
]
