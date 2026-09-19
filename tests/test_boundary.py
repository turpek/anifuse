"""Tests for SceneBoundaryResolver, exposure guards, and thumbnail helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from anifuse.cli.factories.reader import ReaderFactory
from anifuse.cli.models import SourceConfig, SourceType
from anifuse.detection.boundary import (
    SceneBoundaryResolver,
    is_abnormal_exposure,
    to_gray_thumbnail,
)
from anifuse.reader import VideoReader


@pytest.fixture
def synthetic_video_with_fades(tmp_path: Path) -> Path:
    """Create a 12-frame synthetic video with whiteout at both ends."""
    video_path = tmp_path / "fades_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 10.0, (160, 90))

    # Base texture pattern
    base_pattern = np.zeros((90, 160, 3), dtype=np.uint8)
    for y in range(90):
        for x in range(160):
            base_pattern[y, x] = ((x * 4) % 256, (y * 4) % 256, ((x + y) * 2) % 256)

    # Frame 0 and 1: whiteout (255)
    for _ in range(2):
        writer.write(np.full((90, 160, 3), 250, dtype=np.uint8))

    # Frames 2 to 9: panning pattern (shifting horizontally)
    for i in range(8):
        shifted = np.roll(base_pattern, shift=i * 4, axis=1)
        writer.write(shifted)

    # Frames 10 and 11: whiteout (255)
    for _ in range(2):
        writer.write(np.full((90, 160, 3), 250, dtype=np.uint8))

    writer.release()
    return video_path


def test_to_gray_thumbnail_resizes_to_target_dimensions():
    """Verify that to_gray_thumbnail converts a BGR frame to single-channel thumbnail."""
    bgr = np.zeros((1080, 1920, 3), dtype=np.uint8)
    thumb = to_gray_thumbnail(bgr, size=(320, 180))

    assert thumb.shape == (180, 320)
    assert thumb.dtype == np.uint8


@pytest.mark.parametrize(
    ("fill_value", "expected"),
    [
        pytest.param(128, False, id="normal_exposure"),
        pytest.param(240, True, id="whiteout_flash"),
        pytest.param(10, True, id="blackout_fade"),
    ],
)
def test_is_abnormal_exposure_detects_luminance_extremes(fill_value: int, expected: bool):
    """Verify that is_abnormal_exposure correctly identifies whiteout and blackout thumbnails."""
    thumb = np.full((180, 320), fill_value=fill_value, dtype=np.uint8)
    result = is_abnormal_exposure(thumb, high=235.0, low=20.0)

    assert result is expected


def test_scene_boundary_resolver_skips_very_short_sequence(tmp_path: Path):
    """Verify that SceneBoundaryResolver leaves sequences with fewer than 4 frames untouched."""
    video_path = tmp_path / "tiny.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 10.0, (64, 64))
    for _ in range(3):
        writer.write(np.full((64, 64, 3), 128, dtype=np.uint8))
    writer.release()

    with VideoReader(video_path) as reader:
        start_fid, end_fid = SceneBoundaryResolver.resolve_and_adjust(reader)

    assert (start_fid, end_fid) == (0, 2)


def test_scene_boundary_resolver_clips_whiteout_edges(synthetic_video_with_fades: Path):
    """Verify that SceneBoundaryResolver excludes edge whiteout frames and retains the scene."""
    with VideoReader(synthetic_video_with_fades) as reader:
        start_fid, end_fid = SceneBoundaryResolver.resolve_and_adjust(reader)
        remaining_fids = list(reader._reader.frame_ids)

    assert start_fid == 2
    assert end_fid == 9
    assert remaining_fids[0] == 2
    assert remaining_fids[-1] == 9


def test_reader_factory_triggers_boundary_resolution_on_timestamp(
    synthetic_video_with_fades: Path,
):
    """Verify that ReaderFactory triggers boundary resolution when timestamp string is provided."""
    source = SourceConfig(
        source_type=SourceType.VIDEO,
        start="00:00",
        end="00:02",
    )
    with ReaderFactory.create_for_path(source, synthetic_video_with_fades) as reader:
        fids = list(reader._reader.frame_ids)

    assert fids[0] == 2
    assert fids[-1] == 9


def test_reader_factory_preserves_bounds_on_integer_indices(
    synthetic_video_with_fades: Path,
):
    """Verify that ReaderFactory leaves boundary frames untouched when given integer frame indices."""
    source = SourceConfig(
        source_type=SourceType.VIDEO,
        start=0,
        end=12,
    )
    with ReaderFactory.create_for_path(source, synthetic_video_with_fades) as reader:
        fids = list(reader._reader.frame_ids)

    assert fids[0] == 0
    assert fids[-1] == 11
