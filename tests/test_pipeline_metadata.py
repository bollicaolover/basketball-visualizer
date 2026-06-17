"""Tests del loader de metadata del pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pipeline.io.pipeline_metadata import (
    ball_center_from_frame,
    load_pipeline_metadata,
    nearest_player_bbox,
    resolve_metadata_path,
    rim_observation_from_frame,
)


def test_load_and_extract_detections(tmp_path: Path):
    doc = {
        "team_names": ["Celtics", "Knicks"],
        "frames": [
            {
                "frame_index": 0,
                "ball": {"bbox": [100, 200, 110, 210]},
                "rims": [{"bbox": [500, 50, 530, 80]}],
                "players": [{"track_id": 1, "bbox": [90, 180, 130, 260]}],
            },
        ],
    }
    path = tmp_path / "clip_metadata.json"
    path.write_text(json.dumps(doc))

    meta = load_pipeline_metadata(path)
    fr = meta.get(0)
    ball = ball_center_from_frame(fr)
    assert ball is not None
    np.testing.assert_allclose(ball, [105.0, 205.0])
    rim = rim_observation_from_frame(fr)
    assert rim is not None
    np.testing.assert_allclose(rim[0], [515.0, 65.0])
    pbox = nearest_player_bbox(fr, ball)
    assert pbox is not None


def test_resolve_metadata_auto(tmp_path: Path):
    video = tmp_path / "game.mp4"
    video.write_bytes(b"x")
    meta = tmp_path / "game_metadata.json"
    meta.write_text('{"frames": []}')
    assert resolve_metadata_path(video, "auto") == meta
    assert resolve_metadata_path(video, None) is None
