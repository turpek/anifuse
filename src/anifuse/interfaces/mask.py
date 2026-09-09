from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from anicrop.image import Image


class MaskView(ABC):
    """Abstract base class representing a mask view for frames."""

    @abstractmethod
    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[Image, np.ndarray | None]:
        """Extract frame Image and optional exclusion mask from an Image.

        Args:
            image: Input Image instance from anicrop.
            frame_idx: Zero-based frame index in the sequence.

        Returns:
            A tuple of (frame_image, mask_array_or_none).
        """
        pass
