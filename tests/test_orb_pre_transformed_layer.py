"""Unit tests verifying pre-transformed layer distortion cancellation and fast-path rendering."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from anicrop import Document, Image, ImageFormat, transform_image
from anicrop.render import Canvas, CanvasFrame, render_edit
from anicrop.transform import has_distortion

from anifuse.detection.orb import _create_pre_transformed_layer, resize_image


def test_analytical_distortion_cancellation():
    """Verify that layer transform and pre-transformed edit matrix analytically cancel distortion."""
    incoming = Image.new((100, 100), ImageFormat.RGBA, color=(255, 0, 0, 255))
    angle = 15.0
    scale = 1.2
    transformed = transform_image(
        incoming,
        angle=angle,
        scale=scale,
        pivot_angle=(0.0, 0.0),
        pivot_scale=(0.0, 0.0),
    )

    layer = _create_pre_transformed_layer(
        incoming,
        transformed,
        angle=angle,
        scale=scale,
        pivot_x=0.0,
        pivot_y=0.0,
    )
    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0).rotate(
        angle, pivot_x=0.0, pivot_y=0.0
    )

    edit = layer.edits[0]
    m_render = layer.matrix @ edit.matrix

    assert not has_distortion(m_render)


def test_pipeline_fast_path_without_warp_patch():
    """Verify that the renderer detects is_distorted as False and executes without calling warp_patch."""
    incoming = Image.new((100, 100), ImageFormat.RGBA, color=(255, 0, 0, 255))
    angle = 15.0
    scale = 1.2
    transformed = transform_image(
        incoming,
        angle=angle,
        scale=scale,
        pivot_angle=(0.0, 0.0),
        pivot_scale=(0.0, 0.0),
    )

    layer = _create_pre_transformed_layer(
        incoming,
        transformed,
        angle=angle,
        scale=scale,
        pivot_x=0.0,
        pivot_y=0.0,
    )
    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0).rotate(
        angle, pivot_x=0.0, pivot_y=0.0
    )

    with patch("anicrop.render.warp_patch") as mock_warp:
        doc = Document("test", 800, 600)
        doc.add(layer)
        doc.render()
        mock_warp.assert_not_called()


def test_pixel_fidelity_zero_resampling():
    """Verify bit-for-bit pixel equality between render output and pre-transformed buffer."""
    incoming = Image.new((100, 100), ImageFormat.RGBA, color=(255, 0, 0, 255))
    angle = 15.0
    scale = 1.2
    transformed = transform_image(
        incoming,
        angle=angle,
        scale=scale,
        pivot_angle=(0.0, 0.0),
        pivot_scale=(0.0, 0.0),
    )

    layer = _create_pre_transformed_layer(
        incoming,
        transformed,
        angle=angle,
        scale=scale,
        pivot_x=0.0,
        pivot_y=0.0,
    )
    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0).rotate(
        angle, pivot_x=0.0, pivot_y=0.0
    )

    frame = CanvasFrame(layer, Canvas(layer.global_region), local=False)
    result = render_edit(layer.edits[0], frame)
    assert result is not None
    rendered_image, _ = result

    np.testing.assert_array_equal(rendered_image[...], transformed[...])


def test_pivot_consistency_pure_scale():
    """Verify that pure scale with (0.0, 0.0) pivot produces zero distortion and exact pixels."""
    incoming = Image.new((80, 80), ImageFormat.RGBA, color=(100, 150, 200, 255))
    scale = 1.25
    resized = Image(resize_image(incoming[...], scale), incoming.format)

    layer = _create_pre_transformed_layer(
        incoming,
        resized,
        angle=0.0,
        scale=scale,
        pivot_x=0.0,
        pivot_y=0.0,
    )
    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0)

    edit = layer.edits[0]
    m_render = layer.matrix @ edit.matrix
    assert not has_distortion(m_render)

    frame = CanvasFrame(layer, Canvas(layer.global_region), local=False)
    result = render_edit(layer.edits[0], frame)
    assert result is not None
    rendered_image, _ = result

    np.testing.assert_array_equal(rendered_image[...], resized[...])


def test_pivot_consistency_rotation_and_affine():
    """Verify that rotation and scale with (0.0, 0.0) pivot produces zero distortion and exact pixels."""
    incoming = Image.new((80, 80), ImageFormat.RGBA, color=(50, 120, 220, 255))
    angle = 20.0
    scale = 1.15
    transformed = transform_image(
        incoming,
        angle=angle,
        scale=scale,
        pivot_angle=(0.0, 0.0),
        pivot_scale=(0.0, 0.0),
    )

    layer = _create_pre_transformed_layer(
        incoming,
        transformed,
        angle=angle,
        scale=scale,
        pivot_x=0.0,
        pivot_y=0.0,
    )
    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0).rotate(
        angle, pivot_x=0.0, pivot_y=0.0
    )

    edit = layer.edits[0]
    m_render = layer.matrix @ edit.matrix
    assert not has_distortion(m_render)

    frame = CanvasFrame(layer, Canvas(layer.global_region), local=False)
    result = render_edit(layer.edits[0], frame)
    assert result is not None
    rendered_image, _ = result

    np.testing.assert_array_equal(rendered_image[...], transformed[...])
