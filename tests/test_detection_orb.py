"""Tests for ORB feature-based estimators and auxiliary functions."""

import cv2
import numpy as np
import pytest
from anicrop import Layer, transform_image
from anicrop.enums import ImageFormat
from anicrop.image import Image

from anifuse.detection import (
    OrbRotationEstimator,
    OrbScaleEstimator,
    OrbTransformEstimator,
    OrbTranslationEstimator,
    discrete_mode,
    resize_image,
)
from anifuse.interfaces import MotionEstimate


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


def test_discrete_mode_calculates_dominant_values():
    """Verify that discrete_mode computes the mode along each axis correctly."""
    diff = np.array([[10, 5], [10, 5], [10, 2], [3, 5]], dtype=int)

    delx, dely = discrete_mode(diff)

    assert delx == 10.0
    assert dely == 5.0


def test_discrete_mode_returns_zeros_on_empty_input():
    """Verify that discrete_mode returns (0.0, 0.0) when given an empty array."""
    empty_diff = np.empty((0, 2), dtype=int)

    delx, dely = discrete_mode(empty_diff)

    assert delx == 0.0
    assert dely == 0.0


def test_orb_translation_estimator_detects_shift(synthetic_pattern_frame: Image):
    """Verify that OrbTranslationEstimator detects a pure 2D translation offset."""
    arr = synthetic_pattern_frame[...]
    h, w = arr.shape[:2]
    shift_x, shift_y = 10, -5
    shifted_arr = np.zeros_like(arr)
    shifted_arr[0: h + shift_y, shift_x:w] = arr[-shift_y:h, 0: w - shift_x]
    shifted_frame = Image(shifted_arr, synthetic_pattern_frame.format)

    estimator = OrbTranslationEstimator(max_features=1000)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, shifted_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Layer)
    assert returned_frame.edits[0].image is shifted_frame
    assert estimate.dx == pytest.approx(shift_x, abs=2.0)
    assert estimate.dy == pytest.approx(shift_y, abs=2.0)


def test_orb_translation_estimator_returns_zero_confidence_on_blank_frames():
    """Verify that OrbTranslationEstimator returns zero confidence when no keypoints exist."""
    blank_ref = Image.new((100, 100), ImageFormat.RGB)
    blank_incoming = Image.new((100, 100), ImageFormat.RGB)

    estimator = OrbTranslationEstimator()
    estimate, returned_frame = estimator.estimate(blank_ref, blank_incoming)

    assert estimate.confidence == 0.0
    assert isinstance(returned_frame, Layer)
    assert returned_frame.edits[0].image is blank_incoming


def test_orb_transform_estimator_detects_pure_translation(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbTransformEstimator detects translation without triggering rotation."""
    arr = synthetic_pattern_frame[...]
    h, w = arr.shape[:2]
    shift_x, shift_y = 8, 8
    shifted_arr = np.zeros_like(arr)
    shifted_arr[shift_y:h, shift_x:w] = arr[0: h - shift_y, 0: w - shift_x]
    shifted_frame = Image(shifted_arr, synthetic_pattern_frame.format)

    estimator = OrbTransformEstimator(max_features=1000)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, shifted_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Layer)
    assert estimate.dx == pytest.approx(shift_x, abs=2.0)
    assert estimate.dy == pytest.approx(shift_y, abs=2.0)


def test_orb_transform_estimator_detects_rotation_and_prealigns_frame(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbTransformEstimator triggers 2-stage alignment when rotation is present."""
    rotated_frame = transform_image(synthetic_pattern_frame, angle=5.0)

    estimator = OrbTransformEstimator(max_features=2000)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, rotated_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Layer)
    assert estimate.confidence > 0.0
    assert abs(estimate.angle) == pytest.approx(5.0, abs=1.0)
    assert estimate.scale == pytest.approx(1.0, abs=0.05)


def test_orb_translation_estimator_respects_mask(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbTranslationEstimator detects zero features when mask is all zeros."""
    mask = np.zeros(
        (synthetic_pattern_frame.height, synthetic_pattern_frame.width), dtype=np.uint8
    )

    estimator = OrbTranslationEstimator(max_features=1000)
    estimate, _ = estimator.estimate(
        synthetic_pattern_frame, synthetic_pattern_frame, mask=mask
    )

    assert estimate.confidence == 0.0


def test_resize_image_scales_dimensions_orthogonally():
    """Verify that resize_image scales width and height proportionally without rotation."""
    mat = np.zeros((100, 200, 3), dtype=np.uint8)

    scaled = resize_image(mat, scale=1.5)

    assert scaled.shape == (150, 300, 3)


def test_orb_estimators_default_init_parameters():
    """Verify that estimators initialize with explicit default thresholds without relying on config."""
    transform_est = OrbTransformEstimator()
    rot_est = OrbRotationEstimator()
    scale_est = OrbScaleEstimator()
    trans_est = OrbTranslationEstimator()

    assert transform_est.rotate_threshold == 0.10
    assert transform_est.scale_threshold == 0.0010
    assert transform_est.fast_threshold == 10
    assert rot_est.rotate_threshold == 0.10
    assert rot_est.scale_threshold == 0.0010
    assert rot_est.fast_threshold == 10
    assert scale_est.scale_threshold == 0.0010
    assert scale_est.fast_threshold == 10
    assert trans_est.fast_threshold == 10


def test_orb_estimators_custom_parameters():
    """Verify that estimators accept custom parameters explicitly passed to constructor."""
    transform_est = OrbTransformEstimator(
        rotate_threshold=0.25, scale_threshold=0.005, fast_threshold=15
    )
    assert transform_est.rotate_threshold == 0.25
    assert transform_est.scale_threshold == 0.005
    assert transform_est.fast_threshold == 15


def test_orb_scale_estimator_detects_scale_with_zero_angle(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbScaleEstimator resizes the incoming frame and preserves estimated scale."""
    scaled_arr = resize_image(synthetic_pattern_frame[...], scale=1.1)
    scaled_frame = Image(scaled_arr, synthetic_pattern_frame.format)

    estimator = OrbScaleEstimator(max_features=2000, scale_threshold=0.0010)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, scaled_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Layer)
    assert estimate.angle == 0.0
    assert estimate.scale == pytest.approx(1.1, rel=0.05)


def test_orb_rotation_estimator_detects_rotation(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbRotationEstimator triggers rotation alignment and preserves estimated angle."""
    rotated_frame = transform_image(synthetic_pattern_frame, angle=5.0)

    estimator = OrbRotationEstimator(max_features=2000, rotate_threshold=0.10)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, rotated_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Layer)
    assert abs(estimate.angle) == pytest.approx(5.0, abs=1.0)
    assert estimate.scale == pytest.approx(1.0, abs=0.05)


def test_orb_extract_matches_reuses_cached_ref(synthetic_pattern_frame: Image):
    """Verify that _extract_matches reuses cached reference keypoints and descriptors."""
    estimator = OrbRotationEstimator(max_features=1000)
    gray = estimator._to_gray(synthetic_pattern_frame)

    kp1, desc1 = estimator._detect_and_compute(gray)
    assert kp1 is not None and desc1 is not None

    kp1_out, desc1_out, kp2, matches, valid = estimator._extract_matches(
        np.zeros((10, 10), dtype=np.uint8),
        gray,
        cached_ref=(kp1, desc1),
    )

    assert kp1_out is kp1
    assert desc1_out is desc1
    assert len(valid) >= 4
