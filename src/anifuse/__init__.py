"""anifuse — Motor inteligente para fusão de cenas panorâmicas de animes."""

from anifuse.config import config
from anifuse.handlers import (
    RotationHandler,
    ScaleHandler,
    TranslationHandler,
)
from anifuse.interfaces import (
    AlignmentError,
    AlignmentResult,
    Estimator,
    MaskView,
    MotionEstimate,
    Section,
    TransformHandler,
    ViewPolicy,
)
from anifuse.mask import (
    CompositeMaskView,
    DefaultMaskView,
    DynamicMaskView,
    SequenceMaskView,
    StaticMaskView,
)
from anifuse.view_policy import AdaptiveViewPolicy, CrossSections

__all__ = [
    "AdaptiveViewPolicy",
    "AlignmentError",
    "AlignmentResult",
    "CompositeMaskView",
    "CrossSections",
    "DefaultMaskView",
    "DynamicMaskView",
    "Estimator",
    "MaskView",
    "MotionEstimate",
    "RotationHandler",
    "ScaleHandler",
    "Section",
    "SequenceMaskView",
    "StaticMaskView",
    "TransformHandler",
    "TranslationHandler",
    "ViewPolicy",
    "config",
]
