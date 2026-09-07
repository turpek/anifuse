"""Abstract base class and types for motion estimators."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


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
        ref: np.ndarray,
        incoming: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, np.ndarray]:
        """Estimate relative motion between reference and incoming image arrays.

        Args:
            ref: Reference image array (e.g. active view from canvas).
            incoming: Incoming image array.
            mask: Optional single-channel uint8 exclusion mask for incoming array.

        Returns:
            A tuple of (MotionEstimate, processed_incoming_array).
        """
        pass
