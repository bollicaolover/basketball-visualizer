"""Tests del selector de tracking sam / botsort."""

from __future__ import annotations

import numpy as np
import pytest
import supervision as sv

from pipeline.config import Settings
from pipeline.identity.number_ocr import JerseyNumberOCR
from pipeline.strategy.factory import build_foot_point, build_sam_tracker
from pipeline.tracking.dedup import deduplicate_player_detections
from pipeline.tracking.foot_point import BBoxFootPoint
from pipeline.tracking.foot_point_mask import MaskFootPoint
from pipeline.tracking.tracker import tracked_entities_from_detections


def test_settings_default_tracker_is_sam():
    assert Settings.default().tracker_mode == "sam"


def test_build_foot_point_by_mode():
    sam = Settings.default()
    sam.tracker_mode = "sam"
    assert isinstance(build_foot_point(sam), MaskFootPoint)

    bot = Settings.default()
    bot.tracker_mode = "botsort"
    assert isinstance(build_foot_point(bot), BBoxFootPoint)


def test_build_sam_tracker_none_for_botsort():
    s = Settings.default()
    s.tracker_mode = "botsort"
    assert build_sam_tracker(s, yolo_prompter=object()) is None


def test_tracked_entities_from_detections_no_mask():
    dets = sv.Detections(
        xyxy=np.array([[10, 20, 50, 80]], dtype=np.float32),
        class_id=np.array([4]),
        confidence=np.array([0.9]),
        tracker_id=np.array([7]),
    )
    entities = tracked_entities_from_detections(dets)
    assert len(entities) == 1
    assert entities[0].track_id == 7
    assert entities[0].mask is None


def test_deduplicate_drops_lower_confidence_box():
    dets = sv.Detections(
        xyxy=np.array([[0, 0, 100, 100], [5, 5, 95, 95]], dtype=np.float32),
        class_id=np.array([4, 4]),
        confidence=np.array([0.9, 0.5]),
        tracker_id=np.array([1, 2]),
    )
    out = deduplicate_player_detections(dets, min_iou=0.45)
    assert len(out) == 1
    assert out.confidence[0] == pytest.approx(0.9)


def test_ocr_bbox_iou_matching():
    a = np.array([0, 0, 100, 100], dtype=np.float32)
    b = np.array([10, 10, 90, 90], dtype=np.float32)
    assert JerseyNumberOCR._bbox_iou(a, b) > 0.5

    c = np.array([200, 200, 250, 250], dtype=np.float32)
    assert JerseyNumberOCR._bbox_iou(a, c) == 0.0
