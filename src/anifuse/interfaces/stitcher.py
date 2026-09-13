"""Interfaces and protocols for scene stitchers, stack strategies, and progress reporting."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from anicrop.enums import BlendMode, InterpMode

if TYPE_CHECKING:
    from anicrop.image import Image
    from anicrop.layer import Layer
    from anicrop.spatial import Region

    from anifuse.interfaces.effect import AnifuseEffect
    from anifuse.interfaces.estimator import MotionEstimate
    from anifuse.interfaces.reader import FrameReader
    from anifuse.interfaces.view_policy import AlignmentResult


@dataclass(frozen=True)
class StitchContext:
    """Contextual spatial, geometric, and motion data for a stitch step."""

    base_region: Region
    incoming_region: Region
    base: Layer
    incoming: Layer
    motion: MotionEstimate
    frame_idx: int = 0


class StackOrder(StrEnum):
    """Stacking order determining visual priority of frames in the panoramic composite."""

    FIRST_ON_TOP = "first-on-top"
    LAST_ON_TOP = "last-on-top"
    BOTH = "both"


ProgressCallback = Callable[[int, int, "AlignmentResult"], None]


class FrameAccumulator(ABC):
    """Abstract strategy for accumulating aligned incoming frames into a canvas composite."""

    @abstractmethod
    def push(self, context: StitchContext) -> None:
        """Push an aligned incoming layer into the canvas composite with its stitch context."""
        pass

    @property
    @abstractmethod
    def reference_layer(self) -> Layer:
        """The layer used as spatial reference for region and view extraction."""
        pass

    @abstractmethod
    def result(self) -> Image | tuple[Image, Image]:
        """Obtain the final stitched composite image(s)."""
        pass


class Stitcher(ABC):
    """Abstract orchestrator for stitching sequential frames into panoramic composite image(s)."""

    @abstractmethod
    def stitch(
        self,
        reader: FrameReader,
        stack_order: StackOrder = StackOrder.BOTH,
        effects: Sequence[AnifuseEffect] = (),
        blend_mode: BlendMode = BlendMode.SOLID_FILL,
        interp: InterpMode = InterpMode.LANCZOS,
    ) -> Image | tuple[Image, Image]:
        """Stitch frames supplied by reader into panoramic composite image(s)."""
        pass
