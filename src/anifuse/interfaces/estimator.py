from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from anicrop.image import Image


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
        incoming: Image,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, Image]:
        """Estimate relative motion between reference and incoming images.

        Args:
            ref: Reference image (e.g. active view from canvas).
            incoming: Incoming image.
            mask: Optional single-channel uint8 exclusion mask.

        Returns:
            A tuple of (MotionEstimate, processed_incoming_image).
        """
        pass
