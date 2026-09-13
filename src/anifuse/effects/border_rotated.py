"""Rotated and scale border seam cut effect using morphological erosion and anicrop ScratchBuffer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
from anicrop import ImageFormat, Region, ScratchBuffer
from anicrop.composition import flatten

from anifuse.interfaces.effect import AnifuseEffect, LayerTarget

if TYPE_CHECKING:
    import numpy as np
    from anicrop.effect import Effect
    from anicrop.image import Image
    from anicrop.layer import Layer


class RotatedBorderCutEffect(AnifuseEffect):
    """Cuts border seams on rotated or scaled layers using morphological erosion with anicrop ScratchBuffer."""

    target: LayerTarget = LayerTarget.TOP

    _scratch_buf: ScratchBuffer = ScratchBuffer()
    _scratch_eroded: ScratchBuffer = ScratchBuffer()

    def __init__(
        self,
        size: int = 15,
        *,
        min_alpha: int = 250,
        visible: bool = True,
        name: str = "RotatedBorderCut",
    ) -> None:
        """Initialize rotated border cut effect.

        Args:
            size: Border cut thickness in pixels.
            min_alpha: Minimum opacity threshold for underlying bottom layer.
            visible: Whether the effect is active in the render pipeline.
            name: Human-readable identifier for the effect.
        """
        super().__init__(visible=visible, name=name)
        self.size = size
        self.min_alpha = min_alpha
        self._counter: int = 0
        self._buf_size: tuple[int, int] | None = None
        self._sl_buf: tuple[slice, slice] | None = None
        self._sl_top: tuple[slice, slice] | None = None
        self._bot_mask: np.ndarray | None = None

    def get_padding(self) -> tuple[int, int, int, int]:
        """Return zero padding as border cutting does not expand bounds."""
        return (0, 0, 0, 0)

    def merge(self, other: Effect, matrix: np.ndarray) -> Effect | None:
        """Return None as border cutting cannot be analytically merged."""
        return None

    def update(self, top: Layer, bottom: Layer) -> None:
        """Pre-calculate expanded overlap, zero-padded buffer slices, and bottom opacity mask."""
        self._counter = 0
        if not top.global_region.overlaps(bottom.global_region) or self.size <= 0:
            self._counter = 1
            return

        overlap = top.global_region & bottom.global_region
        expanded = overlap.expand(all=self.size)
        expanded_bot = expanded & bottom.global_region
        top_in_exp = top.global_region & expanded_bot

        w, h = expanded_bot.size.to_int()
        if w <= 0 or h <= 0 or top_in_exp.area <= 0:
            self._counter = 1
            return

        sl_buf = expanded_bot.overlap_with(top_in_exp).to_slice()
        sl_top = top.global_region.overlap_with(top_in_exp).to_slice()

        has_rot = (
            abs(bottom.transform.matrix[0, 1]) > 1e-4
            or abs(bottom.transform.matrix[1, 0]) > 1e-4
        )
        if has_rot:
            rendered = flatten([bottom])
            b_img = rendered.edits[0].image
            b_sy, b_sx = rendered.global_region.overlap_with(top_in_exp).to_slice()
            b_arr = b_img[...]
            bot_alpha = b_arr[b_sy, b_sx, 3]
        else:
            b_arr = bottom.edits[0].image[...]
            b_sy, b_sx = bottom.global_region.overlap_with(top_in_exp).to_slice()
            bot_alpha = b_arr[b_sy, b_sx, 3]

        h_clip = sl_top[0].stop - sl_top[0].start
        w_clip = sl_top[1].stop - sl_top[1].start
        if h_clip <= 0 or w_clip <= 0:
            self._counter = 1
            return

        self._buf_size = (w, h)
        self._sl_buf = sl_buf
        self._sl_top = sl_top
        self._bot_mask = bot_alpha[:h_clip, :w_clip] >= self.min_alpha

    @staticmethod
    def _get_buffer(scratch: ScratchBuffer, w: int, h: int) -> np.ndarray:
        """Configure ScratchBuffer and return a 2D ndarray view for OpenCV operations."""
        scratch.configure(size=(w, h), fmt=ImageFormat.GRAY)
        return scratch[Region.from_size(w, h)][..., 0]

    def apply(self, image: Image, matrix: np.ndarray) -> Image:
        """Sample alpha across layers and cut seam on top layer using erosion on expanded zero-padded buffer."""
        if self._counter == 0:
            assert self._buf_size is not None
            assert self._sl_buf is not None
            assert self._sl_top is not None
            assert self._bot_mask is not None

            w_buf, h_buf = self._buf_size
            buf = self._get_buffer(self._scratch_buf, w_buf, h_buf)
            buf.fill(0)

            top_arr = image[...]
            sl_buf_y, sl_buf_x = self._sl_buf
            sl_top_y, sl_top_x = self._sl_top

            buf[sl_buf_y, sl_buf_x] = top_arr[sl_top_y, sl_top_x, 3]

            buf_eroded = self._get_buffer(self._scratch_eroded, w_buf, h_buf)
            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, (2 * self.size + 1, 2 * self.size + 1)
            )
            cv2.erode(buf, kernel, dst=buf_eroded)

            buf_top_orig = buf[sl_buf_y, sl_buf_x]
            buf_top_eroded = buf_eroded[sl_buf_y, sl_buf_x]
            cut_mask = buf_top_orig > buf_top_eroded

            cut = cut_mask & self._bot_mask
            top_arr[sl_top_y, sl_top_x, 3][cut] = 0

        self._counter += 1
        return image
