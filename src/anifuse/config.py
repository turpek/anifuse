"""Global configuration instance for anifuse."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import anicrop
from loguru import logger

from anifuse.interfaces.stitcher import StackOrder


def configure_logging(level: str = "ERROR") -> None:
    """Configure loguru global logging level, suppressing verbose debug output."""
    logger.remove()
    logger.add(sys.stderr, level=level)


# Silence verbose debug logging by default
configure_logging("ERROR")


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
    log_level: str = "ERROR"

    def __post_init__(self) -> None:
        """Initialize and calibrate default backend engine parameters."""
        anicrop.config.hard_mask_threshold = 150
        configure_logging(self.log_level)

    @property
    def hard_mask_threshold(self) -> int:
        """Alpha quantization threshold for HARD_MASKING in anicrop."""
        return anicrop.config.hard_mask_threshold

    @hard_mask_threshold.setter
    def hard_mask_threshold(self, value: int) -> None:
        anicrop.config.hard_mask_threshold = value


config = Config()
