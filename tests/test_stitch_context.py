"""Tests for StitchContext dataclass."""

from dataclasses import FrozenInstanceError

import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.layer import Layer
from anicrop.spatial import Region

import anifuse
import anifuse.interfaces
import anifuse.interfaces.effect
import anifuse.interfaces.stitcher
from anifuse.interfaces import MotionEstimate, StitchContext


def _make_dummy_layer(width: int = 100, height: int = 100) -> Layer:
    image = Image.new((width, height), ImageFormat.RGBA)
    return Layer(image)


def test_stitch_context_default_frame_idx():
    """Verify that StitchContext initializes correctly with default frame_idx."""
    base_reg = Region.from_size(100, 100)
    inc_reg = Region.from_size(100, 100)
    base_layer = _make_dummy_layer()
    inc_layer = _make_dummy_layer()
    motion = MotionEstimate(dx=10.0, dy=5.0)

    ctx = StitchContext(
        base_region=base_reg,
        incoming_region=inc_reg,
        base=base_layer,
        incoming=inc_layer,
        motion=motion,
    )

    assert ctx.base_region == base_reg
    assert ctx.incoming_region == inc_reg
    assert ctx.base is base_layer
    assert ctx.incoming is inc_layer
    assert ctx.motion == motion
    assert ctx.frame_idx == 0


def test_stitch_context_explicit_frame_idx():
    """Verify that StitchContext accepts an explicit frame_idx."""
    base_reg = Region.from_size(100, 100)
    inc_reg = Region.from_size(100, 100)
    base_layer = _make_dummy_layer()
    inc_layer = _make_dummy_layer()
    motion = MotionEstimate(dx=0.0, dy=0.0)

    ctx = StitchContext(
        base_region=base_reg,
        incoming_region=inc_reg,
        base=base_layer,
        incoming=inc_layer,
        motion=motion,
        frame_idx=42,
    )

    assert ctx.frame_idx == 42


def test_stitch_context_is_immutable():
    """Verify that StitchContext attributes cannot be mutated after instantiation."""
    base_reg = Region.from_size(100, 100)
    inc_reg = Region.from_size(100, 100)
    base_layer = _make_dummy_layer()
    inc_layer = _make_dummy_layer()
    motion = MotionEstimate(dx=0.0, dy=0.0)
    ctx = StitchContext(
        base_region=base_reg,
        incoming_region=inc_reg,
        base=base_layer,
        incoming=inc_layer,
        motion=motion,
    )

    with pytest.raises(FrozenInstanceError):
        ctx.frame_idx = 1  # type: ignore[misc]


def test_stitch_context_imports():
    """Verify that StitchContext is exported from all designated interface modules."""
    assert anifuse.StitchContext is StitchContext
    assert anifuse.interfaces.StitchContext is StitchContext
    assert anifuse.interfaces.effect.StitchContext is StitchContext
    assert anifuse.interfaces.stitcher.StitchContext is StitchContext
