"""Border seam cut effect for canvas overlap transitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from anifuse.interfaces.effect import AnifuseEffect, LayerTarget

if TYPE_CHECKING:
    from anicrop.effect import Effect
    from anicrop.image import Image
    from anicrop.layer import Layer
    from anicrop.spatial import Region


class BorderCutEffect(AnifuseEffect):
    """Cuts border seams along overlapping layer edges to eliminate stitching artifacts."""

    target: LayerTarget = LayerTarget.TOP

    def __init__(
        self,
        all: int | None = None,
        *,
        left: int = 0,
        right: int = 0,
        top: int = 0,
        bottom: int = 0,
        min_alpha: int = 250,
        visible: bool = True,
        name: str = "BorderCut",
    ) -> None:
        """Initialize border cut effect with per-side thicknesses or uniform margin.

        Args:
            all: Optional uniform cut thickness applied to all sides.
            left: Cut thickness in pixels for the left edge.
            right: Cut thickness in pixels for the right edge.
            top: Cut thickness in pixels for the top edge.
            bottom: Cut thickness in pixels for the bottom edge.
            min_alpha: Minimum opacity threshold for underlying bottom layer.
            visible: Whether the effect is active in the render pipeline.
            name: Human-readable identifier for the effect.
        """
        super().__init__(visible=visible, name=name)
        self._shrink = {
            "left": left,
            "right": right,
            "top": top,
            "bottom": bottom,
        }
        if all is not None:
            self._shrink["left"] = all
            self._shrink["right"] = all
            self._shrink["top"] = all
            self._shrink["bottom"] = all

        self.min_alpha = min_alpha

        self._top_global_region: Region | None = None
        self._bottom_global_region: Region | None = None
        self._buf_pts: np.ndarray | None = None
        self._is_rotated: bool = False

    def get_padding(self) -> tuple[int, int, int, int]:
        """Return zero padding as border cutting does not expand bounds."""
        return (0, 0, 0, 0)

    def merge(self, other: Effect, matrix: np.ndarray) -> Effect | None:
        """Return None as border cutting cannot be analytically merged."""
        return None

    def update(self, top: Layer, bottom: Layer) -> None:
        """Extract spatial and geometric parameters from top and bottom layers."""
        self._top_global_region = top.global_region
        self._bottom_global_region = bottom.global_region

        mat = top.transform.matrix
        self._is_rotated = not (
            np.isclose(mat[0, 1], 0.0, atol=1e-5)
            and np.isclose(mat[1, 0], 0.0, atol=1e-5)
        )

        w, h = top.region.size.to_int()
        corners = np.array(
            [
                [0.0, 0.0, 1.0],
                [float(w), 0.0, 1.0],
                [float(w), float(h), 1.0],
                [0.0, float(h), 1.0],
            ],
            dtype=np.float32,
        )
        transformed = (mat @ corners.T).T[:, :2]
        self._buf_pts = transformed - np.array(
            top.global_region.top_left, dtype=np.float32
        )

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Calculate overlap and cut seams directly on the image."""
        if self._top_global_region is None or self._bottom_global_region is None:
            return image

        if not self._top_global_region.overlaps(self._bottom_global_region):
            return image

        if self._is_rotated:
            return self._apply_rotated(image)

        return self._apply_axis_aligned(image)

    def _apply_axis_aligned(self, image: Image) -> Image:
        """Erase alpha channel along axis-aligned border seam using Region shrink."""
        assert self._top_global_region is not None
        assert self._bottom_global_region is not None

        dx, dy = (self._top_global_region - self._bottom_global_region).top_left

        shrink = self._shrink.copy()
        if dy == 0:
            shrink["top"] = shrink["bottom"] = 0
        if dx == 0:
            shrink["left"] = shrink["right"] = 0

        overlap_global = self._top_global_region & self._bottom_global_region
        local_view = self._top_global_region.overlap_with(overlap_global)

        shrunk = self._top_global_region.shrink(**shrink)
        if not shrunk.overlaps(self._bottom_global_region):
            image.clear_rect(local_view, fill_value=0, invert=False, alpha_only=True)
            return image

        shrink_global = shrunk & self._bottom_global_region
        local_roi = overlap_global.overlap_with(shrink_global)

        view = image.view(local_view)
        view.clear_rect(local_roi, fill_value=0, invert=True, alpha_only=True)
        return image

    def _apply_rotated(self, image: Image) -> Image:
        """Draw alpha-erasing lines along tilted seams for rotated layers."""
        assert self._top_global_region is not None
        assert self._bottom_global_region is not None

        overlap_incoming = self._top_global_region.overlap_with(
            self._bottom_global_region
        )
        axis_y, axis_x = overlap_incoming.to_slice()

        sides = self._shrink.copy()
        if not any(sides.values()):
            return image

        lines = self._build_rotated_lines(sides, axis_y, axis_x)
        if not lines:
            return image

        arr = image[...]
        h, w = arr.shape[:2]
        sy = slice(axis_y.start, min(axis_y.stop, h))
        sx = slice(axis_x.start, min(axis_x.stop, w))
        if sy.start >= sy.stop or sx.start >= sx.stop:
            return image

        overlap_h = sy.stop - sy.start
        overlap_w = sx.stop - sx.start
        line_mask = np.zeros((overlap_h, overlap_w), dtype=np.uint8)
        for pt1, pt2, size in lines:
            cv2.line(line_mask, pt1, pt2, color=255, thickness=2 * size)

        sub_alpha = arr[sy, sx, 3]
        sub_alpha[line_mask > 0] = 0
        return image

    def _build_rotated_lines(
        self,
        sides: dict[str, int],
        axis_y: slice,
        axis_x: slice,
    ) -> list[tuple[tuple[int, int], tuple[int, int], int]]:
        """Compute tilted line endpoints relative to the overlap bounding slice."""
        if self._buf_pts is None:
            return []

        p = self._buf_pts
        corner_pairs = {
            "top": (p[0], p[1]),
            "right": (p[1], p[2]),
            "bottom": (p[3], p[2]),
            "left": (p[0], p[3]),
        }

        lines: list[tuple[tuple[int, int], tuple[int, int], int]] = []
        for side, size in sides.items():
            if side in corner_pairs and size > 0:
                p1, p2 = corner_pairs[side]
                pt1 = (
                    int(round(p1[0] - axis_x.start)),
                    int(round(p1[1] - axis_y.start)),
                )
                pt2 = (
                    int(round(p2[0] - axis_x.start)),
                    int(round(p2[1] - axis_y.start)),
                )
                lines.append((pt1, pt2, size))

        return lines
