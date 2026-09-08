"""Global configuration instance for anifuse."""

from __future__ import annotations

from dataclasses import dataclass

import anicrop

from anifuse.interfaces.stitcher import StackOrder


@dataclass
class Config:
    """Global configuration settings and threshold tolerances."""

    rotate_threshold: float = 0.10
    scale_threshold: float = 0.0010
    translation_threshold: float = 0.0
    fast_threshold: int = 10
    batch_size: int = 15
    border_cut_size: int = 5
    stack_order: StackOrder = StackOrder.BOTH

    def __post_init__(self) -> None:
        """Initialize and calibrate default backend engine parameters."""
        anicrop.config.hard_mask_threshold = 150

    @property
    def hard_mask_threshold(self) -> int:
        """Alpha quantization threshold for HARD_MASKING in anicrop."""
        return anicrop.config.hard_mask_threshold

    @hard_mask_threshold.setter
    def hard_mask_threshold(self, value: int) -> None:
        anicrop.config.hard_mask_threshold = value


config = Config()
