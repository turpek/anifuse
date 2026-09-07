"""Tests for Estimator interface and MotionEstimate dataclass."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from anifuse.interfaces import Estimator, MotionEstimate


class DummyEstimator(Estimator):
    def estimate(
        self, ref: np.ndarray, incoming: np.ndarray
    ) -> tuple[MotionEstimate, np.ndarray]:
        return MotionEstimate(dx=10.0, dy=-5.0), incoming


def test_estimator_cannot_be_instantiated_directly():
    """Verify that Estimator is an abstract class and cannot be directly instantiated."""
    with pytest.raises(TypeError):
        Estimator()  # type: ignore[abstract]


def test_motion_estimate_default_values():
    """Verify default geometric values and confidence in MotionEstimate."""
    estimate = MotionEstimate()

    assert estimate.dx == 0.0
    assert estimate.dy == 0.0
    assert estimate.angle == 0.0
    assert estimate.scale == 1.0
    assert estimate.confidence == 1.0


def test_motion_estimate_is_immutable():
    """Verify that MotionEstimate fields cannot be mutated after instantiation."""
    estimate = MotionEstimate(dx=5.0)

    with pytest.raises(FrozenInstanceError):
        estimate.dx = 10.0  # type: ignore[misc]


def test_concrete_estimator_returns_estimate_and_array():
    """Verify that concrete Estimator implementation returns expected tuple output."""
    dummy_ref = np.zeros((50, 50), dtype=np.uint8)
    dummy_incoming = np.ones((50, 50), dtype=np.uint8)
    estimator = DummyEstimator()

    estimate, result_arr = estimator.estimate(dummy_ref, dummy_incoming)

    assert isinstance(estimate, MotionEstimate)
    assert estimate.dx == 10.0
    assert estimate.dy == -5.0
    assert result_arr is dummy_incoming
