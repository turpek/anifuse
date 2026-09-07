"""Tests for frame reading strategies, path resolvers, and ImageSequenceReader."""

from pathlib import Path

import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image

from anifuse.interfaces.reader import Frame
from anifuse.reader import (
    BatchedReadStrategy,
    DirectoryPathResolver,
    ImageSequenceReader,
    ListPathResolver,
    StreamReadStrategy,
)


@pytest.fixture
def synthetic_image_dir(tmp_path: Path) -> Path:
    """Create a temporary directory containing three synthetic PNG test images."""
    for name in ["frame_02.png", "frame_01.png", "frame_03.png"]:
        img = Image.new((16, 16), ImageFormat.RGBA, color=(255, 0, 0, 255))
        img.save(tmp_path / name)
    (tmp_path / "notes.txt").write_text("not an image")
    return tmp_path


def test_frame_dataclass_holds_attributes():
    """Verify that Frame dataclass stores index, image, and timestamp correctly."""
    img = Image.new((10, 10), ImageFormat.RGBA)
    frame = Frame(idx=42, image=img, timestamp=1.5)

    assert frame.idx == 42
    assert frame.image is img
    assert frame.timestamp == 1.5


def test_directory_path_resolver_discovers_and_sorts_images(
    synthetic_image_dir: Path,
):
    """Verify that DirectoryPathResolver ignores non-images and returns paths sorted."""
    resolver = DirectoryPathResolver(synthetic_image_dir)
    paths = resolver.resolve()

    assert len(paths) == 3
    assert [p.name for p in paths] == [
        "frame_01.png",
        "frame_02.png",
        "frame_03.png",
    ]


def test_directory_path_resolver_raises_on_invalid_directory(tmp_path: Path):
    """Verify that DirectoryPathResolver raises NotADirectoryError when given a file."""
    fake_file = tmp_path / "not_a_dir.txt"
    fake_file.write_text("dummy")

    with pytest.raises(NotADirectoryError):
        DirectoryPathResolver(fake_file)


def test_list_path_resolver_normalizes_and_sorts_paths():
    """Verify that ListPathResolver converts inputs to Path and sorts them."""
    input_paths = [Path("c.png"), "a.png", Path("b.png")]
    resolver = ListPathResolver(input_paths)
    paths = resolver.resolve()

    assert [p.name for p in paths] == ["a.png", "b.png", "c.png"]


def test_stream_read_strategy_yields_all_frames(synthetic_image_dir: Path):
    """Verify that StreamReadStrategy yields frames sequentially with matching indices."""
    paths = sorted(synthetic_image_dir.glob("*.png"))
    strategy = StreamReadStrategy()

    frames = list(strategy.read(paths, list(range(len(paths))), ImageFormat.RGBA))

    assert len(frames) == 3
    assert [f.idx for f in frames] == [0, 1, 2]
    assert all(isinstance(f.image, Image) for f in frames)


def test_batched_read_strategy_yields_all_frames_across_batches(
    synthetic_image_dir: Path,
):
    """Verify that BatchedReadStrategy yields all frames when batch_size is smaller than total."""
    paths = sorted(synthetic_image_dir.glob("*.png"))
    strategy = BatchedReadStrategy(batch_size=2)

    frames = list(strategy.read(paths, list(range(len(paths))), ImageFormat.RGBA))

    assert len(frames) == 3
    assert [f.idx for f in frames] == [0, 1, 2]


def test_image_sequence_reader_yields_forward_order(synthetic_image_dir: Path):
    """Verify that ImageSequenceReader yields frames in forward order when reverse is False."""
    paths = sorted(synthetic_image_dir.glob("*.png"))
    reader = ImageSequenceReader(paths, reverse=False)

    frames = list(reader)

    assert len(reader) == 3
    assert len(frames) == 3
    assert [f.idx for f in frames] == [0, 1, 2]


def test_image_sequence_reader_yields_reverse_order(synthetic_image_dir: Path):
    """Verify that ImageSequenceReader reverses sequence order when reverse is True."""
    paths = sorted(synthetic_image_dir.glob("*.png"))
    reader = ImageSequenceReader(paths, reverse=True)

    frames = list(reader)

    assert len(reader) == 3
    assert len(frames) == 3
    assert reader._paths[0].name == "frame_03.png"
    assert reader._paths[-1].name == "frame_01.png"


def test_image_sequence_reader_from_dir_factory(synthetic_image_dir: Path):
    """Verify that ImageSequenceReader.from_dir resolves files and constructs reader."""
    reader = ImageSequenceReader.from_dir(synthetic_image_dir)

    assert len(reader) == 3
    assert isinstance(reader, ImageSequenceReader)


def test_image_sequence_reader_from_paths_factory(synthetic_image_dir: Path):
    """Verify that ImageSequenceReader.from_paths normalizes paths and constructs reader."""
    paths = [
        str(synthetic_image_dir / "frame_02.png"),
        synthetic_image_dir / "frame_01.png",
    ]
    reader = ImageSequenceReader.from_paths(paths)

    assert len(reader) == 2
    assert reader._paths[0].name == "frame_01.png"
    assert reader._paths[1].name == "frame_02.png"
