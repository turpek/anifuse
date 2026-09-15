"""CLI factories for declarative construction of pipeline components."""

from __future__ import annotations

from anifuse.cli.factories.effect import EffectFactory
from anifuse.cli.factories.estimator import EstimatorFactory, HandlerFactory
from anifuse.cli.factories.reader import ReaderFactory
from anifuse.cli.factories.stitcher import StitcherFactory

__all__ = [
    "EffectFactory",
    "EstimatorFactory",
    "HandlerFactory",
    "ReaderFactory",
    "StitcherFactory",
]
