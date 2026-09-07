"""Scene stitcher orchestrator for anime panoramic scene reconstruction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from anicrop.enums import BlendMode, InterpMode
from anicrop.image import Image
from anicrop.layer import Layer

from anifuse.accumulator import create_accumulator
from anifuse.detection.orb import OrbTransformEstimator
from anifuse.handlers import TranslationHandler
from anifuse.interfaces.stitcher import ProgressCallback, StackOrder, Stitcher
from anifuse.view_policy import AdaptiveViewPolicy, CrossSections

if TYPE_CHECKING:
    from anicrop.spatial import Region

    from anifuse.interfaces.estimator import Estimator
    from anifuse.interfaces.handler import TransformHandler
    from anifuse.interfaces.mask import MaskView
    from anifuse.interfaces.reader import FrameReader
    from anifuse.interfaces.view_policy import ViewPolicy


class SceneStitcher(Stitcher):
    """High-level panoramic scene reconstruction orchestrator."""

    def __init__(
        self,
        handlers: list[TransformHandler],
        view_policy: ViewPolicy,
        stack_order: StackOrder = StackOrder.BOTH,
        blend_mode: BlendMode = BlendMode.SOLID_FILL,
        interp: InterpMode = InterpMode.LANCZOS,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """Initialize SceneStitcher with explicit transformation handlers and view policy."""
        self.handlers: list[TransformHandler] = list(handlers)
        self.view_policy = view_policy
        self.stack_order = stack_order
        self.blend_mode = blend_mode
        self.interp = interp
        self.on_progress = on_progress

    @classmethod
    def from_default(
        cls,
        estimator: Estimator | None = None,
        handlers: list[TransformHandler] | None = None,
        mask_view: MaskView | None = None,
        confidence_threshold: float = 0.80,
        stack_order: StackOrder = StackOrder.BOTH,
        blend_mode: BlendMode = BlendMode.SOLID_FILL,
        interp: InterpMode = InterpMode.LANCZOS,
        on_progress: ProgressCallback | None = None,
    ) -> Self:
        """Convenience factory using OrbTransformEstimator and TranslationHandler by default."""
        actual_estimator = (
            estimator if estimator is not None else OrbTransformEstimator()
        )
        actual_handlers = (
            list(handlers)
            if handlers is not None
            else [TranslationHandler()]
        )
        policy = AdaptiveViewPolicy(
            estimator=actual_estimator,
            mask_view=mask_view,
            confidence_threshold=confidence_threshold,
        )
        return cls(
            handlers=actual_handlers,
            view_policy=policy,
            stack_order=stack_order,
            blend_mode=blend_mode,
            interp=interp,
            on_progress=on_progress,
        )

    def stitch(self, reader: FrameReader) -> Image | tuple[Image, Image]:
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
            blend_mode=self.blend_mode,
        )
        accumulator = create_accumulator(
            self.stack_order, initial_layer, interp=self.interp
        )
        last_region: Region = initial_layer.global_region

        for frame in frame_iter:
            sections = CrossSections(
                accumulator.reference_layer.global_region, last_region
            )
            alignment, ready_frame = self.view_policy.resolve(
                base=accumulator.reference_layer.edits[0].image,
                incoming=frame.image,
                sections=sections,
                frame_idx=frame.idx,
            )

            ready_image = Image(ready_frame, frame.image.format)
            layer2 = Layer(
                ready_image,
                name=f"frame_{frame.idx}",
                blend_mode=self.blend_mode,
            )
            for handler in self.handlers:
                handler.apply(layer2, alignment)

            accumulator.push(layer2)
            last_region = layer2.global_region

            if self.on_progress is not None:
                self.on_progress(frame.idx, total_frames, alignment)

        return accumulator.result()
