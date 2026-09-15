"""Domain configuration models and enums for anifuse CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from anicrop.enums import BlendMode, InterpMode

from anifuse.interfaces.stitcher import StackOrder


class MotionMode(str, Enum):
    """Supported camera motion estimation modes."""

    TRANSLATION = "translation"
    SCALE = "scale"
    ROTATION = "rotation"
    AFFINE = "affine"


class DirectionConstraint(str, Enum):
    """Axis constraint for pure translation motion."""

    AUTO = "auto"
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class SectionStrategy(str, Enum):
    """Active canvas window sectioning strategy."""

    CROSS = "cross"
    GLOBAL = "global"


class ReadStrategyType(str, Enum):
    """Image loading and buffering strategy."""

    STREAM = "stream"
    BATCHED = "batched"


class SourceType(str, Enum):
    """Input media source type."""

    DIR = "dir"
    IMAGE = "image"
    VIDEO = "video"


class BlendChoice(str, Enum):
    """CLI choices for canvas layer blend mode."""

    HARD_MASKING = "hard-masking"
    SOLID_FILL = "solid-fill"
    NORMAL = "normal"
    NORMAL_LINEAR = "normal-linear"
    MULTIPLY = "multiply"
    CLIP = "clip"

    def to_blend_mode(self) -> BlendMode:
        """Map CLI choice to core anicrop BlendMode."""
        mapping = {
            BlendChoice.HARD_MASKING: BlendMode.HARD_MASKING,
            BlendChoice.SOLID_FILL: BlendMode.SOLID_FILL,
            BlendChoice.NORMAL: BlendMode.NORMAL,
            BlendChoice.NORMAL_LINEAR: BlendMode.NORMAL_LINEAR,
            BlendChoice.MULTIPLY: BlendMode.MULTIPLY,
            BlendChoice.CLIP: BlendMode.CLIP,
        }
        return mapping[self]


class InterpChoice(str, Enum):
    """CLI choices for affine interpolation algorithms."""

    LANCZOS = "lanczos"
    CUBIC = "cubic"
    LINEAR = "linear"
    NEAREST = "nearest"
    AREA = "area"

    def to_interp_mode(self) -> InterpMode:
        """Map CLI choice to core anicrop InterpMode."""
        mapping = {
            InterpChoice.LANCZOS: InterpMode.LANCZOS,
            InterpChoice.CUBIC: InterpMode.CUBIC,
            InterpChoice.LINEAR: InterpMode.LINEAR,
            InterpChoice.NEAREST: InterpMode.NEAREST,
            InterpChoice.AREA: InterpMode.AREA,
        }
        return mapping[self]


class StackOrderChoice(str, Enum):
    """CLI choices for layer stacking order."""

    BOTH = "both"
    LAST_ON_TOP = "last-on-top"
    FIRST_ON_TOP = "first-on-top"

    def to_stack_order(self) -> StackOrder:
        """Map CLI choice to core StackOrder enum."""
        mapping = {
            StackOrderChoice.BOTH: StackOrder.BOTH,
            StackOrderChoice.LAST_ON_TOP: StackOrder.LAST_ON_TOP,
            StackOrderChoice.FIRST_ON_TOP: StackOrder.FIRST_ON_TOP,
        }
        return mapping[self]


@dataclass(frozen=True)
class OutputConfig:
    """Output destination, formatting, and verbosity settings."""

    output_dir: Path = Path(".")
    name_template: str | None = None
    force: bool = False
    quiet: bool = False


@dataclass(frozen=True)
class MotionConfig:
    """Computer vision, feature detection, and motion estimation thresholds."""

    motion_mode: MotionMode = MotionMode.AFFINE
    direction: DirectionConstraint = DirectionConstraint.AUTO
    confidence_threshold: float = 0.80
    fast_threshold: int = 10
    rotate_threshold: float = 0.10
    scale_threshold: float = 0.0010
    translation_threshold: float = 0.0
    max_features: int = 5000
    distance_threshold: float = 40.0
    nbest: int | None = None
    mask_roi: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class CompositionConfig:
    """Canvas composition, layer stacking, and rendering parameters."""

    stack_order: StackOrder = StackOrder.BOTH
    blend_mode: BlendMode = BlendMode.HARD_MASKING
    hard_mask_threshold: int = 150
    interp: InterpMode = InterpMode.LANCZOS
    sections: SectionStrategy = SectionStrategy.CROSS


@dataclass(frozen=True)
class EffectsConfig:
    """Border cutting and seam removal parameters."""

    border_cut: int | None = None
    border_cut_left: int = 0
    border_cut_right: int = 0
    border_cut_top: int = 0
    border_cut_bottom: int = 0

    @property
    def has_cut(self) -> bool:
        """Return True if any border cut dimension is configured."""
        return self.border_cut is not None or any(
            (
                self.border_cut_left,
                self.border_cut_right,
                self.border_cut_top,
                self.border_cut_bottom,
            )
        )


@dataclass(frozen=True)
class SourceConfig:
    """Input source configuration and frame sampling slicing."""

    source_type: SourceType = SourceType.DIR
    paths: tuple[Path, ...] = ()
    start: int = 0
    frames: int | None = None
    step: int = 1
    reverse: bool = False
    read_strategy: ReadStrategyType = ReadStrategyType.BATCHED
    batch_size: int = 15
    fps: float | None = None


@dataclass(frozen=True)
class StitchJob:
    """Self-contained specification for a single stitching job."""

    motion: MotionConfig = field(default_factory=MotionConfig)
    composition: CompositionConfig = field(default_factory=CompositionConfig)
    effects: EffectsConfig = field(default_factory=EffectsConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    source: SourceConfig = field(default_factory=SourceConfig)
