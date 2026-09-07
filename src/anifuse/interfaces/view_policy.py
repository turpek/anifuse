"""Interfaces and data structures for view sampling policies and alignment results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from anicrop.image import Image
    from anicrop.spatial import Region

    from anifuse.interfaces.estimator import MotionEstimate


@dataclass(frozen=True)
class Section:
    """Candidate search section pairing global canvas coordinates with local Image slice."""

    ref: Region
    view: Region


@dataclass(frozen=True)
class AlignmentResult:
    """Consolidated alignment metadata associating a reference canvas region with estimated motion."""

    ref: Region
    motion: MotionEstimate


class ViewPolicy(ABC):
    """Abstract strategy for sampling reference windows, applying masks, and estimating motion."""

    @abstractmethod
    def resolve(
        self,
        base: Image,
        incoming: Image,
        sections: Iterable[Section],
        frame_idx: int = 0,
    ) -> tuple[AlignmentResult, np.ndarray]:
        """Evaluate candidate sections, apply mask to incoming, and estimate motion."""
        pass


class AlignmentError(RuntimeError):
    """Raised when no candidate search section satisfies the confidence threshold."""

    pass
