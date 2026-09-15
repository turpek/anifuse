"""Scene stitcher orchestrator for anime panoramic scene reconstruction."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Self

from anicrop.enums import BlendMode, InterpMode
from anicrop.image import Image
from anicrop.layer import Layer
from anicrop.spatial import Region

from anifuse.accumulator import create_accumulator
from anifuse.detection.orb import OrbTransformEstimator
from anifuse.handlers import RotationHandler, ScaleHandler, TranslationHandler
from anifuse.interfaces.stitcher import (
    ProgressCallback,
    StackOrder,
    StitchContext,
    Stitcher,
)
from anifuse.view_policy import AdaptiveViewPolicy, CrossSections

if TYPE_CHECKING:
    from anicrop.spatial import Region

    from anifuse.interfaces.effect import AnifuseEffect
    from anifuse.interfaces.estimator import Estimator
    from anifuse.interfaces.handler import TransformHandler
    from anifuse.interfaces.mask import MaskView
    from anifuse.interfaces.reader import FrameReader
    from anifuse.interfaces.view_policy import SectionGenerator, ViewPolicy


class SceneStitcher(Stitcher):
    """High-level panoramic scene reconstruction orchestrator."""

    def __init__(
        self,
        handlers: list[TransformHandler],
        view_policy: ViewPolicy,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """Initialize SceneStitcher with explicit transformation handlers and view policy."""
        self.handlers: list[TransformHandler] = list(handlers)
        self.view_policy = view_policy
        self.on_progress = on_progress

    @classmethod
    def from_default(
        cls,
        estimator: Estimator | None = None,
        handlers: list[TransformHandler] | None = None,
        mask_view: MaskView | None = None,
        confidence_threshold: float = 0.80,
        rotate_threshold: float = 0.10,
        scale_threshold: float = 0.0010,
        translation_threshold: float = 0.0,
        fast_threshold: int = 10,
        interp: InterpMode = InterpMode.LANCZOS,
        on_progress: ProgressCallback | None = None,
    ) -> Self:
        """Convenience factory using OrbTransformEstimator and geometric transform handlers by default."""
        actual_estimator = (
            estimator
            if estimator is not None
            else OrbTransformEstimator(
                interp=interp,
                rotate_threshold=rotate_threshold,
                scale_threshold=scale_threshold,
                fast_threshold=fast_threshold,
            )
        )
        actual_handlers: list[TransformHandler] = (
            list(handlers)
            if handlers is not None
            else [
                ScaleHandler(threshold=scale_threshold),
                RotationHandler(threshold=rotate_threshold),
                TranslationHandler(threshold=translation_threshold),
            ]
        )
        policy = AdaptiveViewPolicy(
            estimator=actual_estimator,
            mask_view=mask_view,
            confidence_threshold=confidence_threshold,
        )
        return cls(
            handlers=actual_handlers,
            view_policy=policy,
            on_progress=on_progress,
        )

    def stitch(
        self,
        reader: FrameReader,
        stack_order: StackOrder = StackOrder.BOTH,
        effects: Sequence[AnifuseEffect] = (),
        blend_mode: BlendMode = BlendMode.SOLID_FILL,
        interp: InterpMode = InterpMode.LANCZOS,
        sections_cls: type[SectionGenerator] = CrossSections,
    ) -> Image | tuple[Image, Image]:
        """Stitch frames supplied by reader into panoramic composite image(s)."""
        frame_iter = iter(reader)
        try:
            first_frame = next(frame_iter)
        except StopIteration:
            raise ValueError("FrameReader contains no frames to stitch.")

        total_frames = len(reader)
        initial_layer = Layer(
            first_frame.image,
            name=f"frame_{first_frame.idx}",
            blend_mode=blend_mode,
        )
        accumulator = create_accumulator(
            stack_order, initial_layer, interp=interp, effects=effects
        )
        last_region: Region = initial_layer.global_region

        for step, frame in enumerate(frame_iter, start=2):
            sections = sections_cls(
                accumulator.reference_layer.global_region, last_region
            )
            alignment, layer2 = self.view_policy.resolve(
                base=accumulator.reference_layer.edits[0].image,
                incoming=frame.image,
                sections=sections,
                frame_idx=frame.idx,
            )
            layer2.name = f"frame_{frame.idx}"
            layer2.blend_mode = blend_mode
            for handler in self.handlers:
                handler.apply(layer2, alignment)

            context = StitchContext(
                base_region=accumulator.reference_layer.region,
                incoming_region=Region.from_size(*frame.image.size),
                base=accumulator.reference_layer,
                incoming=layer2,
                motion=alignment.motion,
                frame_idx=frame.idx,
            )
            accumulator.push(context)
            last_region = layer2.global_region

            if self.on_progress is not None:
                self.on_progress(step, total_frames, alignment)

        return accumulator.result()
