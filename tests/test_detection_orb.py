"""Tests for ORB feature-based estimators and auxiliary functions."""

import cv2
import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image

from anifuse.detection import (
    OrbRotationEstimator,
    OrbScaleEstimator,
    OrbTransformEstimator,
    OrbTranslationEstimator,
    discrete_mode,
    resize_image,
    rotate_image,
)
from anifuse.interfaces import MotionEstimate


@pytest.fixture
def synthetic_pattern_frame() -> Image:
    """Generate a synthetic 200x200 frame with high-contrast distinct geometric features."""
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (60, 60), (255, 255, 255), -1)
    cv2.circle(img, (150, 50), 25, (200, 200, 200), -1)
    cv2.circle(img, (80, 140), 30, (180, 180, 180), -1)
    cv2.rectangle(img, (130, 130), (180, 180), (220, 220, 220), -1)
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


def test_rotate_image_expands_dimensions():
    """Verify that rotate_image expands the bounding box when rotating non-zero angles."""
    mat = np.zeros((100, 100, 3), dtype=np.uint8)

    rotated = rotate_image(mat, angle=45.0, scale=1.0)

    assert rotated.shape[0] > 100
    assert rotated.shape[1] > 100


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
    assert returned_frame is shifted_frame
    assert estimate.dx == pytest.approx(shift_x, abs=2.0)
    assert estimate.dy == pytest.approx(shift_y, abs=2.0)


def test_orb_translation_estimator_returns_zero_confidence_on_blank_frames():
    """Verify that OrbTranslationEstimator returns zero confidence when no keypoints exist."""
    blank_ref = Image.new((100, 100), ImageFormat.RGB)
    blank_incoming = Image.new((100, 100), ImageFormat.RGB)

    estimator = OrbTranslationEstimator()
    estimate, returned_frame = estimator.estimate(blank_ref, blank_incoming)

    assert estimate.confidence == 0.0
    assert returned_frame is blank_incoming


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
    assert isinstance(returned_frame, Image)
    assert estimate.dx == pytest.approx(shift_x, abs=2.0)
    assert estimate.dy == pytest.approx(shift_y, abs=2.0)


def test_orb_transform_estimator_detects_rotation_and_prealigns_frame(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbTransformEstimator triggers 2-stage alignment when rotation is present."""
    rotated_arr = rotate_image(synthetic_pattern_frame[...], angle=5.0, scale=1.0)
    rotated_frame = Image(rotated_arr, synthetic_pattern_frame.format)

    estimator = OrbTransformEstimator(max_features=2000)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, rotated_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Image)
    assert estimate.confidence > 0.0
    assert estimate.angle == 0.0
    assert estimate.scale == 1.0


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


def test_orb_estimators_default_init_inherits_config_thresholds():
    """Verify that estimators without explicit thresholds inherit global config tolerances."""
    transform_est = OrbTransformEstimator()
    rot_est = OrbRotationEstimator()
    scale_est = OrbScaleEstimator()

    assert transform_est.rotate_threshold == 0.10
    assert transform_est.scale_threshold == 0.0010
    assert transform_est.fast_threshold == 10
    assert rot_est.rotate_threshold == 0.10
    assert rot_est.fast_threshold == 10
    assert scale_est.scale_threshold == 0.0010
    assert scale_est.fast_threshold == 10


def test_orb_scale_estimator_detects_scale_with_zero_angle(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbScaleEstimator resizes the incoming frame and always returns zero angle."""
    scaled_arr = resize_image(synthetic_pattern_frame[...], scale=1.1)
    scaled_frame = Image(scaled_arr, synthetic_pattern_frame.format)

    estimator = OrbScaleEstimator(max_features=2000, scale_threshold=0.0010)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, scaled_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Image)
    assert estimate.angle == 0.0
    assert estimate.scale == 1.0


def test_orb_rotation_estimator_detects_rotation(
    synthetic_pattern_frame: Image,
):
    """Verify that OrbRotationEstimator triggers rotation alignment when angle exceeds threshold."""
    rotated_arr = rotate_image(synthetic_pattern_frame[...], angle=5.0, scale=1.0)
    rotated_frame = Image(rotated_arr, synthetic_pattern_frame.format)

    estimator = OrbRotationEstimator(max_features=2000, rotate_threshold=0.10)
    estimate, returned_frame = estimator.estimate(synthetic_pattern_frame, rotated_frame)

    assert isinstance(estimate, MotionEstimate)
    assert isinstance(returned_frame, Image)
    assert estimate.angle == 0.0
    assert estimate.scale == 1.0
