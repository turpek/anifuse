"""Interfaces and protocols for post-processing effects in anifuse."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from anicrop.effect import Effect

from anifuse.interfaces.stitcher import StitchContext

if TYPE_CHECKING:
    from anicrop.layer import Layer

__all__ = [
    "AnifuseEffect",
    "BorderSide",
    "LayerTarget",
    "StitchContext",
]


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


class AnifuseEffect(Effect, ABC):
    """Abstract base class for anifuse-aware effects that update based on top and bottom layers."""

    target: LayerTarget

    @abstractmethod
    def update(self, top: Layer, bottom: Layer) -> None:
        """Update effect parameters before layer flattening.

        Args:
            top: Top layer in the current composition step.
            bottom: Bottom layer in the current composition step.
        """
        pass
