"""Global configuration instance for anifuse."""

from dataclasses import dataclass


@dataclass
class Config:
    """Global configuration settings and threshold tolerances."""

    rotate_threshold: float = 0.20
    scale_threshold: float = 0.006
    translation_threshold: float = 0.0
    batch_size: int = 15


config = Config()
