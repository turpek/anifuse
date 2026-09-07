"""Concrete MaskView implementations for frame cropping and feature exclusion masking."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import numpy as np
from anicrop.spatial import Region

from anifuse.interfaces import MaskView

if TYPE_CHECKING:
    from anicrop.image import Image


class DefaultMaskView(MaskView):
    """Default pass-through mask view returning full image and no mask."""

    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[Image, np.ndarray | None]:
        """Return full Image with no mask."""
        return image, None


class StaticMaskView(MaskView):
    """Static mask view that yields the same exclusion across all frames."""

    def __init__(self, mask: Region | np.ndarray | None) -> None:
        """Initialize with a static Region, NumPy array, or None."""
        self._mask = mask

    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[Image, np.ndarray | None]:
        """Return frame Image and mask corresponding to configured static mask."""
        if isinstance(self._mask, Region):
            return image.view(self._mask), None
        if isinstance(self._mask, np.ndarray):
            return image, self._mask
        return image, None


class SequenceMaskView(MaskView):
    """Pre-computed sequence mask view indexed by frame index."""

    def __init__(self, sequence: Sequence[Region | np.ndarray | None]) -> None:
        """Initialize with a sequence of masks corresponding to each frame index."""
        self._sequence = list(sequence)

    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[Image, np.ndarray | None]:
        """Return frame Image and mask corresponding to the given frame index."""
        if 0 <= frame_idx < len(self._sequence):
            mask = self._sequence[frame_idx]
            if isinstance(mask, Region):
                return image.view(mask), None
            if isinstance(mask, np.ndarray):
                return image, mask
        return image, None


class DynamicMaskView(MaskView):
    """Dynamic mask view that evaluates a detector or callback per frame."""

    def __init__(
        self,
        detector: Callable[[Image, int], Region | np.ndarray | None],
    ) -> None:
        """Initialize with a detector callback that receives (image, frame_idx)."""
        self._detector = detector

    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[Image, np.ndarray | None]:
        """Evaluate detector on given image and return frame Image and mask."""
        result = self._detector(image, frame_idx)
        if isinstance(result, Region):
            return image.view(result), None
        if isinstance(result, np.ndarray):
            return image, result
        return image, None


class CompositeMaskView(MaskView):
    """Composite mask view that combines multiple MaskView instances into a single mask."""

    def __init__(self, masks: Sequence[MaskView]) -> None:
        """Initialize with a sequence of child MaskView instances."""
        self._masks = list(masks)

    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[Image, np.ndarray | None]:
        """Collect active child masks and compile into a single uint8 binary mask array."""
        active_masks: list[np.ndarray] = []
        for mv in self._masks:
            _, m = mv.get_mask(image, frame_idx)
            if m is not None:
                active_masks.append(m)

        if not active_masks:
            return image, None

        h, w = image.height, image.width
        compiled = np.full((h, w), 255, dtype=np.uint8)
        for m in active_masks:
            compiled[m == 0] = 0

        return image, compiled
