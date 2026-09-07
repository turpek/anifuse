"""Concrete canvas accumulation strategies for composite frame stacking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anicrop.composition import clone_layer, flatten
from anicrop.enums import InterpMode

from anifuse.interfaces.stitcher import FrameAccumulator, StackOrder

if TYPE_CHECKING:
    from anicrop.image import Image
    from anicrop.layer import Layer


class FirstOnTopAccumulator(FrameAccumulator):
    """Accumulates frames with the initial canvas on top (incoming frames slide underneath)."""

    def __init__(
        self,
        base_layer: Layer,
        interp: InterpMode = InterpMode.LANCZOS,
    ) -> None:
        """Initialize accumulator with base layer and interpolation mode."""
        self._base = base_layer
        self._interp = interp

    def push(self, incoming: Layer) -> None:
        """Flatten incoming layer underneath the accumulated canvas."""
        self._base = flatten([incoming, self._base], interp=self._interp)

    @property
    def reference_layer(self) -> Layer:
        """Return the current base layer as spatial reference."""
        return self._base

    def result(self) -> Image:
        """Return the composite image of the accumulated canvas."""
        return self._base.edits[0].image


class LastOnTopAccumulator(FrameAccumulator):
    """Accumulates frames with the latest incoming frames on top (newer frames overwrite older)."""

    def __init__(
        self,
        base_layer: Layer,
        interp: InterpMode = InterpMode.LANCZOS,
    ) -> None:
        """Initialize accumulator with base layer and interpolation mode."""
        self._base = base_layer
        self._interp = interp

    def push(self, incoming: Layer) -> None:
        """Flatten incoming layer on top of the accumulated canvas."""
        self._base = flatten([self._base, incoming], interp=self._interp)

    @property
    def reference_layer(self) -> Layer:
        """Return the current base layer as spatial reference."""
        return self._base

    def result(self) -> Image:
        """Return the composite image of the accumulated canvas."""
        return self._base.edits[0].image


class DualAccumulator(FrameAccumulator):
    """Accumulates both first-on-top and last-on-top composites concurrently."""

    def __init__(
        self,
        base_layer: Layer,
        interp: InterpMode = InterpMode.LANCZOS,
    ) -> None:
        """Initialize accumulator with two cloned copies of the base layer."""
        self._first_on_top = clone_layer(base_layer)
        self._last_on_top = clone_layer(base_layer)
        self._interp = interp

    def push(self, incoming: Layer) -> None:
        """Update both first-on-top and last-on-top composites."""
        incoming_clone = clone_layer(incoming)
        self._first_on_top = flatten(
            [incoming, self._first_on_top], interp=self._interp
        )
        self._last_on_top = flatten(
            [self._last_on_top, incoming_clone], interp=self._interp
        )

    @property
    def reference_layer(self) -> Layer:
        """Return the first-on-top canvas as spatial reference (both share identical bounds)."""
        return self._first_on_top

    def result(self) -> tuple[Image, Image]:
        """Return tuple of (first_on_top_image, last_on_top_image)."""
        return (self._first_on_top.edits[0].image, self._last_on_top.edits[0].image)


def create_accumulator(
    order: StackOrder,
    initial_layer: Layer,
    interp: InterpMode = InterpMode.LANCZOS,
) -> FrameAccumulator:
    """Factory creating the appropriate FrameAccumulator for the given StackOrder."""
    if order == StackOrder.FIRST_ON_TOP:
        return FirstOnTopAccumulator(initial_layer, interp=interp)
    if order == StackOrder.LAST_ON_TOP:
        return LastOnTopAccumulator(initial_layer, interp=interp)
    if order == StackOrder.BOTH:
        return DualAccumulator(initial_layer, interp=interp)
    raise ValueError(f"Unknown StackOrder: {order}")
