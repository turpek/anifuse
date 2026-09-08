"""Global configuration instance for anifuse."""

from dataclasses import dataclass

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


config = Config()
