"""Interfaces and protocols for post-processing effects in anifuse."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from anicrop.effect import Effect

if TYPE_CHECKING:
    from anicrop.layer import Layer

    from anifuse.interfaces.estimator import MotionEstimate


class LayerTarget(str, Enum):
    """Target layer assignment for an effect during canvas flattening."""

    TOP = "top"
    BOTTOM = "bottom"
    BOTH = "both"


class BorderSide(str, Enum):
    """Canonical sides of a rectangular layer boundary."""

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


@runtime_checkable
class AnifuseEffect(Effect, Protocol):
    """Protocol for anifuse-aware effects that update based on active layers and motion."""

    target: LayerTarget

    def update(
        self,
        top: Layer,
        bottom: Layer,
        motion: MotionEstimate,
    ) -> None:
        """Update effect parameters before layer flattening.

        Args:
            top: The top layer in the current composition stack.
            bottom: The bottom layer in the current composition stack.
            motion: The motion estimate between base and incoming frames.
        """
        ...
