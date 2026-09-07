"""Interfaces and abstract base classes for anifuse."""

from anifuse.interfaces.estimator import Estimator, MotionEstimate
from anifuse.interfaces.handler import TransformHandler
from anifuse.interfaces.mask import MaskView
from anifuse.interfaces.reader import (
    Frame,
    FrameReader,
    PathResolver,
    ReadStrategy,
)
from anifuse.interfaces.stitcher import (
    FrameAccumulator,
    ProgressCallback,
    StackOrder,
    Stitcher,
)
from anifuse.interfaces.view_policy import (
    AlignmentError,
    AlignmentResult,
    Section,
    ViewPolicy,
)

__all__ = [
    "AlignmentError",
    "AlignmentResult",
    "Estimator",
    "Frame",
    "FrameAccumulator",
    "FrameReader",
    "MaskView",
    "MotionEstimate",
    "PathResolver",
    "ProgressCallback",
    "ReadStrategy",
    "Section",
    "StackOrder",
    "Stitcher",
    "TransformHandler",
    "ViewPolicy",
]
