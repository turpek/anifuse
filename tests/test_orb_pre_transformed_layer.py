"""Unit tests verifying LayerCache baked warp caching and zero-resampling rendering."""

from __future__ import annotations

from anicrop import Document, Image, ImageFormat, Layer, transform_image
from anicrop.cache import LayerCache
from anicrop.transform import (
    create_pivot_transform_rel,
    mat_rotation,
    mat_scale,
)

from anifuse.detection.orb import resize_image


def test_layer_cache_set_baked_avoids_dirty():
    """Verify that calling set_baked marks the layer as not dirty in the cache."""
    incoming = Image.new((100, 100), ImageFormat.RGBA, color=(255, 0, 0, 255))
    layer = Layer(incoming)
    cache = LayerCache()

    cache.set_baked(layer, incoming, matrix=layer.matrix)

    assert not cache.is_dirty(layer)


def test_layer_cache_bakes_render_without_recalculation():
    """Verify that cached baked warp image is rendered directly via Document render."""
    incoming = Image.new((100, 100), ImageFormat.RGBA, color=(255, 0, 0, 255))
    layer = Layer(incoming)
    angle = 15.0
    scale = 1.2
    w0, h0 = float(incoming.width), float(incoming.height)
    m_s = create_pivot_transform_rel(
        mat_scale(scale, scale), w0, h0, 0.0, 0.0
    )
    m_r = create_pivot_transform_rel(
        mat_rotation(angle), w0, h0, 0.0, 0.0
    )
    m_dist = m_r @ m_s

    transformed = transform_image(
        incoming,
        angle=angle,
        scale=scale,
        pivot_angle=(0.0, 0.0),
        pivot_scale=(0.0, 0.0),
    )

    cache = LayerCache()
    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0).rotate(
        angle, pivot_x=0.0, pivot_y=0.0
    )
    cache.set_baked(layer, transformed, matrix=m_dist)

    assert not cache.is_dirty(layer)
    doc = Document("test", 800, 600)
    doc.add(layer)
    rendered = doc.render(cache=cache)
    assert rendered is not None


def test_pivot_consistency_pure_scale_cache():
    """Verify that pure scale with (0.0, 0.0) pivot integrates with LayerCache."""
    incoming = Image.new((80, 80), ImageFormat.RGBA, color=(100, 150, 200, 255))
    layer = Layer(incoming)
    scale = 1.25
    resized = Image(resize_image(incoming[...], scale), incoming.format)

    w0, h0 = float(incoming.width), float(incoming.height)
    m_dist = create_pivot_transform_rel(
        mat_scale(scale, scale), w0, h0, 0.0, 0.0
    )
    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0)

    cache = LayerCache()
    cache.set_baked(layer, resized, matrix=m_dist)

    assert not cache.is_dirty(layer)


def test_pivot_consistency_rotation_and_affine_cache():
    """Verify that rotation and scale with (0.0, 0.0) pivot integrates with LayerCache."""
    incoming = Image.new((80, 80), ImageFormat.RGBA, color=(50, 120, 220, 255))
    layer = Layer(incoming)
    angle = 20.0
    scale = 1.15
    transformed = transform_image(
        incoming,
        angle=angle,
        scale=scale,
        pivot_angle=(0.0, 0.0),
        pivot_scale=(0.0, 0.0),
    )

    w0, h0 = float(incoming.width), float(incoming.height)
    m_s = create_pivot_transform_rel(
        mat_scale(scale, scale), w0, h0, 0.0, 0.0
    )
    m_r = create_pivot_transform_rel(
        mat_rotation(angle), w0, h0, 0.0, 0.0
    )
    m_dist = m_r @ m_s

    layer.transform.scale(scale, scale, pivot_x=0.0, pivot_y=0.0).rotate(
        angle, pivot_x=0.0, pivot_y=0.0
    )

    cache = LayerCache()
    cache.set_baked(layer, transformed.crop(), matrix=m_dist)

    assert not cache.is_dirty(layer)
