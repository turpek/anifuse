"""Concrete canvas accumulation strategies for composite frame stacking."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from anicrop.composition import flatten
from anicrop.enums import InterpMode

from anifuse.interfaces.effect import AnifuseEffect, LayerTarget
from anifuse.interfaces.stitcher import FrameAccumulator, StackOrder

if TYPE_CHECKING:
    from anicrop.image import Image
    from anicrop.layer import Layer

    from anifuse.interfaces.estimator import MotionEstimate


def apply_effects(
    top: Layer,
    bottom: Layer,
    effects: Sequence[AnifuseEffect],
    motion: MotionEstimate,
) -> None:
    """Update and bind post-processing effects to target layers before flattening."""
    for effect in effects:
        effect.update(top, bottom, motion)
        if effect.target == LayerTarget.TOP:
            top.add_effect(effect)
        elif effect.target == LayerTarget.BOTTOM:
            bottom.add_effect(effect)
        elif effect.target == LayerTarget.BOTH:
            top.add_effect(effect)
            bottom.add_effect(effect)


class FirstOnTopAccumulator(FrameAccumulator):
    """Accumulates frames with the initial canvas on top (incoming frames slide underneath)."""

    def __init__(
        self,
        base_layer: Layer,
        interp: InterpMode = InterpMode.LANCZOS,
        effects: Sequence[AnifuseEffect] = (),
    ) -> None:
        """Initialize accumulator with base layer, interpolation mode, and effects."""
        self._base = base_layer
        self._interp = interp
        self._effects = tuple(effects)

    def push(self, incoming: Layer, motion: MotionEstimate) -> None:
        """Flatten incoming layer underneath the accumulated canvas with effects applied."""
        top, bottom = self._base, incoming
        apply_effects(top, bottom, self._effects, motion)
        self._base = flatten([bottom, top], interp=self._interp)
        top.clear_effects()
        bottom.clear_effects()

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
        effects: Sequence[AnifuseEffect] = (),
    ) -> None:
        """Initialize accumulator with base layer, interpolation mode, and effects."""
        self._base = base_layer
        self._interp = interp
        self._effects = tuple(effects)

    def push(self, incoming: Layer, motion: MotionEstimate) -> None:
        """Flatten incoming layer on top of the accumulated canvas with effects applied."""
        top, bottom = incoming, self._base
        apply_effects(top, bottom, self._effects, motion)
        self._base = flatten([bottom, top], interp=self._interp)
        top.clear_effects()
        bottom.clear_effects()

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
        effects: Sequence[AnifuseEffect] = (),
    ) -> None:
        """Initialize accumulator with base layer and effects."""
        self._first_on_top = base_layer
        self._last_on_top = base_layer
        self._interp = interp
        self._effects = tuple(effects)

    def _flatten_first_on_top(
        self, incoming: Layer, motion: MotionEstimate
    ) -> None:
        top, bottom = self._first_on_top, incoming
        apply_effects(top, bottom, self._effects, motion)
        self._first_on_top = flatten([bottom, top], interp=self._interp)
        top.clear_effects()
        bottom.clear_effects()

    def _flatten_last_on_top(
        self, incoming: Layer, motion: MotionEstimate
    ) -> None:
        top, bottom = incoming, self._last_on_top
        apply_effects(top, bottom, self._effects, motion)
        self._last_on_top = flatten([bottom, top], interp=self._interp)
        top.clear_effects()
        bottom.clear_effects()

    def push(self, incoming: Layer, motion: MotionEstimate) -> None:
        """Update both first-on-top and last-on-top composites with isolated effects."""
        self._flatten_first_on_top(incoming, motion)
        self._flatten_last_on_top(incoming, motion)

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
    effects: Sequence[AnifuseEffect] = (),
) -> FrameAccumulator:
    """Factory creating the appropriate FrameAccumulator for the given StackOrder."""
    if order == StackOrder.FIRST_ON_TOP:
        return FirstOnTopAccumulator(initial_layer, interp=interp, effects=effects)
    if order == StackOrder.LAST_ON_TOP:
        return LastOnTopAccumulator(initial_layer, interp=interp, effects=effects)
    if order == StackOrder.BOTH:
        return DualAccumulator(initial_layer, interp=interp, effects=effects)
    raise ValueError(f"Unknown StackOrder: {order}")
