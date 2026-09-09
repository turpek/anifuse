"""Geometric transformation handlers applying estimated camera motion to anicrop Layers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anifuse.interfaces.handler import TransformHandler

if TYPE_CHECKING:
    from anicrop.layer import Layer

    from anifuse.interfaces.view_policy import AlignmentResult


class TranslationHandler(TransformHandler):
    """Translates target layer to aligned canvas coordinates compensating for AABB rotation offsets."""

    def __init__(self, threshold: float = 0.0) -> None:
        """Initialize handler with translation deadzone threshold."""
        self.threshold = threshold

    def apply(self, target: Layer, alignment: AlignmentResult) -> None:
        """Translate target layer to canvas coordinates compensating for AABB rotation offsets."""
        dx = (
            alignment.motion.dx
            if abs(alignment.motion.dx) > self.threshold
            else 0.0
        )
        dy = (
            alignment.motion.dy
            if abs(alignment.motion.dy) > self.threshold
            else 0.0
        )
        target_offset = alignment.ref - target.global_region.top_left - (dx, dy)
        target.transform.translate(*target_offset.top_left)


class HorizontalTranslationHandler(TransformHandler):
    """Translates target layer along the X axis only, forcing dy to 0.0."""

    def __init__(self, threshold: float = 0.0) -> None:
        """Initialize handler with translation deadzone threshold."""
        self.threshold = threshold

    def apply(self, target: Layer, alignment: AlignmentResult) -> None:
        """Translate target layer horizontally, keeping dy locked to 0.0."""
        dx = (
            alignment.motion.dx
            if abs(alignment.motion.dx) > self.threshold
            else 0.0
        )
        target_offset = alignment.ref - target.global_region.top_left - (dx, 0.0)
        target.transform.translate(*target_offset.top_left)


class VerticalTranslationHandler(TransformHandler):
    """Translates target layer along the Y axis only, forcing dx to 0.0."""

    def __init__(self, threshold: float = 0.0) -> None:
        """Initialize handler with translation deadzone threshold."""
        self.threshold = threshold

    def apply(self, target: Layer, alignment: AlignmentResult) -> None:
        """Translate target layer vertically, keeping dx locked to 0.0."""
        dy = (
            alignment.motion.dy
            if abs(alignment.motion.dy) > self.threshold
            else 0.0
        )
        target_offset = alignment.ref - target.global_region.top_left - (0.0, dy)
        target.transform.translate(*target_offset.top_left)
