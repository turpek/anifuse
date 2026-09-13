"""Linear border seam cut effect for axis-aligned translation pans."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anifuse.interfaces.effect import AnifuseEffect, LayerTarget

if TYPE_CHECKING:
    import numpy as np
    from anicrop.effect import Effect
    from anicrop.image import Image
    from anicrop.layer import Layer
    from anicrop.spatial import Region


class LinearBorderCutEffect(AnifuseEffect):
    """Cuts border seams along axis-aligned layer edges using anicrop Region shrink and clear_rect."""

    target: LayerTarget = LayerTarget.TOP

    def __init__(
        self,
        all: int | None = None,
        *,
        left: int = 0,
        right: int = 0,
        top: int = 0,
        bottom: int = 0,
        visible: bool = True,
        name: str = "LinearBorderCut",
    ) -> None:
        """Initialize linear border cut effect with per-side thicknesses or uniform margin.

        Args:
            all: Optional uniform cut thickness applied to all sides.
            left: Cut thickness in pixels for the left edge.
            right: Cut thickness in pixels for the right edge.
            top: Cut thickness in pixels for the top edge.
            bottom: Cut thickness in pixels for the bottom edge.
            visible: Whether the effect is active in the render pipeline.
            name: Human-readable identifier for the effect.
        """
        super().__init__(visible=visible, name=name)
        self._all = all
        self._shrink = {
            "left": left,
            "right": right,
            "top": top,
            "bottom": bottom,
        }
        if all is not None:
            self._shrink = {k: all for k in self._shrink}

        self._counter: int = 0
        self._local_view: Region | None = None
        self._local_roi: Region | None = None

    def get_padding(self) -> tuple[int, int, int, int]:
        """Return zero padding as border cutting does not expand bounds."""
        return (0, 0, 0, 0)

    def merge(self, other: Effect, matrix: np.ndarray) -> Effect | None:
        """Return None as border cutting cannot be analytically merged."""
        return None

    def update(self, top: Layer, bottom: Layer) -> None:
        """Pre-calculate local cut regions and reset execution counter."""
        self._counter = 0

        if not top.global_region.overlaps(bottom.global_region):
            self._counter = 1
            return

        dx, dy = (top.global_region - bottom.global_region).top_left

        shrink = self._shrink.copy()
        if dy == 0:
            shrink["top"] = shrink["bottom"] = 0
        if dx == 0:
            shrink["left"] = shrink["right"] = 0

        overlap_global = top.global_region & bottom.global_region
        self._local_view = top.global_region.overlap_with(overlap_global)

        shrunk = top.global_region.shrink(**shrink)
        if not shrunk.overlaps(bottom.global_region):
            self._local_roi = None
        else:
            shrink_global = shrunk & bottom.global_region
            self._local_roi = overlap_global.overlap_with(shrink_global)

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Execute clear_rect directly on pre-calculated region when counter is zero."""
        if self._counter == 0:
            assert self._local_view is not None
            if self._local_roi is None:
                image.clear_rect(self._local_view, fill_value=0, invert=False, alpha_only=True)
            else:
                view = image.view(self._local_view)
                view.clear_rect(self._local_roi, fill_value=0, invert=True, alpha_only=True)
        self._counter += 1
        return image
