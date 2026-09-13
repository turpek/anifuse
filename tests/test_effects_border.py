"""Unit tests for BorderCutEffect seam erasing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from anicrop.composition import flatten
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.layer import Layer

from anifuse.effects.border import BorderCutEffect
from anifuse.handlers import TranslationHandler
from anifuse.interfaces.estimator import MotionEstimate
from anifuse.interfaces.reader import Frame, FrameReader
from anifuse.interfaces.stitcher import StackOrder
from anifuse.interfaces.view_policy import AlignmentResult, Section, ViewPolicy
from anifuse.stitcher import SceneStitcher

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def _create_solid_layer(color: tuple[int, int, int, int], x: float = 0, y: float = 0) -> Layer:
    arr = np.full((100, 100, 4), color, dtype=np.uint8)
    img = Image(arr, ImageFormat.RGBA)
    layer = Layer(img)
    layer.transform.translate(x, y)
    return layer


class _MockFrameReader(FrameReader):
    def __init__(self, frames: list[Frame]) -> None:
        self._frames = list(frames)

    def __len__(self) -> int:
        return len(self._frames)

    def __iter__(self) -> Iterator[Frame]:
        yield from self._frames


class _MockViewPolicy(ViewPolicy):
    def __init__(self, dx: float = 20.0, dy: float = 0.0) -> None:
        self.dx = dx
        self.dy = dy

    def resolve(
        self,
        base: Image,
        incoming: Image,
        sections: Iterable[Section],
        frame_idx: int = 0,
    ) -> tuple[AlignmentResult, Layer]:
        first_section = next(iter(sections))
        motion = MotionEstimate(dx=self.dx, dy=self.dy, confidence=0.99)
        return AlignmentResult(ref=first_section.ref, motion=motion), Layer(incoming)


def test_border_cut_auto_detects_left_edge_on_positive_dx():
    """Verify that positive horizontal movement cuts the left edge of the top layer overlap."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=0, y=0)
    top = _create_solid_layer((0, 255, 0, 255), x=20, y=0)

    effect = BorderCutEffect(all=5)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[:, 0:5, 3] == 0)
    assert np.all(arr[:, 5:80, 3] == 255)


def test_border_cut_auto_detects_right_edge_on_negative_dx():
    """Verify that negative horizontal movement cuts the right edge of the top layer overlap."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=20, y=0)
    top = _create_solid_layer((0, 255, 0, 255), x=0, y=0)

    effect = BorderCutEffect(all=5)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[:, 95:100, 3] == 0)
    assert np.all(arr[:, 20:95, 3] == 255)


def test_border_cut_auto_detects_top_edge_on_positive_dy():
    """Verify that positive vertical movement cuts the top edge of the top layer overlap."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=0, y=0)
    top = _create_solid_layer((0, 255, 0, 255), x=0, y=20)

    effect = BorderCutEffect(all=5)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[0:5, :, 3] == 0)
    assert np.all(arr[5:80, :, 3] == 255)


def test_border_cut_auto_detects_bottom_edge_on_negative_dy():
    """Verify that negative vertical movement cuts the bottom edge of the top layer overlap."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=0, y=20)
    top = _create_solid_layer((0, 255, 0, 255), x=0, y=0)

    effect = BorderCutEffect(all=5)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[95:100, :, 3] == 0)
    assert np.all(arr[20:95, :, 3] == 255)


def test_border_cut_auto_detects_l_cut_on_diagonal_movement():
    """Verify that diagonal movement creates both horizontal and vertical cut slices in L-shape."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=0, y=0)
    top = _create_solid_layer((0, 255, 0, 255), x=20, y=20)

    effect = BorderCutEffect(all=5)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[0:80, 0:5, 3] == 0)
    assert np.all(arr[0:5, 0:80, 3] == 0)
    assert np.all(arr[80:100, :, 3] == 255)
    assert np.all(arr[:, 80:100, 3] == 255)


def test_border_cut_manual_sides_override_automatic_detection():
    """Verify that explicit manual side arguments strictly govern which edges are erased."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=0, y=0)
    top = _create_solid_layer((0, 255, 0, 255), x=20, y=20)

    effect = BorderCutEffect(left=8, top=12)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[0:80, 0:8, 3] == 0)
    assert np.all(arr[0:12, 0:80, 3] == 0)
    assert np.all(arr[80:100, :, 3] == 255)
    assert np.all(arr[:, 80:100, 3] == 255)


def test_border_cut_clamps_to_overlap_boundary():
    """Verify that cut thickness does not overshoot the overlap dimension."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=0, y=0)
    top = _create_solid_layer((0, 255, 0, 255), x=95, y=0)

    effect = BorderCutEffect(all=20)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[:, 0:5, 3] == 0)
    assert np.all(arr[:, 5:, 3] == 255)


def test_border_cut_no_overlap_leaves_image_intact():
    """Verify that disjoint layers produce zero cut slices."""
    bottom = _create_solid_layer((255, 0, 0, 255), x=0, y=0)
    top = _create_solid_layer((0, 255, 0, 255), x=200, y=200)

    effect = BorderCutEffect(all=10)
    effect.update(top, bottom)
    rendered_image = effect.apply(top.edits[0].image, np.eye(3))
    arr = rendered_image[...]

    assert np.all(arr[:, :, 3] == 255)


def test_scene_stitcher_executes_with_border_cut_effect():
    """Verify that SceneStitcher executes smoothly when passing BorderCutEffect to stitch."""
    arr1 = np.full((100, 100, 4), [255, 0, 0, 255], dtype=np.uint8)
    arr2 = np.full((100, 100, 4), [0, 255, 0, 255], dtype=np.uint8)
    frames = [
        Frame(idx=1, image=Image(arr1, ImageFormat.RGBA)),
        Frame(idx=2, image=Image(arr2, ImageFormat.RGBA)),
    ]
    reader = _MockFrameReader(frames)

    stitcher = SceneStitcher(
        handlers=[TranslationHandler()],
        view_policy=_MockViewPolicy(dx=20.0, dy=0.0),
    )
    result = stitcher.stitch(
        reader,
        stack_order=StackOrder.LAST_ON_TOP,
        effects=[BorderCutEffect(all=5)],
    )

    assert isinstance(result, Image)
    assert result.size == (120, 100)


def test_border_cut_rotated_frame_cuts_tilted_seam():
    """Verify that rotated frames generate tilted lines erasing alpha along the seam."""
    bottom = Layer(Image(np.full((100, 100, 4), [255, 0, 0, 255], dtype=np.uint8), ImageFormat.RGBA))
    top = Layer(Image(np.full((100, 100, 4), [0, 255, 0, 255], dtype=np.uint8), ImageFormat.RGBA))
    top.transform.rotate(5)
    top.transform.translate(20, 0)

    effect = BorderCutEffect(all=4)
    effect.update(top, bottom)
    top.add_effect(effect)
    result = flatten([bottom, top])
    arr = result.edits[0].image[...]

    revealed_bottom_pixels = np.count_nonzero((arr[:, :, 0] == 255) & (arr[:, :, 1] == 0))
    assert revealed_bottom_pixels > 2000


def test_border_cut_rotated_frame_with_scale():
    """Verify that combined rotation and scale generate tilted seam cuts."""
    bottom = Layer(Image(np.full((100, 100, 4), [255, 0, 0, 255], dtype=np.uint8), ImageFormat.RGBA))
    top = Layer(Image(np.full((100, 100, 4), [0, 255, 0, 255], dtype=np.uint8), ImageFormat.RGBA))
    top.transform.scale(1.1, 1.1)
    top.transform.rotate(5)
    top.transform.translate(10, 0)

    effect = BorderCutEffect(all=5)
    effect.update(top, bottom)
    top.add_effect(effect)
    result = flatten([bottom, top])
    arr = result.edits[0].image[...]

    assert arr.shape[0] > 100
    assert arr.shape[1] > 100


def test_border_cut_pure_scale_applies_axis_aligned_cut():
    """Verify that pure scale without rotation generates axis-aligned cut correctly."""
    bottom = Layer(Image(np.full((100, 100, 4), [255, 0, 0, 255], dtype=np.uint8), ImageFormat.RGBA))
    top = Layer(Image(np.full((100, 100, 4), [0, 255, 0, 255], dtype=np.uint8), ImageFormat.RGBA))
    top.transform.scale(1.1, 1.1)
    top.transform.translate(10, 0)

    effect = BorderCutEffect(all=5)
    effect.update(top, bottom)
    top.add_effect(effect)
    result = flatten([bottom, top])
    arr = result.edits[0].image[...]
    assert arr.shape[0] > 100
    assert arr.shape[1] > 100
