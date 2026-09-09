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

    from anifuse.interfaces.estimator import MotionEstimate


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
    ) -> None:
        """Initialize border cut effect with per-side thicknesses or uniform margin.

        Args:
            all: Optional uniform cut thickness applied to all sides.
            left: Cut thickness in pixels for the left edge.
            right: Cut thickness in pixels for the right edge.
            top: Cut thickness in pixels for the top edge.
            bottom: Cut thickness in pixels for the bottom edge.
            min_alpha: Minimum opacity threshold for underlying bottom layer.
        """
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

        self.top_layer: Layer | None = None
        self.bottom_layer: Layer | None = None
        self.motion: MotionEstimate | None = None

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
        """Store layer context and motion estimate."""
        self.top_layer = top
        self.bottom_layer = bottom
        self.motion = motion

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Calculate overlap and cut seams directly on the image."""
        if self.top_layer is None or self.bottom_layer is None:
            return image

        top = self.top_layer
        bottom = self.bottom_layer

        if not top.global_region.overlaps(bottom.global_region):
            return image

        if self.motion is not None and (
            abs(self.motion.angle) > 1e-4 or abs(top.transform.matrix[0, 1]) > 1e-4
        ):
            return self._apply_rotated(image, top, bottom)

        return self._apply_axis_aligned(image, top, bottom)

    def _apply_axis_aligned(self, image: Image, top: Layer, bottom: Layer) -> Image:
        """Erase alpha channel along axis-aligned border seam using Region shrink."""
        dx, dy = (top.global_region - bottom.global_region).top_left

        shrink = self._shrink.copy()
        if dy == 0:
            shrink["top"] = shrink["bottom"] = 0
        if dx == 0:
            shrink["left"] = shrink["right"] = 0

        overlap_global = top.global_region & bottom.global_region
        local_view = top.global_region.overlap_with(overlap_global)

        shrunk = top.global_region.shrink(**shrink)
        if not shrunk.overlaps(bottom.global_region):
            image.clear_rect(local_view, fill_value=0, invert=False, alpha_only=True)
            return image

        shrink_global = shrunk & bottom.global_region
        local_roi = overlap_global.overlap_with(shrink_global)

        view = image.view(local_view)
        view.clear_rect(local_roi, fill_value=0, invert=True, alpha_only=True)
        return image

    def _apply_rotated(self, image: Image, top: Layer, bottom: Layer) -> Image:
        """Draw alpha-erasing lines along tilted seams for rotated layers."""
        overlap_top = top.global_region.overlap_with(bottom.global_region)
        axis_y, axis_x = overlap_top.to_slice()

        sides = self._shrink.copy()
        if not any(sides.values()):
            return image

        lines = self._build_rotated_lines(sides, axis_y, axis_x, top)
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
        top: Layer,
    ) -> list[tuple[tuple[int, int], tuple[int, int], int]]:
        """Compute tilted line endpoints relative to the overlap bounding slice."""
        lines: list[tuple[tuple[int, int], tuple[int, int], int]] = []
        w, h = top.region.size
        corners = np.array(
            [[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], dtype=np.float32
        ).T
        global_corners = (top.transform.matrix @ corners)[:2]
        gx, gy = top.global_region.top_left
        layer_corners = (global_corners - np.array([[gx], [gy]])).T

        corner_pairs = {
            "left": (layer_corners[0], layer_corners[3]),
            "right": (layer_corners[1], layer_corners[2]),
            "top": (layer_corners[0], layer_corners[1]),
            "bottom": (layer_corners[3], layer_corners[2]),
        }

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
