"""Detección de tiro (acierto/fallo) y conteo a partir de las señales del detector."""

from pipeline.scoring.shot_tracker import ShotEvent, ShotResult, ShotTracker

__all__ = ["ShotTracker", "ShotResult", "ShotEvent"]
