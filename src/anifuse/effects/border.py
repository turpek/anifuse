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


def clip_segment_to_rect(
    p1: np.ndarray,
    p2: np.ndarray,
    w: float,
    h: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Clip a 2D line segment p1->p2 against an axis-aligned rectangle [0, w] x [0, h] via Liang-Barsky."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    p = [-dx, dx, -dy, dy]
    q = [p1[0], w - p1[0], p1[1], h - p1[1]]
    u1, u2 = 0.0, 1.0

    for i in range(4):
        if p[i] == 0.0:
            if q[i] < 0.0:
                return None
        else:
            t = q[i] / p[i]
            if p[i] < 0.0:
                if t > u1:
                    u1 = t
            elif t < u2:
                u2 = t

    if u1 > u2:
        return None

    c1 = np.array([p1[0] + u1 * dx, p1[1] + u1 * dy], dtype=np.float64)
    c2 = np.array([p1[0] + u2 * dx, p1[1] + u2 * dy], dtype=np.float64)
    return c1, c2


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
        self._all = all
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
        self._m_rel: np.ndarray | None = None
        self._m_rel_inv: np.ndarray | None = None
        self._top_size: tuple[int, int] = (0, 0)
        self._bottom_size: tuple[int, int] = (0, 0)
        self._is_rotated: bool = False
        self._buf_pts: np.ndarray | None = None

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

        w_top, h_top = top.region.size.to_int()
        w_bot, h_bot = bottom.region.size.to_int()
        self._top_size = (w_top, h_top)
        self._bottom_size = (w_bot, h_bot)

        m_top = top.matrix
        m_bottom = bottom.matrix
        self._m_rel = np.linalg.inv(m_bottom) @ m_top
        self._m_rel_inv = np.linalg.inv(self._m_rel)

        mat = top.transform.matrix
        self._is_rotated = not (
            np.isclose(mat[0, 1], 0.0, atol=1e-5)
            and np.isclose(mat[1, 0], 0.0, atol=1e-5)
        )

        corners = np.array(
            [
                [0.0, 0.0, 1.0],
                [float(w_top), 0.0, 1.0],
                [float(w_top), float(h_top), 1.0],
                [0.0, float(h_top), 1.0],
            ],
            dtype=np.float32,
        )
        transformed = (mat @ corners.T).T[:, :2]
        self._buf_pts = transformed - np.array(
            top.global_region.top_left, dtype=np.float32
        )

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Calculate overlap and cut seams directly on the image."""
        if (
            self._top_global_region is None
            or self._bottom_global_region is None
            or self._m_rel is None
            or self._m_rel_inv is None
        ):
            return image

        if not self._top_global_region.overlaps(self._bottom_global_region):
            return image

        sides = self._resolve_sides()
        if not any(sides.values()):
            return image

        if self._is_rotated:
            return self._apply_rotated(image, sides)

        return self._apply_axis_aligned(image, sides)

    def _resolve_sides(self) -> dict[str, int]:
        """Determine cut thicknesses for each side based on movement direction or manual configuration."""
        assert self._top_global_region is not None
        assert self._bottom_global_region is not None

        dx, dy = (self._top_global_region - self._bottom_global_region).top_left
        sides = self._shrink.copy()

        if self._all is not None:
            if dy <= 0:
                sides["top"] = 0
            if dy >= 0:
                sides["bottom"] = 0
            if dx <= 0:
                sides["left"] = 0
            if dx >= 0:
                sides["right"] = 0

        return sides

    def _apply_axis_aligned(self, image: Image, sides: dict[str, int]) -> Image:
        """Erase alpha channel along axis-aligned border seam clipped against bottom layer boundary."""
        assert self._m_rel is not None
        assert self._m_rel_inv is not None

        w_top, h_top = self._top_size
        w_bot, h_bot = self._bottom_size
        arr = image[...]

        edge_defs = {
            "top": (
                np.array([0.0, 0.0, 1.0]),
                np.array([float(w_top), 0.0, 1.0]),
            ),
            "bottom": (
                np.array([0.0, float(h_top), 1.0]),
                np.array([float(w_top), float(h_top), 1.0]),
            ),
            "left": (
                np.array([0.0, 0.0, 1.0]),
                np.array([0.0, float(h_top), 1.0]),
            ),
            "right": (
                np.array([float(w_top), 0.0, 1.0]),
                np.array([float(w_top), float(h_top), 1.0]),
            ),
        }

        for side, size in sides.items():
            if size <= 0 or side not in edge_defs:
                continue

            p1, p2 = edge_defs[side]
            p1_bot = (self._m_rel @ p1)[:2]
            p2_bot = (self._m_rel @ p2)[:2]

            clipped = clip_segment_to_rect(p1_bot, p2_bot, float(w_bot), float(h_bot))
            if clipped is None:
                continue

            c1_top = (self._m_rel_inv @ np.array([clipped[0][0], clipped[0][1], 1.0]))[:2]
            c2_top = (self._m_rel_inv @ np.array([clipped[1][0], clipped[1][1], 1.0]))[:2]

            overlap = self._top_global_region & self._bottom_global_region
            overlap_w, overlap_h = overlap.size.to_int()

            if side in ("left", "right"):
                y_min = max(0, int(round(min(c1_top[1], c2_top[1]))))
                y_max = min(h_top, int(round(max(c1_top[1], c2_top[1]))))
                if y_min >= y_max:
                    continue
                effective_size = min(size, overlap_w)
                if side == "left":
                    x_end = min(w_top, effective_size)
                    arr[y_min:y_max, 0:x_end, 3] = 0
                else:
                    x_start = max(0, w_top - effective_size)
                    arr[y_min:y_max, x_start:w_top, 3] = 0
            else:
                x_min = max(0, int(round(min(c1_top[0], c2_top[0]))))
                x_max = min(w_top, int(round(max(c1_top[0], c2_top[0]))))
                if x_min >= x_max:
                    continue
                effective_size = min(size, overlap_h)
                if side == "top":
                    y_end = min(h_top, effective_size)
                    arr[0:y_end, x_min:x_max, 3] = 0
                else:
                    y_start = max(0, h_top - effective_size)
                    arr[y_start:h_top, x_min:x_max, 3] = 0

        return image

    def _apply_rotated(self, image: Image, sides: dict[str, int]) -> Image:
        """Draw alpha-erasing lines along tilted seams clipped against bottom boundary."""
        assert self._top_global_region is not None
        assert self._bottom_global_region is not None
        assert self._m_rel is not None
        assert self._m_rel_inv is not None

        overlap_incoming = self._top_global_region.overlap_with(
            self._bottom_global_region
        )
        axis_y, axis_x = overlap_incoming.to_slice()

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
        if self._m_rel is None or self._m_rel_inv is None:
            return []

        w_top, h_top = self._top_size
        w_bot, h_bot = self._bottom_size
        assert self._top_global_region is not None

        edge_defs = {
            "top": (
                np.array([0.0, 0.0, 1.0]),
                np.array([float(w_top), 0.0, 1.0]),
            ),
            "right": (
                np.array([float(w_top), 0.0, 1.0]),
                np.array([float(w_top), float(h_top), 1.0]),
            ),
            "bottom": (
                np.array([0.0, float(h_top), 1.0]),
                np.array([float(w_top), float(h_top), 1.0]),
            ),
            "left": (
                np.array([0.0, 0.0, 1.0]),
                np.array([0.0, float(h_top), 1.0]),
            ),
        }

        mat = self._buf_pts
        if mat is None:
            return []

        lines: list[tuple[tuple[int, int], tuple[int, int], int]] = []
        for side, size in sides.items():
            if side not in edge_defs or size <= 0:
                continue

            p1, p2 = edge_defs[side]
            p1_bot = (self._m_rel @ p1)[:2]
            p2_bot = (self._m_rel @ p2)[:2]

            clipped = clip_segment_to_rect(p1_bot, p2_bot, float(w_bot), float(h_bot))
            if clipped is None:
                continue

            c1_top = (self._m_rel_inv @ np.array([clipped[0][0], clipped[0][1], 1.0]))[:2]
            c2_top = (self._m_rel_inv @ np.array([clipped[1][0], clipped[1][1], 1.0]))[:2]

            # Project c1_top and c2_top to image coordinates
            # mat is the transformed corners relative to top_left
            # We can interpolate between the original edge corners using the ratio
            p1_orig = edge_defs[side][0][:2]
            p2_orig = edge_defs[side][1][:2]
            edge_len = np.linalg.norm(p2_orig - p1_orig)
            if edge_len < 1e-6:
                continue

            t1 = np.linalg.norm(c1_top - p1_orig) / edge_len
            t2 = np.linalg.norm(c2_top - p1_orig) / edge_len

            corner_pairs = {
                "top": (mat[0], mat[1]),
                "right": (mat[1], mat[2]),
                "bottom": (mat[3], mat[2]),
                "left": (mat[0], mat[3]),
            }
            corner1, corner2 = corner_pairs[side]
            pt_a = corner1 + t1 * (corner2 - corner1)
            pt_b = corner1 + t2 * (corner2 - corner1)

            pt1_img = (
                int(round(pt_a[0] - axis_x.start)),
                int(round(pt_a[1] - axis_y.start)),
            )
            pt2_img = (
                int(round(pt_b[0] - axis_x.start)),
                int(round(pt_b[1] - axis_y.start)),
            )
            lines.append((pt1_img, pt2_img, size))

        return lines
