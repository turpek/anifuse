"""Declarative factory for assembling the SceneStitcher orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anicrop.spatial import Region

from anifuse.cli.factories.estimator import EstimatorFactory, HandlerFactory
from anifuse.cli.models import SectionStrategy, StitchJob
from anifuse.interfaces.stitcher import ProgressCallback
from anifuse.interfaces.view_policy import SectionGenerator
from anifuse.mask import StaticMaskView
from anifuse.stitcher import SceneStitcher
from anifuse.view_policy import CrossSections, GlobalSections

if TYPE_CHECKING:
    from anifuse.interfaces.mask import MaskView

SECTION_MAP: dict[SectionStrategy, type[SectionGenerator]] = {
    SectionStrategy.CROSS: CrossSections,
    SectionStrategy.GLOBAL: GlobalSections,
}


class StitcherFactory:
    """Factory responsible for assembling configured SceneStitcher instances."""

    @staticmethod
    def resolve_sections(strategy: SectionStrategy) -> type[SectionGenerator]:
        """Resolve the active canvas sectioning strategy generator."""
        return SECTION_MAP.get(strategy, CrossSections)

    @classmethod
    def create(
        cls,
        job: StitchJob,
        on_progress: ProgressCallback | None = None,
    ) -> SceneStitcher:
        """Construct a configured SceneStitcher matching the job specifications."""
        estimator = EstimatorFactory.create(job.motion, job.composition)
        handlers = HandlerFactory.create(job.motion)

        mask_view: MaskView | None = None
        if job.motion.mask_roi is not None:
            x, y, w, h = job.motion.mask_roi
            mask_view = StaticMaskView(Region(x, y, w, h))

        return SceneStitcher.from_default(
            estimator=estimator,
            handlers=handlers,
            mask_view=mask_view,
            confidence_threshold=job.motion.confidence_threshold,
            on_progress=on_progress,
        )
