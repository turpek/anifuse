"""Tests for frame reading strategies, path resolvers, and ImageSequenceReader."""

from pathlib import Path

import cv2
import numpy as np
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
    VideoReader,
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
    assert BatchedReadStrategy().batch_size == 15


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
    paths: list[Path | str] = [
        str(synthetic_image_dir / "frame_02.png"),
        synthetic_image_dir / "frame_01.png",
    ]
    reader = ImageSequenceReader.from_paths(paths)

    assert len(reader) == 2
    assert reader._paths[0].name == "frame_01.png"
    assert reader._paths[1].name == "frame_02.png"


@pytest.fixture
def numbered_image_dir(tmp_path: Path) -> Path:
    """Create a temporary directory containing six synthetic numbered PNG images."""
    for i in range(1, 7):
        img = Image.new((10, 10), ImageFormat.RGBA)
        img.save(tmp_path / f"frame_{i:02d}.png")
    return tmp_path


@pytest.mark.parametrize(
    ("start", "frames", "step", "reverse", "expected_names"),
    [
        (
            0,
            None,
            1,
            False,
            [
                "frame_01.png",
                "frame_02.png",
                "frame_03.png",
                "frame_04.png",
                "frame_05.png",
                "frame_06.png",
            ],
        ),
        (2, 3, 1, False, ["frame_03.png", "frame_04.png", "frame_05.png"]),
        (0, None, 2, False, ["frame_01.png", "frame_03.png", "frame_05.png"]),
        (1, 4, 2, False, ["frame_02.png", "frame_04.png"]),
        (1, 3, 1, True, ["frame_04.png", "frame_03.png", "frame_02.png"]),
    ],
    ids=[
        "full-sequence",
        "start-and-frames",
        "step-sampling",
        "start-frames-step",
        "sliced-and-reversed",
    ],
)
def test_image_sequence_reader_sampling(
    numbered_image_dir: Path,
    start: int,
    frames: int | None,
    step: int,
    reverse: bool,
    expected_names: list[str],
):
    """Verify that ImageSequenceReader correctly applies start, frames, step, and reverse sampling."""
    reader = ImageSequenceReader.from_dir(
        numbered_image_dir,
        start=start,
        frames=frames,
        step=step,
        reverse=reverse,
    )
    actual_names = [p.name for p in reader._paths]

    assert actual_names == expected_names


@pytest.fixture
def synthetic_video_path(tmp_path: Path) -> Path:
    """Generate a temporary synthetic 10-frame MP4 video for reader tests."""
    video_path = tmp_path / "synthetic_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 10.0, (32, 32))
    for i in range(10):
        frame = np.full((32, 32, 3), fill_value=i * 20, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return video_path


def test_video_reader_forward_reads_all_frames(synthetic_video_path: Path):
    """Verify that VideoReader iterates over all frames in forward order and converts to Image."""
    with VideoReader(synthetic_video_path) as reader:
        frames = list(reader)

    assert len(frames) == 10
    assert [f.idx for f in frames] == list(range(10))
    assert all(isinstance(f.image, Image) for f in frames)
    assert all(f.image.format == ImageFormat.RGBA for f in frames)


def test_video_reader_metadata_properties(synthetic_video_path: Path):
    """Verify that VideoReader exposes fps, total_frames, and len accurately."""
    with VideoReader(synthetic_video_path, start=2, end=7) as reader:
        total = reader.total_frames
        fps = reader.fps
        count = len(reader)

    assert total == 10
    assert fps == 10.0
    assert count == 5


def test_video_reader_with_start_and_end(synthetic_video_path: Path):
    """Verify that VideoReader bounds frame reading within [start, end)."""
    with VideoReader(synthetic_video_path, start=2, end=6) as reader:
        frames = list(reader)

    assert len(frames) == 4
    assert [f.idx for f in frames] == [2, 3, 4, 5]


def test_video_reader_with_step(synthetic_video_path: Path):
    """Verify that VideoReader steps over frames according to the step interval."""
    with VideoReader(synthetic_video_path, start=0, end=6, step=2) as reader:
        frames = list(reader)

    assert len(frames) == 3
    assert [f.idx for f in frames] == [0, 2, 4]


def test_video_reader_with_explicit_indices(synthetic_video_path: Path):
    """Verify that VideoReader decodes specifically requested arbitrary frame indices."""
    with VideoReader(synthetic_video_path, indices=[1, 4, 7]) as reader:
        frames = list(reader)

    assert len(frames) == 3
    assert [f.idx for f in frames] == [1, 4, 7]


def test_video_reader_reverse(synthetic_video_path: Path):
    """Verify that VideoReader yields frames in reverse order when reverse is True."""
    with VideoReader(synthetic_video_path, start=2, end=5, reverse=True) as reader:
        frames = list(reader)

    assert len(frames) == 3
    assert [f.idx for f in frames] == [4, 3, 2]


def test_video_reader_timestamp_calculation(synthetic_video_path: Path):
    """Verify that VideoReader calculates accurate timestamps based on frame index and fps."""
    with VideoReader(synthetic_video_path, start=0, end=3) as reader:
        frames = list(reader)

    assert [round(f.timestamp, 2) for f in frames] == [0.0, 0.1, 0.2]
