"""Concrete view sampling policies and candidate section iterators."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from types import EllipsisType
from typing import TYPE_CHECKING

from anicrop.spatial import Region

from anifuse.interfaces import (
    AlignmentError,
    AlignmentResult,
    Section,
    SectionGenerator,
    ViewPolicy,
)
from anifuse.mask import DefaultMaskView

if TYPE_CHECKING:
    from anicrop.image import Image
    from anicrop.layer import Layer

    from anifuse.interfaces import Estimator, MaskView


class CrossSections(SectionGenerator):
    """Generator yielding candidate search sections: first local cross neighborhood, then global canvas grid."""

    def __init__(
        self,
        global_region: Region,
        last_region: Region | EllipsisType = ...,
        step: float = 500.0,
        min_size: float = 100.0,
    ) -> None:
        """Initialize with canvas global bounds and reference last region."""
        self.global_region = global_region
        self.last_region = last_region
        self.step = step
        self.min_size = min_size

    def __iter__(self) -> Iterator[Section]:
        """Yield candidate sections lazily: Center -> Cross Neighbors -> Full Canvas Grid."""
        if isinstance(self.last_region, EllipsisType):
            local_view = Region.from_size(*self.global_region.size)
            yield Section(ref=self.global_region, view=local_view)
            return

        visited: set[tuple[int, int]] = set()

        # Phase 1: Center (last known position)
        if self.global_region.overlaps(self.last_region):
            center_ref = self.global_region & self.last_region
            if center_ref.width >= self.min_size and center_ref.height >= self.min_size:
                visited.add(center_ref.top_left.to_int())
                local_view = self.global_region.overlap_with(center_ref)
                yield Section(ref=center_ref, view=local_view)

        # Phase 1: Cross neighbors: right (+x), left (-x), down (+y), up (-y)
        cross_offsets = [
            (self.step, 0.0),
            (-self.step, 0.0),
            (0.0, self.step),
            (0.0, -self.step),
        ]

        for dx, dy in cross_offsets:
            candidate = self.last_region + (dx, dy)
            if self.global_region.overlaps(candidate):
                candidate_ref = self.global_region & candidate
                if (
                    candidate_ref.width >= self.min_size
                    and candidate_ref.height >= self.min_size
                ):
                    coord_key = candidate_ref.top_left.to_int()
                    if coord_key not in visited:
                        visited.add(coord_key)
                        local_view = self.global_region.overlap_with(candidate_ref)
                        yield Section(ref=candidate_ref, view=local_view)

        # Phase 2: Full Canvas Grid sweep (fallback if local neighborhood fails)
        frame_w, frame_h = self.last_region.size.to_int()

        slice_y, slice_x = self.global_region.to_slice()
        min_x, max_x = slice_x.start, slice_x.stop
        min_y, max_y = slice_y.start, slice_y.stop
        step_val = max(1, int(self.step))

        curr_x = min_x
        while curr_x < max_x:
            curr_y = min_y
            while curr_y < max_y:
                tile = Region.from_rect(
                    float(curr_x), float(curr_y), float(frame_w), float(frame_h)
                )
                if self.global_region.overlaps(tile):
                    tile_ref = self.global_region & tile
                    if (
                        tile_ref.width >= self.min_size
                        and tile_ref.height >= self.min_size
                    ):
                        coord_key = tile_ref.top_left.to_int()
                        if coord_key not in visited:
                            visited.add(coord_key)
                            local_view = self.global_region.overlap_with(tile_ref)
                            yield Section(ref=tile_ref, view=local_view)
                curr_y += step_val
            curr_x += step_val


class GlobalSections(SectionGenerator):
    """Generator yielding a single section covering the entire canvas global bounds."""

    def __init__(
        self,
        global_region: Region,
        last_region: Region | EllipsisType = ...,
    ) -> None:
        """Initialize generator with canvas global bounds and reference last region."""
        self.global_region = global_region
        self.last_region = last_region

    def __iter__(self) -> Iterator[Section]:
        """Yield candidate section spanning the full global canvas."""
        yield Section(
            ref=self.global_region,
            view=Region.from_size(*self.global_region.size),
        )


class AdaptiveViewPolicy(ViewPolicy):
    """Adaptive view policy returning the first section that satisfies the confidence threshold."""

    def __init__(
        self,
        estimator: Estimator,
        mask_view: MaskView | None = None,
        confidence_threshold: float = 0.80,
    ) -> None:
        """Initialize with motion estimator, optional mask view, and confidence threshold."""
        self._estimator = estimator
        self._mask_view = mask_view or DefaultMaskView()
        self._confidence_threshold = confidence_threshold

    def resolve(
        self,
        base: Image,
        incoming: Image,
        sections: Iterable[Section],
        frame_idx: int = 0,
    ) -> tuple[AlignmentResult, Layer]:
        """Resolve frame alignment by returning the first candidate section meeting confidence threshold."""
        incoming_img, mask_arr = self._mask_view.get_mask(incoming, frame_idx)

        for section in sections:
            ref_view = base.view(section.view)
            motion, ready_image = self._estimator.estimate(
                ref_view, incoming_img, mask=mask_arr
            )

            if motion.confidence >= self._confidence_threshold:
                return AlignmentResult(ref=section.ref, motion=motion), ready_image

        raise AlignmentError(
            f"Frame {frame_idx} could not be aligned: no candidate section reached confidence threshold {self._confidence_threshold}."
        )
