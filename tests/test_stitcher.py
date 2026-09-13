"""Tests for SceneStitcher orchestrator."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from anicrop import transform_image
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.layer import Layer
from anicrop.render import warp_patch
from anicrop.spatial import Region

from anifuse.detection.orb import OrbTransformEstimator, resize_image
from anifuse.handlers import (
    RotationHandler,
    ScaleHandler,
    TranslationHandler,
)
from anifuse.interfaces import (
    AlignmentResult,
    Frame,
    FrameAccumulator,
    FrameReader,
    MotionEstimate,
    Section,
    StackOrder,
    StitchContext,
    ViewPolicy,
)
from anifuse.stitcher import SceneStitcher
from anifuse.view_policy import AdaptiveViewPolicy

if TYPE_CHECKING:
    pass


class _MockFrameReader(FrameReader):
    """Synthetic in-memory FrameReader yielding fixed frames."""

    def __init__(self, frames: list[Frame]) -> None:
        self._frames = list(frames)

    def __len__(self) -> int:
        return len(self._frames)

    def __iter__(self) -> Iterator[Frame]:
        yield from self._frames


class _MockViewPolicy(ViewPolicy):
    """Mock ViewPolicy returning fixed alignment shifts."""

    def __init__(self, dx: float = 20.0, dy: float = 0.0) -> None:
        self.dx = dx
        self.dy = dy

    def resolve(
        self,
        base: Image,
        incoming: Image,
        sections: Iterable[Section],
        frame_idx: int = 0,
    ) -> tuple[AlignmentResult, Layer]:
        first_section = next(iter(sections))
        motion = MotionEstimate(dx=self.dx, dy=self.dy, confidence=0.99)
        return AlignmentResult(ref=first_section.ref, motion=motion), Layer(incoming)


@pytest.fixture
def synthetic_frame() -> Frame:
    """Return a single 100x100 synthetic Frame."""
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    arr[:, :] = [200, 100, 50, 255]
    return Frame(idx=1, image=Image(arr, ImageFormat.RGBA))


@pytest.fixture
def synthetic_sequence() -> list[Frame]:
    """Return 3 synthetic 100x100 Frames."""
    frames = []
    for i in range(1, 4):
        arr = np.zeros((100, 100, 4), dtype=np.uint8)
        arr[:, :] = [i * 60, 50, 50, 255]
        frames.append(Frame(idx=i, image=Image(arr, ImageFormat.RGBA)))
    return frames


@pytest.fixture
def synthetic_pattern_frame() -> Image:
    """Generate a synthetic 300x300 frame with high-contrast distinct textured features."""
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    for i in range(12):
        x = 30 + (i % 4) * 60
        y = 30 + (i // 4) * 80
        cv2.rectangle(img, (x, y), (x + 40, y + 40), (200, 200, 200), -1)
        cv2.putText(
            img, f"K{i}", (x + 5, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2
        )
    return Image(img, ImageFormat.RGB)


def test_stitch_raises_value_error_on_empty_reader():
    """Verify that stitch raises ValueError when reader contains zero frames."""
    reader = _MockFrameReader([])
    stitcher = SceneStitcher(
        handlers=[TranslationHandler()], view_policy=_MockViewPolicy()
    )

    with pytest.raises(ValueError, match="no frames to stitch"):
        stitcher.stitch(reader)


def test_stitch_single_frame_returns_image(synthetic_frame: Frame):
    """Verify that stitch returns single frame Image directly when reader has length 1."""
    reader = _MockFrameReader([synthetic_frame])
    stitcher = SceneStitcher(
        handlers=[TranslationHandler()],
        view_policy=_MockViewPolicy(),
    )

    result = stitcher.stitch(reader, stack_order=StackOrder.FIRST_ON_TOP)

    assert isinstance(result, Image)
    assert result.size == (100, 100)


def test_stitch_single_frame_with_both_returns_tuple(synthetic_frame: Frame):
    """Verify that stitch returns duplicate tuple when reader has length 1 with StackOrder.BOTH."""
    reader = _MockFrameReader([synthetic_frame])
    stitcher = SceneStitcher(
        handlers=[TranslationHandler()],
        view_policy=_MockViewPolicy(),
    )

    result = stitcher.stitch(reader, stack_order=StackOrder.BOTH)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], Image)
    assert isinstance(result[1], Image)


def test_stitch_multi_frame_expands_composite_canvas(
    synthetic_sequence: list[Frame],
):
    """Verify that stitch expands canvas across sequential translated frames."""
    reader = _MockFrameReader(synthetic_sequence)
    stitcher = SceneStitcher(
        handlers=[TranslationHandler()],
        view_policy=_MockViewPolicy(dx=20.0, dy=0.0),
    )

    result = stitcher.stitch(reader, stack_order=StackOrder.FIRST_ON_TOP)

    assert isinstance(result, Image)
    assert result.size[0] > 100
    assert result.size[1] == 100


def test_stitch_multi_frame_with_both_returns_image_pair(
    synthetic_sequence: list[Frame],
):
    """Verify that stitch with StackOrder.BOTH produces a pair of rendered images."""
    reader = _MockFrameReader(synthetic_sequence)
    stitcher = SceneStitcher(
        handlers=[TranslationHandler()],
        view_policy=_MockViewPolicy(dx=15.0, dy=0.0),
    )

    result = stitcher.stitch(reader, stack_order=StackOrder.BOTH)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], Image)
    assert isinstance(result[1], Image)
    assert result[0].size == result[1].size


def test_stitch_invokes_on_progress_callback(synthetic_sequence: list[Frame]):
    """Verify that configured on_progress callback is invoked for each aligned frame."""
    progress_log: list[tuple[int, int]] = []

    def log_progress(current: int, total: int, alignment: AlignmentResult) -> None:
        progress_log.append((current, total))

    reader = _MockFrameReader(synthetic_sequence)
    stitcher = SceneStitcher(
        handlers=[TranslationHandler()],
        view_policy=_MockViewPolicy(),
        on_progress=log_progress,
    )

    stitcher.stitch(reader)

    assert len(progress_log) == 2
    assert progress_log[0] == (2, 3)
    assert progress_log[1] == (3, 3)


def test_from_default_configures_default_handlers_and_policy():
    """Verify that from_default factory initializes scale, rotation, and translation handlers."""
    stitcher = SceneStitcher.from_default()

    assert len(stitcher.handlers) == 3
    assert isinstance(stitcher.handlers[0], ScaleHandler)
    assert isinstance(stitcher.handlers[1], RotationHandler)
    assert isinstance(stitcher.handlers[2], TranslationHandler)


def test_from_default_forwards_threshold_parameters():
    """Verify that from_default propagates custom threshold parameters to handlers and estimator."""
    stitcher = SceneStitcher.from_default(
        rotate_threshold=0.25,
        scale_threshold=0.005,
        translation_threshold=2.0,
        fast_threshold=7,
    )

    scale_handler = stitcher.handlers[0]
    rot_handler = stitcher.handlers[1]
    trans_handler = stitcher.handlers[2]
    policy = stitcher.view_policy
    assert isinstance(scale_handler, ScaleHandler)
    assert scale_handler.threshold == 0.005
    assert isinstance(rot_handler, RotationHandler)
    assert rot_handler.threshold == 0.25
    assert isinstance(trans_handler, TranslationHandler)
    assert trans_handler.threshold == 2.0
    assert isinstance(policy, AdaptiveViewPolicy)
    estimator = policy._estimator
    assert isinstance(estimator, OrbTransformEstimator)
    assert estimator.rotate_threshold == 0.25
    assert estimator.scale_threshold == 0.005
    assert estimator.fast_threshold == 7


class _MockContextAccumulator(FrameAccumulator):
    """Mock accumulator capturing pushed StitchContext instances."""

    def __init__(self, base_layer: Layer) -> None:
        self._base = base_layer
        self.pushed_contexts: list[StitchContext] = []

    def push(self, context: StitchContext) -> None:
        self.pushed_contexts.append(context)

    @property
    def reference_layer(self) -> Layer:
        return self._base

    def result(self) -> Image:
        return self._base.edits[0].image


def test_stitch_passes_stitch_context_to_accumulator(
    synthetic_sequence: list[Frame],
    monkeypatch: pytest.MonkeyPatch,
):
    """Verify that stitcher constructs and forwards StitchContext to the accumulator."""
    mock_acc: list[_MockContextAccumulator] = []

    def mock_create(*args, **kwargs) -> _MockContextAccumulator:
        acc = _MockContextAccumulator(args[1])
        mock_acc.append(acc)
        return acc

    monkeypatch.setattr("anifuse.stitcher.create_accumulator", mock_create)

    reader = _MockFrameReader(synthetic_sequence)
    stitcher = SceneStitcher(
        handlers=[TranslationHandler()],
        view_policy=_MockViewPolicy(dx=15.0, dy=-5.0),
    )

    stitcher.stitch(reader)

    acc = mock_acc[0]
    first_ctx = acc.pushed_contexts[0]
    assert len(acc.pushed_contexts) == 2
    assert isinstance(first_ctx, StitchContext)
    assert first_ctx.base_region == Region.from_size(100, 100)
    assert first_ctx.incoming_region == Region.from_size(100, 100)
    assert first_ctx.motion.dx == 15.0
    assert first_ctx.motion.dy == -5.0
    assert first_ctx.frame_idx == 2


def test_stitch_pipeline_with_rotation_guarantees_fast_path(
    synthetic_pattern_frame: Image,
):
    """Verify that stitching frames with rotation takes the fast-path without warp_patch."""
    frame1 = Frame(idx=1, image=synthetic_pattern_frame)
    frame2 = Frame(
        idx=2,
        image=transform_image(synthetic_pattern_frame, angle=5.0),
    )
    reader = _MockFrameReader([frame1, frame2])
    stitcher = SceneStitcher.from_default()

    with patch("anicrop.render.warp_patch", wraps=warp_patch) as mock_warp:
        result = stitcher.stitch(reader, stack_order=StackOrder.FIRST_ON_TOP)

        assert isinstance(result, Image)
        mock_warp.assert_not_called()


def test_stitch_pipeline_with_scale_guarantees_fast_path(
    synthetic_pattern_frame: Image,
):
    """Verify that stitching frames with scale takes the fast-path without warp_patch."""
    scaled_arr = resize_image(synthetic_pattern_frame[...], scale=1.1)
    frame1 = Frame(idx=1, image=synthetic_pattern_frame)
    frame2 = Frame(
        idx=2,
        image=Image(scaled_arr, synthetic_pattern_frame.format),
    )
    reader = _MockFrameReader([frame1, frame2])
    stitcher = SceneStitcher.from_default()

    with patch("anicrop.render.warp_patch", wraps=warp_patch) as mock_warp:
        result = stitcher.stitch(reader, stack_order=StackOrder.FIRST_ON_TOP)

        assert isinstance(result, Image)
        mock_warp.assert_not_called()
