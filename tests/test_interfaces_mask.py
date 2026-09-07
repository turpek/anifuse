import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image

from anifuse.interfaces import MaskView


class DummyArrayMask(MaskView):
    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[np.ndarray, np.ndarray | None]:
        return image[...], np.zeros(image[...].shape[:2], dtype=np.uint8)


class DummyNoneMask(MaskView):
    def get_mask(
        self, image: Image, frame_idx: int = 0
    ) -> tuple[np.ndarray, np.ndarray | None]:
        return image[...], None


def test_mask_view_cannot_be_instantiated_directly():
    """Verify that MaskView is an abstract class and cannot be directly instantiated."""
    with pytest.raises(TypeError):
        MaskView()  # type: ignore[abstract]


@pytest.mark.parametrize(
    ("mask_cls", "expected_mask_type"),
    [
        (DummyArrayMask, np.ndarray),
        (DummyNoneMask, type(None)),
    ],
    ids=["numpy_array_mask", "none_mask"],
)
def test_mask_view_concrete_subclass_returns_expected_types(
    mask_cls: type[MaskView], expected_mask_type: type
):
    """Verify that concrete MaskView implementations return frame array and expected mask type."""
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    dummy_image = Image(arr, ImageFormat.RGB)
    instance = mask_cls()
    frame_arr, mask = instance.get_mask(dummy_image, frame_idx=0)

    assert isinstance(frame_arr, np.ndarray)
    assert isinstance(mask, expected_mask_type)
