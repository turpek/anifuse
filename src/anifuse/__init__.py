"""anifuse — Motor inteligente para fusão de cenas panorâmicas de animes."""

from anifuse.accumulator import (
    DualAccumulator,
    FirstOnTopAccumulator,
    LastOnTopAccumulator,
    create_accumulator,
)
from anifuse.config import config
from anifuse.handlers import (
    HorizontalTranslationHandler,
    TranslationHandler,
    VerticalTranslationHandler,
)
from anifuse.interfaces import (
    AlignmentError,
    AlignmentResult,
    Estimator,
    Frame,
    FrameAccumulator,
    FrameReader,
    MaskView,
    MotionEstimate,
    PathResolver,
    ProgressCallback,
    ReadStrategy,
    Section,
    StackOrder,
    Stitcher,
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
from anifuse.reader import (
    BatchedReadStrategy,
    DirectoryPathResolver,
    ImageSequenceReader,
    ListPathResolver,
    StreamReadStrategy,
)
from anifuse.stitcher import SceneStitcher
from anifuse.view_policy import AdaptiveViewPolicy, CrossSections

__all__ = [
    "AdaptiveViewPolicy",
    "AlignmentError",
    "AlignmentResult",
    "BatchedReadStrategy",
    "CompositeMaskView",
    "CrossSections",
    "DefaultMaskView",
    "DirectoryPathResolver",
    "DualAccumulator",
    "DynamicMaskView",
    "Estimator",
    "FirstOnTopAccumulator",
    "Frame",
    "FrameAccumulator",
    "FrameReader",
    "HorizontalTranslationHandler",
    "ImageSequenceReader",
    "LastOnTopAccumulator",
    "ListPathResolver",
    "MaskView",
    "MotionEstimate",
    "PathResolver",
    "ProgressCallback",
    "ReadStrategy",
    "SceneStitcher",
    "Section",
    "SequenceMaskView",
    "StackOrder",
    "StaticMaskView",
    "Stitcher",
    "StreamReadStrategy",
    "TransformHandler",
    "TranslationHandler",
    "VerticalTranslationHandler",
    "ViewPolicy",
    "config",
    "create_accumulator",
]
