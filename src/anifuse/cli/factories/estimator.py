"""Declarative factory for camera motion estimators and geometric transform handlers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING

from anifuse.cli.models import DirectionConstraint, MotionConfig, MotionMode
from anifuse.detection.orb import (
    OrbRotationEstimator,
    OrbScaleEstimator,
    OrbTransformEstimator,
    OrbTranslationEstimator,
)
from anifuse.handlers import (
    HorizontalTranslationHandler,
    RotationHandler,
    ScaleHandler,
    TranslationHandler,
    VerticalTranslationHandler,
)
from anifuse.interfaces.estimator import Estimator
from anifuse.interfaces.handler import TransformHandler

if TYPE_CHECKING:
    from anifuse.cli.models import CompositionConfig

ESTIMATOR_MAP: dict[MotionMode, type[Estimator]] = {
    MotionMode.TRANSLATION: OrbTranslationEstimator,
    MotionMode.SCALE: OrbScaleEstimator,
    MotionMode.ROTATION: OrbRotationEstimator,
    MotionMode.AFFINE: OrbTransformEstimator,
}


def _build_translation_handler(motion: MotionConfig) -> TransformHandler:
    if motion.direction == DirectionConstraint.HORIZONTAL:
        return HorizontalTranslationHandler(threshold=motion.translation_threshold)
    if motion.direction == DirectionConstraint.VERTICAL:
        return VerticalTranslationHandler(threshold=motion.translation_threshold)
    return TranslationHandler(threshold=motion.translation_threshold)


HANDLER_RECIPES: dict[MotionMode, list[Callable[[MotionConfig], TransformHandler]]] = {
    MotionMode.TRANSLATION: [_build_translation_handler],
    MotionMode.SCALE: [
        lambda m: ScaleHandler(threshold=m.scale_threshold),
        _build_translation_handler,
    ],
    MotionMode.ROTATION: [
        lambda m: RotationHandler(threshold=m.rotate_threshold),
        _build_translation_handler,
    ],
    MotionMode.AFFINE: [
        lambda m: ScaleHandler(threshold=m.scale_threshold),
        lambda m: RotationHandler(threshold=m.rotate_threshold),
        _build_translation_handler,
    ],
}


class EstimatorFactory:
    """Factory responsible for instantiating concrete feature-based motion estimators."""

    @staticmethod
    def create(motion: MotionConfig, composition: CompositionConfig) -> Estimator:
        """Create an Estimator configured with the specified motion and interpolation parameters."""
        estimator_cls = ESTIMATOR_MAP.get(motion.motion_mode)
        if estimator_cls is None:
            raise ValueError(f"Modo de movimento não suportado: '{motion.motion_mode}'")

        available_params = {
            "max_features": motion.max_features,
            "distance_threshold": motion.distance_threshold,
            "nbest": motion.nbest,
            "fast_threshold": motion.fast_threshold,
            "interp": composition.interp,
            "scale_threshold": motion.scale_threshold,
            "rotate_threshold": motion.rotate_threshold,
            "confidence_threshold": motion.confidence_threshold,
        }
        sig = inspect.signature(estimator_cls.__init__)
        filtered_kwargs = {
            k: v for k, v in available_params.items() if k in sig.parameters
        }
        return estimator_cls(**filtered_kwargs)


class HandlerFactory:
    """Factory responsible for building ordered transform handler pipelines."""

    @staticmethod
    def create(motion: MotionConfig) -> list[TransformHandler]:
        """Create a list of geometric transform handlers corresponding to the motion mode."""
        if motion.motion_mode != MotionMode.TRANSLATION and motion.direction in (
            DirectionConstraint.HORIZONTAL,
            DirectionConstraint.VERTICAL,
        ):
            raise ValueError(
                f"A restrição de direção '{motion.direction.value}' só é suportada "
                f"quando o modo de movimento for 'translation'."
            )

        builders = HANDLER_RECIPES.get(motion.motion_mode)
        if builders is None:
            raise ValueError(f"Modo de movimento não suportado: '{motion.motion_mode}'")

        return [builder(motion) for builder in builders]
