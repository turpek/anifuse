"""Tests for CrossSections generator and AdaptiveViewPolicy implementation."""

from __future__ import annotations

import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.spatial import Region

from anifuse.interfaces import (
    AlignmentError,
    AlignmentResult,
    Estimator,
    MotionEstimate,
    Section,
    SectionGenerator,
)
from anifuse.mask import StaticMaskView
from anifuse.view_policy import (
    AdaptiveViewPolicy,
    CrossSections,
    GlobalSections,
)


class _MockEstimator(Estimator):
    """Mock estimator returning predetermined MotionEstimates by call count or section."""

    def __init__(self, confidences: list[float]) -> None:
        self.confidences = list(confidences)
        self.call_count = 0
        self.last_mask: np.ndarray | None = None

    def estimate(
        self,
        ref: Image,
        incoming: Image,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, Image]:
        self.last_mask = mask
        conf = (
            self.confidences[self.call_count]
            if self.call_count < len(self.confidences)
            else 0.0
        )
        self.call_count += 1
        return MotionEstimate(dx=10.0, dy=5.0, confidence=conf), incoming


@pytest.fixture
def canvas_image() -> Image:
    """Return a 2000x1000 synthetic canvas Image."""
    arr = np.zeros((1000, 2000, 3), dtype=np.uint8)
    return Image(arr, ImageFormat.RGB)


@pytest.fixture
def incoming_image() -> Image:
    """Return a 500x500 synthetic incoming frame Image."""
    arr = np.zeros((500, 500, 3), dtype=np.uint8)
    return Image(arr, ImageFormat.RGB)


def test_cross_sections_with_ellipsis_yields_full_canvas():
    """Verify that CrossSections yields full canvas when last_region is Ellipsis."""
    canvas_bounds = Region.from_rect(0, 0, 2000, 1000)
    cross = CrossSections(global_region=canvas_bounds, last_region=...)

    sections = list(cross)

    assert len(sections) == 1
    assert sections[0].ref == canvas_bounds
    assert sections[0].view == Region.from_rect(0, 0, 2000, 1000)


def test_cross_sections_yields_center_and_neighbors():
    """Verify that CrossSections yields center section followed by valid cross neighbors."""
    canvas_bounds = Region.from_rect(0, 0, 2000, 1000)
    last_region = Region.from_rect(500, 300, 400, 300)
    cross = CrossSections(global_region=canvas_bounds, last_region=last_region, step=100.0)

    sections = list(cross)

    assert len(sections) >= 5
    assert sections[0].ref == last_region
    assert sections[1].ref == Region.from_rect(600, 300, 400, 300)  # Right
    assert sections[2].ref == Region.from_rect(400, 300, 400, 300)  # Left
    assert sections[3].ref == Region.from_rect(500, 400, 400, 300)  # Down
    assert sections[4].ref == Region.from_rect(500, 200, 400, 300)  # Up


def test_cross_sections_skips_out_of_bounds_neighbors():
    """Verify that CrossSections skips candidate offsets that lie outside canvas bounds."""
    canvas_bounds = Region.from_rect(0, 0, 500, 500)
    last_region = Region.from_rect(0, 0, 500, 500)
    cross = CrossSections(global_region=canvas_bounds, last_region=last_region, step=450.0)

    sections = list(cross)

    assert all(sec.ref.width >= 100.0 and sec.ref.height >= 100.0 for sec in sections)


def test_cross_sections_sweeps_entire_canvas_grid():
    """Verify that CrossSections generates tiles spanning across the entire canvas."""
    canvas_bounds = Region.from_rect(0, 0, 2000, 1000)
    last_region = Region.from_rect(1500, 500, 400, 300)
    cross = CrossSections(global_region=canvas_bounds, last_region=last_region, step=500.0)

    sections = list(cross)

    assert len(sections) > 5
    assert any(sec.ref.top_left.x == 0.0 for sec in sections)


def test_adaptive_view_policy_returns_first_section_passing_threshold(
    canvas_image: Image, incoming_image: Image
):
    """Verify that AdaptiveViewPolicy returns immediately on first section meeting threshold."""
    estimator = _MockEstimator(confidences=[0.85, 0.90])
    policy = AdaptiveViewPolicy(estimator=estimator)
    sec1 = Section(Region.from_rect(0, 0, 200, 200), Region.from_rect(0, 0, 200, 200))
    sec2 = Section(Region.from_rect(200, 0, 200, 200), Region.from_rect(200, 0, 200, 200))

    alignment, ready_image = policy.resolve(canvas_image, incoming_image, [sec1, sec2])

    assert isinstance(alignment, AlignmentResult)
    assert alignment.ref == sec1.ref
    assert isinstance(ready_image, Image)
    assert ready_image is incoming_image
    assert estimator.call_count == 1


def test_adaptive_view_policy_evaluates_subsequent_sections_if_first_fails(
    canvas_image: Image, incoming_image: Image
):
    """Verify that AdaptiveViewPolicy evaluates second section if first fails threshold."""
    estimator = _MockEstimator(confidences=[0.10, 0.85])
    policy = AdaptiveViewPolicy(estimator=estimator)
    sec1 = Section(Region.from_rect(0, 0, 200, 200), Region.from_rect(0, 0, 200, 200))
    sec2 = Section(Region.from_rect(200, 0, 200, 200), Region.from_rect(200, 0, 200, 200))

    alignment, ready_image = policy.resolve(canvas_image, incoming_image, [sec1, sec2])

    assert alignment.ref == sec2.ref
    assert isinstance(ready_image, Image)
    assert ready_image is incoming_image
    assert estimator.call_count == 2


def test_adaptive_view_policy_raises_alignment_error_when_no_section_passes(
    canvas_image: Image, incoming_image: Image
):
    """Verify that AdaptiveViewPolicy raises AlignmentError when all candidate sections fail threshold."""
    estimator = _MockEstimator(confidences=[0.10, 0.05])
    policy = AdaptiveViewPolicy(estimator=estimator)
    sec1 = Section(Region.from_rect(0, 0, 200, 200), Region.from_rect(0, 0, 200, 200))
    sec2 = Section(Region.from_rect(200, 0, 200, 200), Region.from_rect(200, 0, 200, 200))

    with pytest.raises(AlignmentError):
        policy.resolve(canvas_image, incoming_image, [sec1, sec2], frame_idx=7)


def test_adaptive_view_policy_passes_mask_to_estimator(
    canvas_image: Image, incoming_image: Image
):
    """Verify that configured MaskView passes mask array to estimator."""
    mask_arr = np.ones((500, 500), dtype=np.uint8)
    mask_view = StaticMaskView(mask_arr)
    estimator = _MockEstimator(confidences=[0.9])
    policy = AdaptiveViewPolicy(estimator=estimator, mask_view=mask_view)
    sec = Section(Region.from_rect(0, 0, 200, 200), Region.from_rect(0, 0, 200, 200))

    policy.resolve(canvas_image, incoming_image, [sec])

    assert estimator.last_mask is mask_arr


def test_cross_sections_inherits_section_generator():
    """Verify that CrossSections is an instance of SectionGenerator."""
    canvas_bounds = Region.from_rect(0, 0, 1000, 500)
    cross = CrossSections(global_region=canvas_bounds)
    assert isinstance(cross, SectionGenerator)


def test_global_sections_inherits_section_generator():
    """Verify that GlobalSections is an instance of SectionGenerator."""
    canvas_bounds = Region.from_rect(0, 0, 1000, 500)
    global_sec = GlobalSections(global_region=canvas_bounds)
    assert isinstance(global_sec, SectionGenerator)


def test_global_sections_yields_full_canvas_region():
    """Verify that GlobalSections yields a single section covering the entire canvas."""
    canvas_bounds = Region.from_rect(100, 200, 1920, 1080)
    global_sec = GlobalSections(global_region=canvas_bounds)
    sections = list(global_sec)

    assert len(sections) == 1
    assert sections[0].ref == canvas_bounds
    assert sections[0].view == Region.from_size(1920, 1080)
