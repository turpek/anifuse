from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.spatial import Region

from anifuse.interfaces import (
    AlignmentError,
    AlignmentResult,
    MotionEstimate,
    Section,
    ViewPolicy,
)


class _DummyConcretePolicy(ViewPolicy):
    """Dummy concrete policy for testing interface compliance."""

    def resolve(
        self,
        base: Image,
        incoming: Image,
        sections: Iterable[Section],
        frame_idx: int = 0,
    ) -> tuple[AlignmentResult, np.ndarray]:
        for sec in sections:
            return (
                AlignmentResult(ref=sec.ref, motion=MotionEstimate(dx=10.0, dy=5.0)),
                incoming[...],
            )
        raise AlignmentError("No sections available")


def test_section_stores_ref_and_view():
    """Verify that Section correctly stores ref and view Region instances."""
    ref_reg = Region.from_rect(100.0, 50.0, 1920.0, 1080.0)
    view_reg = Region.from_rect(0.0, 0.0, 1920.0, 1080.0)

    sec = Section(ref=ref_reg, view=view_reg)

    assert sec.ref == ref_reg
    assert sec.view == view_reg


def test_section_is_frozen_and_immutable():
    """Verify that Section cannot be mutated after instantiation."""
    sec = Section(
        ref=Region.from_rect(0, 0, 10, 10), view=Region.from_rect(0, 0, 10, 10)
    )

    with pytest.raises(AttributeError):
        sec.ref = Region.from_rect(5, 5, 10, 10)  # type: ignore[misc]


def test_alignment_result_stores_attributes_correctly():
    """Verify that AlignmentResult correctly stores ref Region and MotionEstimate."""
    region = Region.from_rect(10.0, 20.0, 100.0, 200.0)
    motion = MotionEstimate(dx=5.0, dy=-3.0, angle=1.5, scale=1.02, confidence=0.85)

    result = AlignmentResult(ref=region, motion=motion)

    assert result.ref == region
    assert result.motion == motion


def test_alignment_result_is_frozen_and_immutable():
    """Verify that AlignmentResult cannot be mutated after instantiation."""
    region = Region.from_rect(0.0, 0.0, 50.0, 50.0)
    motion = MotionEstimate(dx=0.0, dy=0.0)
    result = AlignmentResult(ref=region, motion=motion)

    with pytest.raises(AttributeError):
        result.ref = Region.from_rect(10.0, 10.0, 50.0, 50.0)  # type: ignore[misc]


def test_alignment_error_is_subclass_of_runtime_error():
    """Verify that AlignmentError inherits from RuntimeError."""
    err = AlignmentError("Test alignment failure")

    assert isinstance(err, RuntimeError)


def test_view_policy_cannot_be_instantiated_directly():
    """Verify that ViewPolicy raises TypeError when instantiated without implementing resolve."""
    with pytest.raises(TypeError):
        ViewPolicy()  # type: ignore[abstract]


def test_concrete_view_policy_implements_resolve_protocol():
    """Verify that a concrete ViewPolicy subclass can resolve an alignment."""
    base_img = Image(np.zeros((100, 100, 3), dtype=np.uint8), ImageFormat.RGB)
    incoming_img = Image(np.zeros((50, 50, 3), dtype=np.uint8), ImageFormat.RGB)
    sec = Section(
        ref=Region.from_rect(0, 0, 50, 50), view=Region.from_rect(0, 0, 50, 50)
    )

    policy = _DummyConcretePolicy()
    alignment, returned_arr = policy.resolve(base_img, incoming_img, [sec])

    assert isinstance(alignment, AlignmentResult)
    assert isinstance(returned_arr, np.ndarray)
    assert alignment.ref == sec.ref
    assert alignment.motion.dx == 10.0
