"""Tests for geometric transformation handlers."""

import numpy as np
from anicrop.layer import Layer
from anicrop.spatial import Region

from anifuse.handlers import (
    RotationHandler,
    ScaleHandler,
    TranslationHandler,
)
from anifuse.interfaces import AlignmentResult, MotionEstimate


def test_rotation_handler_applies_rotation_when_above_threshold():
    """Verify that RotationHandler applies counter-rotation when angle exceeds threshold."""
    layer = Layer(Region.from_rect(0, 0, 100, 100))
    alignment = AlignmentResult(
        ref=Region.from_rect(0, 0, 100, 100),
        motion=MotionEstimate(angle=5.0),
    )
    handler = RotationHandler(threshold=0.20, pivot_x=0.0, pivot_y=0.0)

    result = handler.apply(layer, alignment)

    assert result is None
    assert not np.allclose(layer.transform.matrix, np.eye(3))


def test_rotation_handler_skips_when_below_threshold():
    """Verify that RotationHandler leaves layer untouched when angle is within deadzone."""
    layer = Layer(Region.from_rect(0, 0, 100, 100))
    alignment = AlignmentResult(
        ref=Region.from_rect(0, 0, 100, 100),
        motion=MotionEstimate(angle=0.10),
    )
    handler = RotationHandler(threshold=0.20, pivot_x=0.0, pivot_y=0.0)

    result = handler.apply(layer, alignment)

    assert result is None
    assert np.allclose(layer.transform.matrix, np.eye(3))


def test_scale_handler_applies_scale_when_above_threshold():
    """Verify that ScaleHandler applies inverse scaling when scale exceeds threshold."""
    layer = Layer(Region.from_rect(0, 0, 100, 100))
    alignment = AlignmentResult(
        ref=Region.from_rect(0, 0, 100, 100),
        motion=MotionEstimate(scale=1.05),
    )
    handler = ScaleHandler(threshold=0.006, pivot_x=0.0, pivot_y=0.0)

    result = handler.apply(layer, alignment)

    assert result is None
    assert not np.allclose(layer.transform.matrix, np.eye(3))


def test_scale_handler_skips_when_below_threshold():
    """Verify that ScaleHandler leaves layer untouched when scale is within deadzone."""
    layer = Layer(Region.from_rect(0, 0, 100, 100))
    alignment = AlignmentResult(
        ref=Region.from_rect(0, 0, 100, 100),
        motion=MotionEstimate(scale=1.002),
    )
    handler = ScaleHandler(threshold=0.006, pivot_x=0.0, pivot_y=0.0)

    result = handler.apply(layer, alignment)

    assert result is None
    assert np.allclose(layer.transform.matrix, np.eye(3))


def test_translation_handler_positions_layer_at_offset():
    """Verify that TranslationHandler translates layer to the reference canvas offset."""
    layer = Layer(Region.from_rect(0, 0, 200, 200))
    ref_region = Region.from_rect(500, 600, 200, 200)
    alignment = AlignmentResult(
        ref=ref_region,
        motion=MotionEstimate(dx=50.0, dy=-30.0),
    )
    handler = TranslationHandler()

    result = handler.apply(layer, alignment)

    assert result is None
    assert layer.global_region.top_left == (450.0, 630.0)


def test_translation_handler_compensates_for_rotated_layer_aabb():
    """Verify that TranslationHandler subtracts layer global AABB offset from prior rotation."""
    layer = Layer(Region.from_rect(0, 0, 100, 100))
    layer.transform.rotate(90, pivot_x=0.0, pivot_y=0.0)
    ref_region = Region.from_rect(300, 400, 100, 100)
    alignment = AlignmentResult(
        ref=ref_region,
        motion=MotionEstimate(dx=10.0, dy=20.0),
    )
    handler = TranslationHandler()

    result = handler.apply(layer, alignment)

    assert result is None
    assert layer.global_region.top_left == (290.0, 380.0)


def test_translation_handler_respects_threshold():
    """Verify that TranslationHandler ignores sub-threshold displacement deltas."""
    layer = Layer(Region.from_rect(0, 0, 100, 100))
    ref_region = Region.from_rect(100, 100, 100, 100)
    alignment = AlignmentResult(
        ref=ref_region,
        motion=MotionEstimate(dx=0.5, dy=0.0),
    )
    handler = TranslationHandler(threshold=1.0)

    result = handler.apply(layer, alignment)

    assert result is None
    assert layer.global_region.top_left == (100.0, 100.0)
