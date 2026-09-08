"""Border seam cut effect for canvas overlap transitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anifuse.config import config
from anifuse.interfaces.effect import AnifuseEffect, LayerTarget

if TYPE_CHECKING:
    import numpy as np
    from anicrop.effect import Effect
    from anicrop.image import Image
    from anicrop.layer import Layer

    from anifuse.interfaces.estimator import MotionEstimate


class BorderCutEffect(AnifuseEffect):
    """Cuts border seams along overlapping layer edges to eliminate stitching artifacts."""

    target: LayerTarget = LayerTarget.TOP

    def __init__(
        self,
        cut_size: int | None = None,
        *,
        left: int | None = None,
        right: int | None = None,
        top: int | None = None,
        bottom: int | None = None,
    ) -> None:
        """Initialize border cut effect with uniform or per-side thickness.

        Args:
            cut_size: Uniform cut thickness in pixels for automatically detected sides.
                Defaults to config.border_cut_size if None and no manual sides are specified.
            left: Explicit cut thickness in pixels for the left edge.
            right: Explicit cut thickness in pixels for the right edge.
            top: Explicit cut thickness in pixels for the top edge.
            bottom: Explicit cut thickness in pixels for the bottom edge.
        """
        self.cut_size = (
            cut_size if cut_size is not None else config.border_cut_size
        )
        self.manual_sides = {
            side: val
            for side, val in [
                ("left", left),
                ("right", right),
                ("top", top),
                ("bottom", bottom),
            ]
            if val is not None and val > 0
        }
        self._slices: list[tuple[slice, slice]] = []

    def get_padding(self) -> tuple[int, int, int, int]:
        """Return zero padding as border cutting does not expand bounds."""
        return (0, 0, 0, 0)

    def merge(self, other: Effect, matrix: np.ndarray) -> Effect | None:
        """Return None as border cutting cannot be analytically merged."""
        return None

    def update(
        self,
        top: Layer,
        bottom: Layer,
        motion: MotionEstimate,
    ) -> None:
        """Calculate overlap region and active edge slice bounds on the top layer."""
        self._slices = []
        if not top.global_region.overlaps(bottom.global_region):
            return

        axis_y, axis_x = top.global_region.overlap_with(
            bottom.global_region
        ).to_slice()

        if self.manual_sides:
            sides = self.manual_sides
        else:
            dx, dy = (top.global_region - bottom.global_region).top_left
            sides = {}
            if self.cut_size > 0:
                if dx > 0:
                    sides["left"] = self.cut_size
                elif dx < 0:
                    sides["right"] = self.cut_size
                if dy > 0:
                    sides["top"] = self.cut_size
                elif dy < 0:
                    sides["bottom"] = self.cut_size

        for side, size in sides.items():
            if side == "left":
                self._slices.append(
                    (
                        axis_y,
                        slice(axis_x.start, min(axis_x.stop, axis_x.start + size)),
                    )
                )
            elif side == "right":
                self._slices.append(
                    (
                        axis_y,
                        slice(max(axis_x.start, axis_x.stop - size), axis_x.stop),
                    )
                )
            elif side == "top":
                self._slices.append(
                    (
                        slice(axis_y.start, min(axis_y.stop, axis_y.start + size)),
                        axis_x,
                    )
                )
            elif side == "bottom":
                self._slices.append(
                    (
                        slice(max(axis_y.start, axis_y.stop - size), axis_y.stop),
                        axis_x,
                    )
                )

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Erase alpha channel in-place along calculated border seam slices."""
        if not self._slices:
            return image

        arr = image[...]
        if arr.ndim >= 3 and arr.shape[2] == 4:
            for sy, sx in self._slices:
                arr[sy, sx, 3] = 0

        return image
