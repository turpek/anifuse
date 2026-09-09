"""ORB feature-based estimators for pure translation and full affine transformations."""

from __future__ import annotations

from collections.abc import Callable
from statistics import StatisticsError, mode

import cv2
import numpy as np
from anicrop import ScratchBuffer, transform_image
from anicrop.enums import ImageFormat, InterpMode
from anicrop.image import Image

from anifuse.interfaces import Estimator, MotionEstimate


def discrete_mode(diff: np.ndarray) -> tuple[float, float]:
    """Calculate the discrete statistical mode along each axis for displacement vectors.

    Args:
        diff: 2D NumPy array of shape (N, 2) representing coordinate differences.

    Returns:
        Tuple of (delx, dely) displacement.
    """
    if len(diff) == 0:
        return 0.0, 0.0

    try:
        delx = float(mode(diff[:, 0]))
        dely = float(mode(diff[:, 1]))
    except (StatisticsError, ValueError):
        delx = float(np.median(diff[:, 0]))
        dely = float(np.median(diff[:, 1]))

    return delx, dely


def resize_image(
    mat: np.ndarray,
    scale: float,
    interp: InterpMode = InterpMode.LANCZOS,
) -> np.ndarray:
    """Resize an image array along X and Y axes without any rotational skew.

    Args:
        mat: Input image NumPy array (H, W) or (H, W, C).
        scale: Scale multiplier (e.g. 1.0 / detected_scale).
        interp: Interpolation mode from anicrop.enums (defaults to InterpMode.LANCZOS).

    Returns:
        Resized image array.
    """
    height, width = mat.shape[:2]
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    return cv2.resize(mat, (new_w, new_h), interpolation=interp.value)


class _BaseOrbEstimator(Estimator):
    """Internal base helper managing shared ORB detector and matcher instances."""

    def __init__(
        self,
        max_features: int = 5000,
        distance_threshold: float = 40.0,
        nbest: int = 40,
        translation_metric: Callable[[np.ndarray], tuple[float, float]] = discrete_mode,
        fast_threshold: int = 10,
    ) -> None:
        self.max_features = max_features
        self.distance_threshold = distance_threshold
        self.nbest = nbest
        self.translation_metric = translation_metric
        self.fast_threshold = fast_threshold

        self._orb = cv2.ORB_create(  # type: ignore[attr-defined]
            nfeatures=max_features,
            scoreType=cv2.ORB_FAST_SCORE,
            fastThreshold=self.fast_threshold,
        )
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self._scratch = ScratchBuffer()
        self._mask_scratch = ScratchBuffer()

    def _to_gray(self, img: Image) -> np.ndarray:
        return img.to_uint8().to_format(ImageFormat.GRAY)[...].squeeze()

    def _detect_and_compute(
        self,
        gray: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> tuple[list[cv2.KeyPoint] | None, np.ndarray | None]:
        """Detect keypoints and compute descriptors on a single grayscale image."""
        kp, desc = self._orb.detectAndCompute(gray, mask)
        if desc is None or len(kp) < 4:
            return None, None
        return kp, desc

    def _match_descriptors(
        self,
        desc1: np.ndarray,
        desc2: np.ndarray,
    ) -> tuple[list[cv2.DMatch], list[cv2.DMatch]]:
        """Match descriptors using BFMatcher with distance filtering."""
        matches = sorted(self._matcher.match(desc1, desc2), key=lambda x: x.distance)
        valid = [m for m in matches if m.distance < self.distance_threshold]
        if len(valid) < 4:
            valid = matches[: max(4, len(matches))]
        return matches, valid

    def _extract_matches(
        self,
        gray1: np.ndarray,
        gray2: np.ndarray,
        mask: np.ndarray | None = None,
        cached_ref: tuple[list[cv2.KeyPoint], np.ndarray] | None = None,
    ) -> tuple[
        list[cv2.KeyPoint] | None,
        np.ndarray | None,
        list[cv2.KeyPoint] | None,
        list[cv2.DMatch],
        list[cv2.DMatch],
    ]:
        """Extract features and match descriptors between reference and incoming images.

        If cached_ref is supplied, avoids recomputing keypoints and descriptors on gray1.
        """
        if cached_ref is not None:
            kp1, desc1 = cached_ref
        else:
            kp1, desc1 = self._detect_and_compute(gray1, None)

        kp2, desc2 = self._detect_and_compute(gray2, mask)

        if kp1 is None or desc1 is None or kp2 is None or desc2 is None:
            return None, None, None, [], []

        matches, valid = self._match_descriptors(desc1, desc2)
        return kp1, desc1, kp2, matches, valid

    def _calculate_confidence(
        self,
        diff: np.ndarray,
        delx: float,
        dely: float,
        valid_count: int,
    ) -> float:
        """Calculate scale-independent motion confidence based on consensus and inlier volume."""
        if len(diff) == 0:
            return 0.0
        min_required = min(self.nbest, 20)
        volume_factor = min(1.0, float(valid_count / max(1, min_required)))
        inliers = (np.abs(diff[:, 0] - delx) <= 2) & (np.abs(diff[:, 1] - dely) <= 2)
        consensus_factor = float(np.sum(inliers) / len(diff))
        return float(volume_factor * consensus_factor)


class OrbTranslationEstimator(_BaseOrbEstimator):
    """Fast single-pass motion estimator for pure translation pan shots."""

    def __init__(
        self,
        max_features: int = 5000,
        distance_threshold: float = 40.0,
        nbest: int = 40,
        translation_metric: Callable[[np.ndarray], tuple[float, float]] = discrete_mode,
        fast_threshold: int = 10,
    ) -> None:
        super().__init__(
            max_features=max_features,
            distance_threshold=distance_threshold,
            nbest=nbest,
            translation_metric=translation_metric,
            fast_threshold=fast_threshold,
        )

    def estimate(
        self,
        ref: Image,
        incoming: Image,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, Image]:
        """Estimate 2D translation in a single pass, returning the unmodified incoming frame."""
        gray1 = self._to_gray(ref)
        gray2 = self._to_gray(incoming)

        kp1, _, kp2, matches, valid = self._extract_matches(gray1, gray2, mask=mask)
        if kp1 is None or kp2 is None or len(valid) < 4:
            return MotionEstimate(confidence=0.0), incoming

        n_use = min(self.nbest, len(matches))
        coords1 = [kp1[m.queryIdx].pt for m in matches[:n_use]]
        coords2 = [kp2[m.trainIdx].pt for m in matches[:n_use]]
        diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

        delx, dely = self.translation_metric(diff)
        confidence = self._calculate_confidence(diff, delx, dely, len(valid))

        estimate = MotionEstimate(
            dx=delx,
            dy=dely,
            angle=0.0,
            scale=1.0,
            confidence=confidence,
        )
        return estimate, incoming


class OrbTransformEstimator(_BaseOrbEstimator):
    """Two-stage affine estimator handling camera rotation, scale, and translation."""

    def __init__(
        self,
        max_features: int = 5000,
        distance_threshold: float = 40.0,
        nbest: int = 40,
        translation_metric: Callable[[np.ndarray], tuple[float, float]] = discrete_mode,
        interp: InterpMode = InterpMode.LANCZOS,
        rotate_threshold: float = 0.10,
        scale_threshold: float = 0.0010,
        fast_threshold: int = 10,
    ) -> None:
        super().__init__(
            max_features=max_features,
            distance_threshold=distance_threshold,
            nbest=nbest,
            translation_metric=translation_metric,
            fast_threshold=fast_threshold,
        )
        self.interp = interp
        self.rotate_threshold = rotate_threshold
        self.scale_threshold = scale_threshold

    def estimate(
        self,
        ref: Image,
        incoming: Image,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, Image]:
        """Estimate rotation and scale, rotating the frame if necessary, then refine translation."""
        gray1 = self._to_gray(ref)
        gray2 = self._to_gray(incoming)

        kp1, desc1, kp2, matches, valid = self._extract_matches(
            gray1, gray2, mask=mask
        )
        if kp1 is None or desc1 is None or kp2 is None or len(valid) < 4:
            return MotionEstimate(confidence=0.0), incoming

        pts1 = np.array([kp1[m.queryIdx].pt for m in valid], dtype=np.float32).reshape(
            -1, 1, 2
        )
        pts2 = np.array([kp2[m.trainIdx].pt for m in valid], dtype=np.float32).reshape(
            -1, 1, 2
        )

        matrix_inv, _ = cv2.estimateAffinePartial2D(pts1, pts2)
        if matrix_inv is not None:
            raw_scale = float(np.sqrt(np.linalg.det(matrix_inv[:2, :2])))
            raw_angle = float(
                np.arctan2(matrix_inv[1, 0], matrix_inv[0, 0]) * (180.0 / np.pi)
            )
        else:
            raw_scale, raw_angle = 1.0, 0.0

        has_rotation = abs(raw_angle) > self.rotate_threshold
        has_scale = abs(1.0 - raw_scale) > self.scale_threshold

        angle = raw_angle if has_rotation else 0.0
        scale = raw_scale if has_scale else 1.0

        if has_rotation or has_scale:
            apply_angle = angle
            apply_scale = (1.0 / scale) if has_scale else 1.0

            if not has_rotation:
                transformed_arr = resize_image(
                    incoming[...], apply_scale, interp=self.interp
                )
                transformed_incoming = Image(transformed_arr, incoming.format)
                transformed_mask = (
                    resize_image(mask, apply_scale, interp=InterpMode.NEAREST)
                    if mask is not None
                    else None
                )
            else:
                transformed_incoming = transform_image(
                    incoming,
                    angle=-apply_angle,
                    scale=apply_scale,
                    interp=self.interp,
                    dst=self._scratch,
                )
                transformed_mask = (
                    transform_image(
                        Image(mask, ImageFormat.GRAY),
                        angle=-apply_angle,
                        scale=apply_scale,
                        interp=InterpMode.NEAREST,
                        dst=self._mask_scratch,
                    )[...]
                    if mask is not None
                    else None
                )

            gray2_transformed = self._to_gray(transformed_incoming)

            kp1_r, _, kp2_r, matches_r, valid_r = self._extract_matches(
                gray1,
                gray2_transformed,
                mask=transformed_mask,
                cached_ref=(kp1, desc1),
            )

            if kp1_r is None or kp2_r is None or len(valid_r) < 4:
                return MotionEstimate(confidence=0.0), transformed_incoming

            n_use = min(self.nbest, len(matches_r))
            coords1 = [kp1_r[m.queryIdx].pt for m in matches_r[:n_use]]
            coords2 = [kp2_r[m.trainIdx].pt for m in matches_r[:n_use]]
            diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

            delx, dely = self.translation_metric(diff)
            confidence = self._calculate_confidence(diff, delx, dely, len(valid_r))

            estimate = MotionEstimate(
                dx=delx,
                dy=dely,
                angle=angle,
                scale=scale,
                confidence=confidence,
            )
            return estimate, transformed_incoming

        # Single step (no significant transform): compute translation directly
        n_use = min(self.nbest, len(matches))
        coords1 = [kp1[m.queryIdx].pt for m in matches[:n_use]]
        coords2 = [kp2[m.trainIdx].pt for m in matches[:n_use]]
        diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

        delx, dely = self.translation_metric(diff)
        confidence = self._calculate_confidence(diff, delx, dely, len(valid))

        estimate = MotionEstimate(
            dx=delx,
            dy=dely,
            angle=0.0,
            scale=1.0,
            confidence=confidence,
        )
        return estimate, incoming


class OrbRotationEstimator(_BaseOrbEstimator):
    """Specialized estimator for pan shots with camera rotation / roll changes.

    Disregards rotational noise below rotate_threshold, and incorporates scale if present.
    """

    def __init__(
        self,
        max_features: int = 5000,
        distance_threshold: float = 40.0,
        nbest: int = 40,
        translation_metric: Callable[[np.ndarray], tuple[float, float]] = discrete_mode,
        interp: InterpMode = InterpMode.LANCZOS,
        rotate_threshold: float = 0.10,
        scale_threshold: float = 0.0010,
        fast_threshold: int = 10,
    ) -> None:
        super().__init__(
            max_features=max_features,
            distance_threshold=distance_threshold,
            nbest=nbest,
            translation_metric=translation_metric,
            fast_threshold=fast_threshold,
        )
        self.interp = interp
        self.rotate_threshold = rotate_threshold
        self.scale_threshold = scale_threshold

    def estimate(
        self,
        ref: Image,
        incoming: Image,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, Image]:
        """Estimate rotation, rotating incoming frame if needed, then refine translation."""
        gray1 = self._to_gray(ref)
        gray2 = self._to_gray(incoming)

        kp1, desc1, kp2, matches, valid = self._extract_matches(
            gray1, gray2, mask=mask
        )
        if kp1 is None or desc1 is None or kp2 is None or len(valid) < 4:
            return MotionEstimate(confidence=0.0), incoming

        pts1 = np.array([kp1[m.queryIdx].pt for m in valid], dtype=np.float32).reshape(
            -1, 1, 2
        )
        pts2 = np.array([kp2[m.trainIdx].pt for m in valid], dtype=np.float32).reshape(
            -1, 1, 2
        )

        matrix_inv, _ = cv2.estimateAffinePartial2D(pts1, pts2)
        if matrix_inv is not None:
            raw_scale = float(np.sqrt(np.linalg.det(matrix_inv[:2, :2])))
            raw_angle = float(
                np.arctan2(matrix_inv[1, 0], matrix_inv[0, 0]) * (180.0 / np.pi)
            )
        else:
            raw_scale, raw_angle = 1.0, 0.0

        has_rotation = abs(raw_angle) > self.rotate_threshold
        has_scale = abs(1.0 - raw_scale) > self.scale_threshold

        angle = raw_angle if has_rotation else 0.0
        scale = raw_scale if has_scale else 1.0

        if has_rotation:
            apply_angle = angle
            apply_scale = (1.0 / scale) if has_scale else 1.0
            transformed_incoming = transform_image(
                incoming,
                angle=-apply_angle,
                scale=apply_scale,
                interp=self.interp,
                dst=self._scratch,
            )
            gray2_rot = self._to_gray(transformed_incoming)
            transformed_mask = (
                transform_image(
                    Image(mask, ImageFormat.GRAY),
                    angle=-apply_angle,
                    scale=apply_scale,
                    interp=InterpMode.NEAREST,
                    dst=self._mask_scratch,
                )[...]
                if mask is not None
                else None
            )

            kp1_r, _, kp2_r, matches_r, valid_r = self._extract_matches(
                gray1,
                gray2_rot,
                mask=transformed_mask,
                cached_ref=(kp1, desc1),
            )

            if kp1_r is None or kp2_r is None or len(valid_r) < 4:
                return MotionEstimate(confidence=0.0), transformed_incoming

            n_use = min(self.nbest, len(matches_r))
            coords1 = [kp1_r[m.queryIdx].pt for m in matches_r[:n_use]]
            coords2 = [kp2_r[m.trainIdx].pt for m in matches_r[:n_use]]
            diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

            delx, dely = self.translation_metric(diff)
            confidence = self._calculate_confidence(diff, delx, dely, len(valid_r))

            estimate = MotionEstimate(
                dx=delx,
                dy=dely,
                angle=angle,
                scale=scale,
                confidence=confidence,
            )
            return estimate, transformed_incoming

        # Single-pass: pure translation
        n_use = min(self.nbest, len(matches))
        coords1 = [kp1[m.queryIdx].pt for m in matches[:n_use]]
        coords2 = [kp2[m.trainIdx].pt for m in matches[:n_use]]
        diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

        delx, dely = self.translation_metric(diff)
        confidence = self._calculate_confidence(diff, delx, dely, len(valid))

        estimate = MotionEstimate(
            dx=delx,
            dy=dely,
            angle=0.0,
            scale=1.0,
            confidence=confidence,
        )
        return estimate, incoming


class OrbScaleEstimator(_BaseOrbEstimator):
    """Specialized estimator for pan shots with camera zoom / scale changes.

    Disregards rotational jitter completely (angle is always 0.0), using pure
    axis-aligned image resizing instead of affine warping to avoid subpixel rotation blur.
    """

    def __init__(
        self,
        max_features: int = 5000,
        distance_threshold: float = 40.0,
        nbest: int = 40,
        translation_metric: Callable[[np.ndarray], tuple[float, float]] = discrete_mode,
        interp: InterpMode = InterpMode.LANCZOS,
        scale_threshold: float = 0.0010,
        fast_threshold: int = 10,
    ) -> None:
        super().__init__(
            max_features=max_features,
            distance_threshold=distance_threshold,
            nbest=nbest,
            translation_metric=translation_metric,
            fast_threshold=fast_threshold,
        )
        self.interp = interp
        self.scale_threshold = scale_threshold

    def estimate(
        self,
        ref: Image,
        incoming: Image,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, Image]:
        """Estimate scale, resizing incoming frame if needed, then refine translation."""
        gray1 = self._to_gray(ref)
        gray2 = self._to_gray(incoming)

        kp1, desc1, kp2, matches, valid = self._extract_matches(
            gray1, gray2, mask=mask
        )
        if kp1 is None or desc1 is None or kp2 is None or len(valid) < 4:
            return MotionEstimate(confidence=0.0), incoming

        pts1 = np.array([kp1[m.queryIdx].pt for m in valid], dtype=np.float32).reshape(
            -1, 1, 2
        )
        pts2 = np.array([kp2[m.trainIdx].pt for m in valid], dtype=np.float32).reshape(
            -1, 1, 2
        )

        matrix_inv, _ = cv2.estimateAffinePartial2D(pts1, pts2)
        if matrix_inv is not None:
            raw_scale = float(np.sqrt(np.linalg.det(matrix_inv[:2, :2])))
        else:
            raw_scale = 1.0

        has_scale = abs(1.0 - raw_scale) > self.scale_threshold
        scale = raw_scale if has_scale else 1.0

        if has_scale:
            apply_scale = 1.0 / scale
            transformed_arr = resize_image(
                incoming[...], apply_scale, interp=self.interp
            )
            transformed_incoming = Image(transformed_arr, incoming.format)
            gray2_scaled = self._to_gray(transformed_incoming)
            transformed_mask = (
                resize_image(mask, apply_scale, interp=InterpMode.NEAREST)
                if mask is not None
                else None
            )

            kp1_s, _, kp2_s, matches_s, valid_s = self._extract_matches(
                gray1,
                gray2_scaled,
                mask=transformed_mask,
                cached_ref=(kp1, desc1),
            )

            if kp1_s is None or kp2_s is None or len(valid_s) < 4:
                return MotionEstimate(confidence=0.0), transformed_incoming

            n_use = min(self.nbest, len(matches_s))
            coords1 = [kp1_s[m.queryIdx].pt for m in matches_s[:n_use]]
            coords2 = [kp2_s[m.trainIdx].pt for m in matches_s[:n_use]]
            diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

            delx, dely = self.translation_metric(diff)
            confidence = self._calculate_confidence(diff, delx, dely, len(valid_s))

            estimate = MotionEstimate(
                dx=delx,
                dy=dely,
                angle=0.0,
                scale=scale,
                confidence=confidence,
            )
            return estimate, transformed_incoming

        # Single-pass: pure translation
        n_use = min(self.nbest, len(matches))
        coords1 = [kp1[m.queryIdx].pt for m in matches[:n_use]]
        coords2 = [kp2[m.trainIdx].pt for m in matches[:n_use]]
        diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

        delx, dely = self.translation_metric(diff)
        confidence = self._calculate_confidence(diff, delx, dely, len(valid))

        estimate = MotionEstimate(
            dx=delx,
            dy=dely,
            angle=0.0,
            scale=1.0,
            confidence=confidence,
        )
        return estimate, incoming
