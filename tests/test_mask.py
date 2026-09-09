import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image
from anicrop.spatial import Region

from anifuse.mask import (
    CompositeMaskView,
    DefaultMaskView,
    DynamicMaskView,
    SequenceMaskView,
    StaticMaskView,
)


@pytest.fixture
def dummy_image() -> Image:
    """Return an Image instance wrapping a synthetic 100x100x3 test array."""
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    return Image(arr, ImageFormat.RGB)


def test_default_mask_view_returns_full_image_and_no_mask(dummy_image: Image):
    """Verify that DefaultMaskView returns full Image and None mask."""
    mask_view = DefaultMaskView()

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=0)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (100, 100, 3)
    assert mask is None


def test_static_mask_view_with_region_slices_image(dummy_image: Image):
    """Verify that a Region passed to StaticMaskView slices image directly with None mask."""
    region = Region.from_rect(10, 20, 30, 40)
    mask_view = StaticMaskView(region)

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=0)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (40, 30, 3)
    assert mask is None


def test_static_mask_view_returns_configured_array(dummy_image: Image):
    """Verify that a NumPy array passed to StaticMaskView is returned as mask."""
    mask_arr = np.ones((100, 100), dtype=np.uint8)
    mask_view = StaticMaskView(mask_arr)

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=5)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (100, 100, 3)
    assert mask is mask_arr


def test_static_mask_view_returns_none_when_configured_with_none(
    dummy_image: Image,
):
    """Verify that StaticMaskView returns None mask when initialized with None."""
    mask_view = StaticMaskView(None)

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=0)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (100, 100, 3)
    assert mask is None


@pytest.mark.parametrize(
    ("frame_idx", "expected_shape"),
    [
        (0, (10, 20, 3)),
        (1, (30, 40, 3)),
    ],
    ids=["first_frame_region", "second_frame_region"],
)
def test_sequence_mask_view_returns_mask_by_index(
    dummy_image: Image,
    frame_idx: int,
    expected_shape: tuple[int, int, int],
):
    """Verify that SequenceMaskView returns the correct region crop corresponding to frame index."""
    seq = [Region.from_rect(0, 0, 20, 10), Region.from_rect(10, 10, 40, 30)]
    mask_view = SequenceMaskView(seq)

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=frame_idx)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == expected_shape
    assert mask is None


def test_sequence_mask_view_returns_none_when_out_of_bounds(
    dummy_image: Image,
):
    """Verify that SequenceMaskView returns full image and None mask when index exceeds length."""
    seq = [Region.from_rect(0, 0, 10, 10)]
    mask_view = SequenceMaskView(seq)

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=99)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (100, 100, 3)
    assert mask is None


def test_dynamic_mask_view_evaluates_detector_callback(dummy_image: Image):
    """Verify that DynamicMaskView invokes the detector callback with image and index."""

    def mock_detector(image: Image, idx: int) -> Region | None:
        return Region.from_rect(0, 0, idx * 10, idx * 10)

    mask_view = DynamicMaskView(mock_detector)

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=3)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (30, 30, 3)
    assert mask is None


def test_composite_mask_view_returns_none_when_all_masks_are_none(
    dummy_image: Image,
):
    """Verify that CompositeMaskView returns None mask when all child masks evaluate to None."""
    mask_view = CompositeMaskView([StaticMaskView(None), StaticMaskView(None)])

    frame_img, mask = mask_view.get_mask(dummy_image, frame_idx=0)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (100, 100, 3)
    assert mask is None


def test_composite_mask_view_combines_array_masks(
    dummy_image: Image,
):
    """Verify that CompositeMaskView compiles multiple array masks into a single binary mask."""
    arr1 = np.full((100, 100), 255, dtype=np.uint8)
    arr1[0:10, 0:10] = 0
    arr2 = np.full((100, 100), 255, dtype=np.uint8)
    arr2[20:30, 20:30] = 0

    composite = CompositeMaskView([StaticMaskView(arr1), StaticMaskView(arr2)])
    frame_img, compiled = composite.get_mask(dummy_image, frame_idx=0)

    assert isinstance(frame_img, Image)
    assert frame_img.shape == (100, 100, 3)
    assert isinstance(compiled, np.ndarray)
    assert compiled.shape == (100, 100)
    assert compiled.dtype == np.uint8
    assert np.all(compiled[0:10, 0:10] == 0)
    assert np.all(compiled[20:30, 20:30] == 0)
    assert compiled[50, 50] == 255
