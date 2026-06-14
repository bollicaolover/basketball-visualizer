"""Factories del backend de tracking según ``Settings.tracker_mode``."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from pipeline.tracking.foot_point import BBoxFootPoint, IFootPointEstimator
from pipeline.tracking.tracker import ITracker

if TYPE_CHECKING:
    from pipeline.config import Settings

_LOG = logging.getLogger(__name__)

VALID_TRACKER_MODES = frozenset({"sam", "botsort"})
VALID_BALL_METHODS = frozenset({"ema", "kalman"})


def build_ball_tracker(settings: "Settings") -> Any:
    """Devuelve el seguidor del balón según ``settings.ball_tracking.method``.

    ``"ema"`` → :class:`BallTracker` (suavizado exponencial, original).
    ``"kalman"`` → :class:`KalmanBallTracker` (Kalman + validación de trayectoria).
    """
    method = settings.ball_tracking.method
    if method not in VALID_BALL_METHODS:
        raise ValueError(
            f"ball_tracking.method inválido: {method!r} (usa 'ema' o 'kalman')"
        )
    if method == "kalman":
        from pipeline.tracking.ball_tracker_kalman import KalmanBallTracker

        return KalmanBallTracker(settings.ball_tracking)

    from pipeline.tracking.ball_tracker import BallTracker

    return BallTracker(settings.ball_tracking)


def build_foot_point(settings: "Settings") -> IFootPointEstimator:
    if settings.tracker_mode == "sam":
        from pipeline.tracking.foot_point_mask import MaskFootPoint

        return MaskFootPoint()
    return BBoxFootPoint()


def build_sam_tracker(
    settings: "Settings", yolo_prompter: Any,
) -> Optional[ITracker]:
    if settings.tracker_mode != "sam":
        return None

    if yolo_prompter is None:
        raise ValueError("build_sam_tracker requiere el detector RF-DETR como prompter.")

    try:
        from pipeline.tracking.sam_tracker import SAMTracker

        return SAMTracker(settings.sam, yolo_prompter=yolo_prompter)
    except ImportError as exc:
        _LOG.warning(
            "tracker_mode='sam' pero SAM no está disponible (%s). "
            "Usa --tracker botsort o instala transformers/SAM 3.",
            exc,
        )
        return None
