from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from anicrop.cache import AbstractLayerCache
    from anicrop.image import Image
    from anicrop.layer import Layer


@dataclass(frozen=True)
class MotionEstimate:
    """Container for estimated geometric parameters."""

    dx: float = 0.0
    dy: float = 0.0
    angle: float = 0.0
    scale: float = 1.0
    confidence: float = 1.0


class Estimator(ABC):
    """Abstract base class for motion and alignment estimators."""

    @abstractmethod
    def estimate(
        self,
        ref: Image,
        layer: Layer,
        cache: AbstractLayerCache,
        mask: np.ndarray | None = None,
    ) -> MotionEstimate:
        """Estimate relative motion between reference and incoming layer, caching bakes when warped.

        Args:
            ref: Reference image (e.g. active view from canvas).
            layer: Incoming layer containing raw image to align and bake.
            cache: Layer cache for registering pre-transformed warps.
            mask: Optional single-channel uint8 exclusion mask.

        Returns:
            The estimated MotionEstimate.
        """
        pass
