"""Scene boundary resolver using anchored phase correlation and exposure guards."""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
from aniseek import Direction

if TYPE_CHECKING:
    from anifuse.reader import VideoReader

DEFAULT_MIN_RESPONSE: float = 0.20
DEFAULT_HIGH_EXPOSURE: float = 235.0
DEFAULT_LOW_EXPOSURE: float = 20.0
THUMBNAIL_SIZE: tuple[int, int] = (320, 180)


def to_gray_thumbnail(
    frame_bgr: np.ndarray,
    size: tuple[int, int] = THUMBNAIL_SIZE,
) -> np.ndarray:
    """Convert a BGR frame to a small grayscale thumbnail for fast frequency analysis."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)


def is_abnormal_exposure(
    gray_thumb: np.ndarray,
    high: float = DEFAULT_HIGH_EXPOSURE,
    low: float = DEFAULT_LOW_EXPOSURE,
) -> bool:
    """Return True if image luminance indicates a whiteout flash or blackout fade."""
    mean_luminance = float(np.mean(gray_thumb))
    return mean_luminance > high or mean_luminance < low


class SceneBoundaryResolver:
    """Discovers precise scene boundaries from an internal anchor to filter edge cuts and fades."""

    @classmethod
    def resolve_and_adjust(
        cls,
        reader: VideoReader,
        *,
        min_response: float = DEFAULT_MIN_RESPONSE,
        high_exposure: float = DEFAULT_HIGH_EXPOSURE,
        low_exposure: float = DEFAULT_LOW_EXPOSURE,
    ) -> tuple[int, int]:
        """Probe scene boundaries from an anchor and adjust reader bounds to valid content."""
        aniseek_reader = reader._reader
        frame_ids = list(aniseek_reader.frame_ids)
        if len(frame_ids) < 4:
            return (frame_ids[0], frame_ids[-1]) if frame_ids else (0, 0)

        initial_start = frame_ids[0]
        initial_end = frame_ids[-1]

        # Anchor selection: 1.0s ahead, or midpoint for short sequences
        fps = float(aniseek_reader.fps) if aniseek_reader.fps > 0 else 24.0
        mid_idx = len(frame_ids) // 2
        offset = min(int(fps * 1.0), mid_idx)
        anchor_idx = offset
        anchor_fid = frame_ids[anchor_idx]

        # Read anchor frame
        aniseek_reader.set_frame(anchor_fid)
        aniseek_reader.proceed()
        ret, frame_bgr = aniseek_reader.read()
        if not ret or frame_bgr is None:
            return (initial_start, initial_end)

        anchor_gray = to_gray_thumbnail(frame_bgr)
        if is_abnormal_exposure(anchor_gray, high_exposure, low_exposure):
            anchor_idx = mid_idx
            anchor_fid = frame_ids[anchor_idx]
            aniseek_reader.set_frame(anchor_fid)
            aniseek_reader.proceed()
            ret, frame_bgr = aniseek_reader.read()
            if not ret or frame_bgr is None:
                return (initial_start, initial_end)
            anchor_gray = to_gray_thumbnail(frame_bgr)

        # 1. Backward scan from anchor to start
        real_start_fid = cls._scan_backward(
            aniseek_reader=aniseek_reader,
            anchor_fid=anchor_fid,
            anchor_gray=anchor_gray,
            min_fid=initial_start,
            min_response=min_response,
            high_exposure=high_exposure,
            low_exposure=low_exposure,
        )

        # 2. Forward scan from anchor to end
        real_end_fid = cls._scan_forward(
            aniseek_reader=aniseek_reader,
            anchor_fid=anchor_fid,
            anchor_gray=anchor_gray,
            max_fid=initial_end,
            min_response=min_response,
            high_exposure=high_exposure,
            low_exposure=low_exposure,
        )

        # 3. Apply resolved bounds to the reader
        if real_start_fid != initial_start or real_end_fid != initial_end:
            aniseek_reader.set_bounds(real_start_fid, real_end_fid + 1)

        if aniseek_reader.direction == Direction.REVERSE:
            aniseek_reader.set_frame(real_end_fid)
            aniseek_reader.rewind()
        else:
            aniseek_reader.set_frame(real_start_fid)
            aniseek_reader.proceed()

        return (real_start_fid, real_end_fid)

    @classmethod
    def _scan_backward(
        cls,
        aniseek_reader: object,
        anchor_fid: int,
        anchor_gray: np.ndarray,
        min_fid: int,
        min_response: float,
        high_exposure: float,
        low_exposure: float,
    ) -> int:
        aniseek_reader.set_frame(anchor_fid)
        aniseek_reader.rewind()

        prev_gray = anchor_gray
        last_valid_fid = anchor_fid
        real_start_fid = min_fid

        while True:
            ret, frame_bgr = aniseek_reader.read()
            fid = aniseek_reader.frame_id
            if not ret or frame_bgr is None or fid is None or fid < min_fid:
                break

            cur_gray = to_gray_thumbnail(frame_bgr)
            if is_abnormal_exposure(cur_gray, high_exposure, low_exposure):
                real_start_fid = last_valid_fid
                break

            _, response = cv2.phaseCorrelate(
                prev_gray.astype(np.float32),
                cur_gray.astype(np.float32),
            )
            if response < min_response:
                real_start_fid = last_valid_fid
                break

            last_valid_fid = fid
            prev_gray = cur_gray
            real_start_fid = fid

        return real_start_fid

    @classmethod
    def _scan_forward(
        cls,
        aniseek_reader: object,
        anchor_fid: int,
        anchor_gray: np.ndarray,
        max_fid: int,
        min_response: float,
        high_exposure: float,
        low_exposure: float,
    ) -> int:
        aniseek_reader.set_frame(anchor_fid)
        aniseek_reader.proceed()

        prev_gray = anchor_gray
        last_valid_fid = anchor_fid
        real_end_fid = max_fid

        while True:
            ret, frame_bgr = aniseek_reader.read()
            fid = aniseek_reader.frame_id
            if not ret or frame_bgr is None or fid is None or fid > max_fid:
                break

            cur_gray = to_gray_thumbnail(frame_bgr)
            if is_abnormal_exposure(cur_gray, high_exposure, low_exposure):
                real_end_fid = last_valid_fid
                break

            _, response = cv2.phaseCorrelate(
                prev_gray.astype(np.float32),
                cur_gray.astype(np.float32),
            )
            if response < min_response:
                real_end_fid = last_valid_fid
                break

            last_valid_fid = fid
            prev_gray = cur_gray
            real_end_fid = fid

        return real_end_fid
