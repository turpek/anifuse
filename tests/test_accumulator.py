"""Tests for canvas accumulation strategies."""

from __future__ import annotations

import numpy as np
import pytest
from anicrop.effect import Effect
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.layer import Layer

from anifuse.accumulator import (
    DualAccumulator,
    FirstOnTopAccumulator,
    LastOnTopAccumulator,
    apply_effects,
    create_accumulator,
)
from anifuse.interfaces.effect import AnifuseEffect, LayerTarget
from anifuse.interfaces.estimator import MotionEstimate
from anifuse.interfaces.stitcher import StackOrder, StitchContext


class _TrackingEffect(AnifuseEffect):
    def __init__(self, target: LayerTarget, name: str = "tracking") -> None:
        super().__init__(name=name)
        self.target = target
        self.recorded_top: Layer | None = None
        self.recorded_bottom: Layer | None = None

    def update(self, top: Layer, bottom: Layer) -> None:
        self.recorded_top = top
        self.recorded_bottom = bottom

    def get_padding(self) -> tuple[int, int, int, int]:
        return (0, 0, 0, 0)

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        return image

    def merge(self, other: Effect, matrix: np.ndarray) -> Effect | None:
        return None


@pytest.fixture
def red_layer() -> Layer:
    """Return a 100x100 solid red layer located at (0, 0)."""
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    arr[:, :] = [255, 0, 0, 255]
    img = Image(arr, ImageFormat.RGBA)
    return Layer(img, name="red")


@pytest.fixture
def blue_layer() -> Layer:
    """Return a 100x100 solid blue layer translated to (50, 50)."""
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    arr[:, :] = [0, 0, 255, 255]
    img = Image(arr, ImageFormat.RGBA)
    layer = Layer(img, name="blue")
    layer.transform.translate(50, 50)
    return layer


def _make_context(
    base: Layer, incoming: Layer, motion: MotionEstimate
) -> StitchContext:
    return StitchContext(
        base_region=base.region,
        incoming_region=incoming.region,
        base=base,
        incoming=incoming,
        motion=motion,
    )


def test_first_on_top_accumulator_keeps_base_pixels(
    red_layer: Layer, blue_layer: Layer
):
    """Verify that FirstOnTopAccumulator preserves initial frame pixels in overlap regions."""
    motion = MotionEstimate(dx=50.0, dy=50.0, confidence=1.0)
    accumulator = FirstOnTopAccumulator(red_layer)
    accumulator.push(_make_context(red_layer, blue_layer, motion))
    result_img = accumulator.result()
    arr = result_img[...]

    assert result_img.size == (150, 150)
    assert np.array_equal(arr[50, 50], [255, 0, 0, 255])
    assert np.array_equal(arr[120, 120], [0, 0, 255, 255])


def test_last_on_top_accumulator_overwrites_with_incoming_pixels(
    red_layer: Layer, blue_layer: Layer
):
    """Verify that LastOnTopAccumulator overwrites overlap regions with incoming frame pixels."""
    motion = MotionEstimate(dx=50.0, dy=50.0, confidence=1.0)
    accumulator = LastOnTopAccumulator(red_layer)
    accumulator.push(_make_context(red_layer, blue_layer, motion))
    result_img = accumulator.result()
    arr = result_img[...]

    assert result_img.size == (150, 150)
    assert np.array_equal(arr[50, 50], [0, 0, 255, 255])
    assert np.array_equal(arr[10, 10], [255, 0, 0, 255])


def test_dual_accumulator_produces_both_composites(
    red_layer: Layer, blue_layer: Layer
):
    """Verify that DualAccumulator outputs both first-on-top and last-on-top composites."""
    motion = MotionEstimate(dx=50.0, dy=50.0, confidence=1.0)
    accumulator = DualAccumulator(red_layer)
    accumulator.push(_make_context(red_layer, blue_layer, motion))
    first_img, last_img = accumulator.result()

    assert first_img.size == (150, 150)
    assert last_img.size == (150, 150)
    assert np.array_equal(first_img[...][50, 50], [255, 0, 0, 255])
    assert np.array_equal(last_img[...][50, 50], [0, 0, 255, 255])


@pytest.mark.parametrize(
    ("order", "expected_cls"),
    [
        (StackOrder.FIRST_ON_TOP, FirstOnTopAccumulator),
        (StackOrder.LAST_ON_TOP, LastOnTopAccumulator),
        (StackOrder.BOTH, DualAccumulator),
    ],
    ids=["first_on_top", "last_on_top", "both"],
)
def test_create_accumulator_instantiates_correct_type(
    red_layer: Layer, order: StackOrder, expected_cls: type
):
    """Verify that create_accumulator factory maps each StackOrder to its corresponding class."""
    accumulator = create_accumulator(order, red_layer)

    assert isinstance(accumulator, expected_cls)
    assert accumulator.reference_layer is not None


def test_create_accumulator_raises_on_invalid_order(red_layer: Layer):
    """Verify that create_accumulator raises ValueError on unsupported orders."""
    with pytest.raises(ValueError):
        create_accumulator("invalid_order", red_layer)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("target", "expect_on_top", "expect_on_bottom"),
    [
        (LayerTarget.TOP, True, False),
        (LayerTarget.BOTTOM, False, True),
        (LayerTarget.BOTH, True, True),
    ],
    ids=["target_top", "target_bottom", "target_both"],
)
def test_apply_effects_updates_and_binds_to_target_layers(
    red_layer: Layer,
    blue_layer: Layer,
    target: LayerTarget,
    expect_on_top: bool,
    expect_on_bottom: bool,
):
    """Verify that apply_effects passes top and bottom layers to effect.update and binds to targets."""
    effect = _TrackingEffect(target=target)

    apply_effects(red_layer, blue_layer, [effect])

    assert effect.recorded_top is red_layer
    assert effect.recorded_bottom is blue_layer
    assert (effect in red_layer.effects) is expect_on_top
    assert (effect in blue_layer.effects) is expect_on_bottom


@pytest.mark.parametrize(
    ("accumulator_cls", "expected_top_name", "expected_bottom_name"),
    [
        (FirstOnTopAccumulator, "red", "blue"),
        (LastOnTopAccumulator, "blue", "red"),
    ],
    ids=["first_on_top", "last_on_top"],
)
def test_accumulator_push_passes_correct_layer_order_to_effects(
    red_layer: Layer,
    blue_layer: Layer,
    accumulator_cls: type[FirstOnTopAccumulator | LastOnTopAccumulator],
    expected_top_name: str,
    expected_bottom_name: str,
):
    """Verify that accumulators pass semantic top and bottom layers to effect.update on push."""
    effect = _TrackingEffect(target=LayerTarget.TOP)
    accumulator = accumulator_cls(red_layer, effects=[effect])
    motion = MotionEstimate(dx=50.0, dy=50.0, confidence=1.0)

    accumulator.push(_make_context(red_layer, blue_layer, motion))

    assert effect.recorded_top is not None
    assert effect.recorded_bottom is not None
    assert effect.recorded_top.name == expected_top_name
    assert effect.recorded_bottom.name == expected_bottom_name
