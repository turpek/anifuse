"""Geometric transformation handlers applying estimated camera motion to anicrop Layers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anifuse.config import config
from anifuse.interfaces.handler import TransformHandler

if TYPE_CHECKING:
    from anicrop.layer import Layer

    from anifuse.interfaces.view_policy import AlignmentResult


class RotationHandler(TransformHandler):
    """Counter-rotates target layer around pivot when estimated angle exceeds threshold."""

    def __init__(
        self,
        threshold: float | None = None,
        pivot_x: float = 0.0,
        pivot_y: float = 0.0,
    ) -> None:
        """Initialize handler with rotation deadzone threshold and pivot coordinates."""
        self.threshold = (
            config.rotate_threshold if threshold is None else threshold
        )
        self.pivot_x = pivot_x
        self.pivot_y = pivot_y

    def apply(self, target: Layer, alignment: AlignmentResult) -> None:
        """Counter-rotate target layer around pivot if angle exceeds threshold."""
        angle = alignment.motion.angle
        if abs(angle) > self.threshold:
            target.transform.rotate(
                -angle, pivot_x=self.pivot_x, pivot_y=self.pivot_y
            )


class ScaleHandler(TransformHandler):
    """Counter-scales target layer around pivot when estimated scale deviation exceeds threshold."""

    def __init__(
        self,
        threshold: float | None = None,
        pivot_x: float = 0.0,
        pivot_y: float = 0.0,
    ) -> None:
        """Initialize handler with scale deadzone threshold and pivot coordinates."""
        self.threshold = (
            config.scale_threshold if threshold is None else threshold
        )
        self.pivot_x = pivot_x
        self.pivot_y = pivot_y

    def apply(self, target: Layer, alignment: AlignmentResult) -> None:
        """Counter-scale target layer around pivot if scale deviation exceeds threshold."""
        scale = alignment.motion.scale
        if abs(1.0 - scale) > self.threshold and scale > 0:
            target.transform.scale(
                1.0 / scale, 1.0 / scale, pivot_x=self.pivot_x, pivot_y=self.pivot_y
            )


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
