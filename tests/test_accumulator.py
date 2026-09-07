"""Tests for canvas accumulation strategies."""

from __future__ import annotations

import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.layer import Layer

from anifuse.accumulator import (
    DualAccumulator,
    FirstOnTopAccumulator,
    LastOnTopAccumulator,
    create_accumulator,
)
from anifuse.interfaces.stitcher import StackOrder


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


def test_first_on_top_accumulator_keeps_base_pixels(
    red_layer: Layer, blue_layer: Layer
):
    """Verify that FirstOnTopAccumulator preserves initial frame pixels in overlap regions."""
    accumulator = FirstOnTopAccumulator(red_layer)
    accumulator.push(blue_layer)
    result_img = accumulator.result()
    arr = result_img[...]

    assert result_img.size == (150, 150)
    assert np.array_equal(arr[50, 50], [255, 0, 0, 255])
    assert np.array_equal(arr[120, 120], [0, 0, 255, 255])


def test_last_on_top_accumulator_overwrites_with_incoming_pixels(
    red_layer: Layer, blue_layer: Layer
):
    """Verify that LastOnTopAccumulator overwrites overlap regions with incoming frame pixels."""
    accumulator = LastOnTopAccumulator(red_layer)
    accumulator.push(blue_layer)
    result_img = accumulator.result()
    arr = result_img[...]

    assert result_img.size == (150, 150)
    assert np.array_equal(arr[50, 50], [0, 0, 255, 255])
    assert np.array_equal(arr[10, 10], [255, 0, 0, 255])


def test_dual_accumulator_produces_both_composites(
    red_layer: Layer, blue_layer: Layer
):
    """Verify that DualAccumulator outputs both first-on-top and last-on-top composites."""
    accumulator = DualAccumulator(red_layer)
    accumulator.push(blue_layer)
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
