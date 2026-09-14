"""Rotated and scale border seam cut effect using morphological erosion and anicrop ScratchBuffer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
from anicrop import ImageFormat, Region, ScratchBuffer

from anifuse.interfaces.effect import AnifuseEffect, LayerTarget

if TYPE_CHECKING:
    from anicrop.effect import Effect
    from anicrop.image import Image
    from anicrop.layer import Layer


class RotatedBorderCutEffect(AnifuseEffect):
    """Cuts border seams on rotated or scaled layers using morphological erosion with anicrop ScratchBuffer."""

    target: LayerTarget = LayerTarget.BOTH

    _scratch_buf: ScratchBuffer = ScratchBuffer()
    _scratch_eroded: ScratchBuffer = ScratchBuffer()

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
        name: str = "RotatedBorderCut",
    ) -> None:
        """Initialize rotated border cut effect with per-side thicknesses or uniform margin.

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
            self._shrink = {k: all for k in self._shrink}
        elif not any((left, right, top, bottom)):
            self._all = 15
            self._shrink = {k: 15 for k in self._shrink}

        self.min_alpha = min_alpha
        self._counter: int = 0
        self._top_image: Image | None = None
        self._buf_size: tuple[int, int] | None = None
        self._sl_buf: tuple[slice, slice] | None = None
        self._sl_top: tuple[slice, slice] | None = None
        self._sl_bot: tuple[slice, slice] | None = None

    def get_padding(self) -> tuple[int, int, int, int]:
        """Return zero padding as border cutting does not expand bounds."""
        return (0, 0, 0, 0)

    def merge(self, other: Effect, matrix: np.ndarray) -> Effect | None:
        """Return None as border cutting cannot be analytically merged."""
        return None

    def update(self, top: Layer, bottom: Layer) -> None:
        """Pre-calculate expanded overlap and zero-padded buffer slices without rasterizing bottom."""
        self._counter = 0
        self._top_image = None
        max_cut = max(self._shrink.values())
        if not top.global_region.overlaps(bottom.global_region) or max_cut <= 0:
            self._counter = 2
            return

        overlap = top.global_region & bottom.global_region
        expanded = overlap.expand(
            left=self._shrink["left"],
            right=self._shrink["right"],
            top=self._shrink["top"],
            bottom=self._shrink["bottom"],
        )
        expanded_bot = expanded & bottom.global_region
        top_in_exp = top.global_region & expanded_bot

        w, h = expanded_bot.size.to_int()
        if w <= 0 or h <= 0 or top_in_exp.area <= 0:
            self._counter = 2
            return

        self._buf_size = (w, h)
        self._sl_buf = expanded_bot.overlap_with(top_in_exp).to_slice()
        self._sl_top = top.global_region.overlap_with(top_in_exp).to_slice()
        self._sl_bot = bottom.global_region.overlap_with(top_in_exp).to_slice()

    @staticmethod
    def _get_buffer(scratch: ScratchBuffer, w: int, h: int) -> np.ndarray:
        """Configure ScratchBuffer and return a 2D ndarray view for OpenCV operations."""
        scratch.configure(size=(w, h), fmt=ImageFormat.GRAY)
        return scratch[Region.from_size(w, h)][..., 0]

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Sample alpha across layers and cut seam on top layer in two-pass traversal."""
        if self._counter == 0:
            self._top_image = image
            self._counter += 1
            return image

        if self._counter == 1:
            if self._top_image is not None and self._buf_size is not None:
                assert self._sl_buf is not None
                assert self._sl_top is not None
                assert self._sl_bot is not None

                w_buf, h_buf = self._buf_size
                buf = self._get_buffer(self._scratch_buf, w_buf, h_buf)
                buf.fill(0)

                top_arr = self._top_image[...]
                sl_buf_y, sl_buf_x = self._sl_buf
                sl_top_y, sl_top_x = self._sl_top
                sl_bot_y, sl_bot_x = self._sl_bot

                buf[sl_buf_y, sl_buf_x] = top_arr[sl_top_y, sl_top_x, 3]

                buf_eroded = self._get_buffer(self._scratch_eroded, w_buf, h_buf)

                left = self._shrink["left"]
                right = self._shrink["right"]
                top_cut = self._shrink["top"]
                bot_cut = self._shrink["bottom"]

                if left == right == top_cut == bot_cut:
                    kernel = cv2.getStructuringElement(
                        cv2.MORPH_RECT, (2 * left + 1, 2 * left + 1)
                    )
                    cv2.erode(buf, kernel, dst=buf_eroded)
                else:
                    buf_eroded[...] = buf[...]
                    if left > 0:
                        k_left = np.ones((1, left + 1), dtype=np.uint8)
                        eroded_l = cv2.erode(buf, k_left, anchor=(left, 0))
                        np.minimum(buf_eroded, eroded_l, out=buf_eroded)
                    if right > 0:
                        k_right = np.ones((1, right + 1), dtype=np.uint8)
                        eroded_r = cv2.erode(buf, k_right, anchor=(0, 0))
                        np.minimum(buf_eroded, eroded_r, out=buf_eroded)
                    if top_cut > 0:
                        k_top = np.ones((top_cut + 1, 1), dtype=np.uint8)
                        eroded_t = cv2.erode(buf, k_top, anchor=(0, top_cut))
                        np.minimum(buf_eroded, eroded_t, out=buf_eroded)
                    if bot_cut > 0:
                        k_bot = np.ones((bot_cut + 1, 1), dtype=np.uint8)
                        eroded_b = cv2.erode(buf, k_bot, anchor=(0, 0))
                        np.minimum(buf_eroded, eroded_b, out=buf_eroded)

                buf_top_orig = buf[sl_buf_y, sl_buf_x]
                buf_top_eroded = buf_eroded[sl_buf_y, sl_buf_x]
                cut_mask = buf_top_orig > buf_top_eroded

                bot_arr = image[...]
                h_clip = sl_top_y.stop - sl_top_y.start
                w_clip = sl_top_x.stop - sl_top_x.start
                bot_alpha = bot_arr[sl_bot_y, sl_bot_x, 3][:h_clip, :w_clip]
                bot_mask = bot_alpha >= self.min_alpha

                cut = cut_mask & bot_mask
                top_arr[sl_top_y, sl_top_x, 3][cut] = 0
                self._top_image = None

            self._counter += 1
            return image

        return image
