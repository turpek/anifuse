"""ORB feature-based estimators for pure translation and full affine transformations."""

from collections.abc import Callable
from statistics import StatisticsError, mode

import cv2
import numpy as np

from anifuse.config import config
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


def rotate_image(mat: np.ndarray, angle: float, scale: float) -> np.ndarray:
    """Rotate and scale an image array, expanding bounding box to avoid clipping.

    Args:
        mat: Input image NumPy array (H, W) or (H, W, C).
        angle: Rotation angle in degrees (counter-clockwise).
        scale: Scale multiplier.

    Returns:
        Warped image array with expanded dimensions.
    """
    height, width = mat.shape[:2]
    center = (width / 2.0, height / 2.0)
    rot_mat = cv2.getRotationMatrix2D(center, angle, scale)

    abs_cos = abs(rot_mat[0, 0])
    abs_sin = abs(rot_mat[0, 1])
    bound_w = int(height * abs_sin + width * abs_cos)
    bound_h = int(height * abs_cos + width * abs_sin)

    rot_mat[0, 2] += bound_w / 2.0 - center[0]
    rot_mat[1, 2] += bound_h / 2.0 - center[1]

    return cv2.warpAffine(mat, rot_mat, (bound_w, bound_h))


class _BaseOrbEstimator(Estimator):
    """Internal base helper managing shared ORB detector and matcher instances."""

    def __init__(
        self,
        max_features: int = 5000,
        distance_threshold: float = 40.0,
        nbest: int = 40,
        translation_metric: Callable[[np.ndarray], tuple[float, float]] = discrete_mode,
    ) -> None:
        self.max_features = max_features
        self.distance_threshold = distance_threshold
        self.nbest = nbest
        self.translation_metric = translation_metric

        self._orb = cv2.ORB_create(nfeatures=max_features, scoreType=cv2.ORB_FAST_SCORE)
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def _to_gray(self, img: np.ndarray) -> np.ndarray:
        if img.ndim == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _extract_matches(
        self,
        gray1: np.ndarray,
        gray2: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> tuple[
        list[cv2.KeyPoint] | None,
        list[cv2.KeyPoint] | None,
        list[cv2.DMatch],
        list[cv2.DMatch],
    ]:
        kp1, desc1 = self._orb.detectAndCompute(gray1, None)
        kp2, desc2 = self._orb.detectAndCompute(gray2, mask)

        if desc1 is None or desc2 is None or len(kp1) < 4 or len(kp2) < 4:
            return None, None, [], []

        matches = sorted(self._matcher.match(desc1, desc2), key=lambda x: x.distance)
        valid = [m for m in matches if m.distance < self.distance_threshold]
        if len(valid) < 4:
            valid = matches[: max(4, len(matches))]

        return kp1, kp2, matches, valid

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

    def estimate(
        self,
        ref: np.ndarray,
        incoming: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, np.ndarray]:
        """Estimate 2D translation in a single pass, returning the unmodified incoming frame."""
        gray1 = self._to_gray(ref)
        gray2 = self._to_gray(incoming)

        kp1, kp2, matches, valid = self._extract_matches(gray1, gray2, mask=mask)
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

    def estimate(
        self,
        ref: np.ndarray,
        incoming: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> tuple[MotionEstimate, np.ndarray]:
        """Estimate rotation and scale, rotating the frame if necessary, then refine translation."""
        gray1 = self._to_gray(ref)
        gray2 = self._to_gray(incoming)

        kp1, kp2, matches, valid = self._extract_matches(gray1, gray2, mask=mask)
        if kp1 is None or kp2 is None or len(valid) < 4:
            return MotionEstimate(confidence=0.0), incoming

        pts1 = np.float32([kp1[m.queryIdx].pt for m in valid]).reshape(-1, 1, 2)
        pts2 = np.float32([kp2[m.trainIdx].pt for m in valid]).reshape(-1, 1, 2)

        matrix_inv, _ = cv2.estimateAffinePartial2D(pts1, pts2)
        if matrix_inv is not None:
            scale = float(np.sqrt(np.linalg.det(matrix_inv[:2, :2])))
            angle = float(
                np.arctan2(matrix_inv[1, 0], matrix_inv[0, 0]) * (180.0 / np.pi)
            )
        else:
            scale, angle = 1.0, 0.0

        has_rotation = abs(angle) > config.rotate_threshold
        has_scale = abs(1.0 - scale) > config.scale_threshold

        if has_rotation or has_scale:
            # Rotate incoming image and run second pass on aligned pixel grid
            rotated_incoming = rotate_image(incoming, angle, 1.0 / scale)
            gray2_rot = self._to_gray(rotated_incoming)
            rotated_mask = (
                rotate_image(mask, angle, 1.0 / scale)
                if mask is not None
                else None
            )

            kp1_r, kp2_r, matches_r, valid_r = self._extract_matches(
                gray1, gray2_rot, mask=rotated_mask
            )

            if kp1_r is None or kp2_r is None or len(valid_r) < 4:
                return MotionEstimate(confidence=0.0), rotated_incoming

            n_use = min(self.nbest, len(matches_r))
            coords1 = [kp1_r[m.queryIdx].pt for m in matches_r[:n_use]]
            coords2 = [kp2_r[m.trainIdx].pt for m in matches_r[:n_use]]
            diff = np.array(coords2, dtype=int) - np.array(coords1, dtype=int)

            delx, dely = self.translation_metric(diff)
            confidence = self._calculate_confidence(diff, delx, dely, len(valid_r))

            estimate = MotionEstimate(
                dx=delx,
                dy=dely,
                angle=0.0,
                scale=1.0,
                confidence=confidence,
            )
            return estimate, rotated_incoming

        # Single step (no significant rotation): compute translation directly
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
