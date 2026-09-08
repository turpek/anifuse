"""Border seam cut effect for canvas overlap transitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
from anicrop.composition import flatten

from anifuse.config import config
from anifuse.interfaces.effect import AnifuseEffect, LayerTarget

if TYPE_CHECKING:
    from anicrop.effect import Effect
    from anicrop.image import Image
    from anicrop.layer import Layer
    from anicrop.spatial import Region

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
        min_alpha: int = 250,
    ) -> None:
        """Initialize border cut effect with uniform or per-side thickness.

        Args:
            cut_size: Uniform cut thickness in pixels for automatically detected sides.
                Defaults to config.border_cut_size if None and no manual sides are specified.
            left: Explicit cut thickness in pixels for the left edge.
            right: Explicit cut thickness in pixels for the right edge.
            top: Explicit cut thickness in pixels for the top edge.
            bottom: Explicit cut thickness in pixels for the bottom edge.
            min_alpha: Minimum opacity threshold for the underlying bottom layer to allow
                cutting. Prevents creating transparent tears/holes in unrendered voids.
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
        self.min_alpha = min_alpha
        self._slices: list[tuple[slice, slice]] = []
        self._lines: list[tuple[tuple[int, int], tuple[int, int], int]] = []
        self._overlap_slice: tuple[slice, slice] | None = None
        self._bottom_mask: np.ndarray | None = None

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
        """Calculate overlap region, active edge cut geometries, and underlying opacity."""
        self._slices = []
        self._lines = []
        self._overlap_slice = None
        self._bottom_mask = None

        if not top.global_region.overlaps(bottom.global_region):
            return

        overlap_top = top.global_region.overlap_with(bottom.global_region)
        overlap_bottom = bottom.global_region.overlap_with(top.global_region)

        axis_y, axis_x = overlap_top.to_slice()
        self._overlap_slice = (axis_y, axis_x)

        expected_shape = (axis_y.stop - axis_y.start, axis_x.stop - axis_x.start)
        self._bottom_mask = self._extract_bottom_mask(
            bottom, overlap_bottom, expected_shape
        )

        sides = self._resolve_sides(top, bottom)

        if abs(motion.angle) > 1e-4 or abs(top.transform.matrix[0, 1]) > 1e-4:
            self._lines = self._build_rotated_lines(
                sides, axis_y, axis_x, top
            )
        else:
            self._slices = self._build_axis_aligned_slices(
                sides, axis_y, axis_x
            )

    def _extract_bottom_mask(
        self,
        bottom: Layer,
        overlap_bottom: Region,
        expected_shape: tuple[int, int],
    ) -> np.ndarray | None:
        """Extract boolean opacity mask from bottom layer over the overlap region."""
        has_rot = (
            abs(bottom.transform.matrix[0, 1]) > 1e-4
            or abs(bottom.transform.matrix[1, 0]) > 1e-4
        )
        if has_rot:
            rendered = flatten([bottom])
            b_img = rendered.edits[0].image
            b_sy, b_sx = rendered.global_region.overlap_with(
                bottom.global_region
            ).to_slice()
        else:
            b_img = bottom.edits[0].image
            b_sy, b_sx = overlap_bottom.to_slice()

        b_arr = b_img[...]
        if b_arr.ndim < 3 or b_arr.shape[2] != 4:
            return np.ones(expected_shape, dtype=bool)

        bh, bw = b_arr.shape[:2]
        clamped_y = slice(max(0, b_sy.start), min(bh, b_sy.stop))
        clamped_x = slice(max(0, b_sx.start), min(bw, b_sx.stop))
        if clamped_y.start >= clamped_y.stop or clamped_x.start >= clamped_x.stop:
            return None

        sub_b_alpha = b_arr[clamped_y, clamped_x, 3]
        return sub_b_alpha >= self.min_alpha

    def _resolve_sides(self, top: Layer, bottom: Layer) -> dict[str, int]:
        """Determine active cut sides and thicknesses via manual configuration or Canvas movement."""
        if self.manual_sides:
            return self.manual_sides

        dx, dy = (top.global_region - bottom.global_region).top_left
        sides: dict[str, int] = {}
        if self.cut_size > 0:
            if dx > 0:
                sides["left"] = self.cut_size
            elif dx < 0:
                sides["right"] = self.cut_size
            if dy > 0:
                sides["top"] = self.cut_size
            elif dy < 0:
                sides["bottom"] = self.cut_size
        return sides

    def _build_axis_aligned_slices(
        self,
        sides: dict[str, int],
        axis_y: slice,
        axis_x: slice,
    ) -> list[tuple[slice, slice]]:
        """Construct rectangular slicing bounds aligned with Cartesian image axes."""
        slices: list[tuple[slice, slice]] = []
        for side, size in sides.items():
            if size <= 0:
                continue
            if side == "left":
                slices.append(
                    (
                        axis_y,
                        slice(axis_x.start, min(axis_x.stop, axis_x.start + size)),
                    )
                )
            elif side == "right":
                slices.append(
                    (
                        axis_y,
                        slice(max(axis_x.start, axis_x.stop - size), axis_x.stop),
                    )
                )
            elif side == "top":
                slices.append(
                    (
                        slice(axis_y.start, min(axis_y.stop, axis_y.start + size)),
                        axis_x,
                    )
                )
            elif side == "bottom":
                slices.append(
                    (
                        slice(max(axis_y.start, axis_y.stop - size), axis_y.stop),
                        axis_x,
                    )
                )
        return slices

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

    def _apply_rotated_lines(self, arr: np.ndarray) -> None:
        """Draw alpha-erasing lines onto the overlap region using cv2.line."""
        if self._overlap_slice is None:
            return
        axis_y, axis_x = self._overlap_slice
        h, w = arr.shape[:2]
        sy = slice(axis_y.start, min(axis_y.stop, h))
        sx = slice(axis_x.start, min(axis_x.stop, w))
        if sy.start >= sy.stop or sx.start >= sx.stop:
            return

        overlap_h = sy.stop - sy.start
        overlap_w = sx.stop - sx.start
        line_mask = np.zeros((overlap_h, overlap_w), dtype=np.uint8)
        for pt1, pt2, size in self._lines:
            cv2.line(line_mask, pt1, pt2, color=255, thickness=2 * size)

        cut_mask = line_mask > 0
        if self._bottom_mask is not None:
            bm = self._bottom_mask
            mh, mw = min(overlap_h, bm.shape[0]), min(overlap_w, bm.shape[1])
            cut_mask[:mh, :mw] = cut_mask[:mh, :mw] & bm[:mh, :mw]
            if overlap_h > mh:
                cut_mask[mh:, :] = False
            if overlap_w > mw:
                cut_mask[:, mw:] = False

        sub_alpha = arr[sy, sx, 3]
        sub_alpha[cut_mask] = 0

    def _apply_axis_aligned_slices(self, arr: np.ndarray) -> None:
        """Erase rectangular slices in-place along orthogonal layer edges."""
        if self._overlap_slice is None:
            return
        axis_y, axis_x = self._overlap_slice
        h, w = arr.shape[:2]
        sy = slice(axis_y.start, min(axis_y.stop, h))
        sx = slice(axis_x.start, min(axis_x.stop, w))
        if sy.start >= sy.stop or sx.start >= sx.stop:
            return

        overlap_h = sy.stop - sy.start
        overlap_w = sx.stop - sx.start
        cut_mask = np.zeros((overlap_h, overlap_w), dtype=bool)

        for s_box_y, s_box_x in self._slices:
            rel_y_start = max(0, s_box_y.start - sy.start)
            rel_y_stop = min(overlap_h, s_box_y.stop - sy.start)
            rel_x_start = max(0, s_box_x.start - sx.start)
            rel_x_stop = min(overlap_w, s_box_x.stop - sx.start)
            if rel_y_start < rel_y_stop and rel_x_start < rel_x_stop:
                cut_mask[rel_y_start:rel_y_stop, rel_x_start:rel_x_stop] = True

        if self._bottom_mask is not None:
            bm = self._bottom_mask
            mh, mw = min(overlap_h, bm.shape[0]), min(overlap_w, bm.shape[1])
            cut_mask[:mh, :mw] = cut_mask[:mh, :mw] & bm[:mh, :mw]
            if overlap_h > mh:
                cut_mask[mh:, :] = False
            if overlap_w > mw:
                cut_mask[:, mw:] = False

        sub_alpha = arr[sy, sx, 3]
        sub_alpha[cut_mask] = 0

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Erase alpha channel in-place along calculated border seam slices or lines."""
        arr = image[...]
        if arr.ndim < 3 or arr.shape[2] != 4:
            return image

        if self._lines:
            self._apply_rotated_lines(arr)
        if self._slices:
            self._apply_axis_aligned_slices(arr)

        return image
