"""BoT-SORT (boxmot) para tracking de jugadores por bounding box."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import supervision as sv

from pipeline.config import PLAYER_CLASSES, PlayerTrackingSettings

_LOG = logging.getLogger(__name__)


class PlayerTracker:
    """BoT-SORT envuelto para producir/consumir :class:`sv.Detections`."""

    def __init__(self, settings: Optional[PlayerTrackingSettings] = None) -> None:
        s = settings or PlayerTrackingSettings()
        self._s = s

        from boxmot.trackers.botsort.botsort import BotSort

        reid_model = self._build_reid_model() if s.botsort_with_reid else None
        with_reid = s.botsort_with_reid and reid_model is not None

        self._tracker = BotSort(
            reid_model=reid_model,
            track_high_thresh=s.botsort_track_high_thresh,
            track_low_thresh=s.botsort_track_low_thresh,
            new_track_thresh=s.botsort_new_track_thresh,
            track_buffer=s.botsort_track_buffer,
            match_thresh=s.botsort_match_thresh,
            proximity_thresh=s.botsort_proximity_thresh,
            appearance_thresh=s.botsort_appearance_thresh,
            cmc_method=s.botsort_cmc_method,
            frame_rate=s.botsort_frame_rate,
            fuse_first_associate=s.botsort_fuse_first_associate,
            with_reid=with_reid,
            per_class=False,
            min_hits=s.botsort_min_hits,
        )

    def _build_reid_model(self):
        try:
            from boxmot.reid import ReID

            weights = Path(self._s.botsort_reid_weights)
            return ReID(
                weights=weights,
                device=self._s.botsort_device,
                half=self._s.botsort_reid_half,
            ).model
        except Exception as exc:  # noqa: BLE001
            _LOG.warning(
                "BoT-SORT: no se pudo cargar ReID (%s). Continuando motion-only.",
                exc,
            )
            return None

    def update(
        self,
        detections: sv.Detections,
        frame_bgr: np.ndarray,
    ) -> sv.Detections:
        empty_dets = np.zeros((0, 6), dtype=np.float32)

        if detections is None or len(detections) == 0:
            self._tracker.update(empty_dets, frame_bgr)
            return sv.Detections.empty()

        player_mask = np.isin(detections.class_id, list(PLAYER_CLASSES))
        if not player_mask.any():
            self._tracker.update(empty_dets, frame_bgr)
            return sv.Detections.empty()

        players = detections[player_mask]
        if len(players) > 1:
            players = players.with_nms(
                threshold=self._s.detection_nms_iou,
                class_agnostic=True,
            )

        if len(players) == 0:
            self._tracker.update(empty_dets, frame_bgr)
            return sv.Detections.empty()

        dets = np.concatenate(
            [
                players.xyxy.astype(np.float32),
                players.confidence.reshape(-1, 1).astype(np.float32),
                players.class_id.reshape(-1, 1).astype(np.float32),
            ],
            axis=1,
        )

        out = self._tracker.update(dets, frame_bgr)
        if out is None or len(out) == 0:
            return sv.Detections.empty()

        out = np.asarray(out, dtype=np.float32)
        det_idx = out[:, 7].astype(int)
        valid = (det_idx >= 0) & (det_idx < len(players))
        if not valid.any():
            return sv.Detections.empty()

        out = out[valid]
        det_idx = det_idx[valid]
        kept = players[det_idx]
        kept.tracker_id = out[:, 4].astype(int)
        return kept
