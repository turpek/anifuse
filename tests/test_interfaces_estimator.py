"""Tests for Estimator interface and MotionEstimate dataclass."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from anicrop.cache import AbstractLayerCache, LayerCache
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.layer import Layer

from anifuse.interfaces import Estimator, MotionEstimate


class DummyEstimator(Estimator):
    def estimate(
        self,
        ref: Image,
        layer: Layer,
        cache: AbstractLayerCache,
        mask: np.ndarray | None = None,
    ) -> MotionEstimate:
        return MotionEstimate(dx=10.0, dy=-5.0)


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


def test_concrete_estimator_returns_estimate():
    """Verify that concrete Estimator implementation returns expected MotionEstimate output."""
    dummy_ref = Image.new((50, 50), ImageFormat.RGB)
    dummy_layer = Layer(Image.new((50, 50), ImageFormat.RGB))
    cache = LayerCache()
    estimator = DummyEstimator()

    estimate = estimator.estimate(dummy_ref, dummy_layer, cache=cache)

    assert isinstance(estimate, MotionEstimate)
    assert estimate.dx == 10.0
    assert estimate.dy == -5.0
