"""Concrete image sequence reading implementations, path resolvers, and strategies."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Self

import anicrop
from anicrop.enums import ImageFormat
from anicrop.image import Image

from anifuse.interfaces.reader import (
    Frame,
    FrameReader,
    PathResolver,
    ReadStrategy,
)


class DirectoryPathResolver(PathResolver):
    """Discovers and sorts supported image files inside a directory."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

    def __init__(self, dir_path: Path | str) -> None:
        """Initialize resolver with target directory path."""
        self.dir_path = Path(dir_path)
        if not self.dir_path.is_dir():
            raise NotADirectoryError(f"Expected a directory, got: {self.dir_path}")

    def resolve(self) -> Sequence[Path]:
        """Return a sorted sequence of matching image file paths."""
        return sorted(
            [
                f
                for f in self.dir_path.iterdir()
                if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ]
        )


class ListPathResolver(PathResolver):
    """Normalizes and sorts an explicit sequence of image file paths."""

    def __init__(self, img_paths: Sequence[Path | str]) -> None:
        """Initialize resolver with arbitrary path representations."""
        self.img_paths = [Path(p) for p in img_paths]

    def resolve(self) -> Sequence[Path]:
        """Return a sorted sequence of normalized Path objects."""
        return sorted(self.img_paths)


class StreamReadStrategy(ReadStrategy):
    """Direct on-demand streaming strategy (ideal for Pyvips and low memory footprint)."""

    def read(
        self,
        paths: Sequence[Path],
        indices: Sequence[int],
        image_format: ImageFormat,
    ) -> Iterator[Frame]:
        """Yield frames sequentially without prefetching."""
        for idx, path in zip(indices, paths):
            img = Image.open(path, image_format=image_format)
            yield Frame(idx=idx, image=img)


class BatchedReadStrategy(ReadStrategy):
    """Batched buffer strategy (ideal for OpenCV and batch filesystem read-ahead)."""

    def __init__(self, batch_size: int = 15) -> None:
        """Initialize strategy with batch chunk size."""
        self.batch_size = max(1, batch_size)

    def read(
        self,
        paths: Sequence[Path],
        indices: Sequence[int],
        image_format: ImageFormat,
    ) -> Iterator[Frame]:
        """Yield frames loaded in discrete memory batches."""
        total = len(paths)
        for chunk_start in range(0, total, self.batch_size):
            chunk_paths = paths[chunk_start: chunk_start + self.batch_size]
            chunk_indices = indices[chunk_start: chunk_start + self.batch_size]

            batch: deque[Frame] = deque(
                Frame(idx=i, image=Image.open(p, image_format=image_format))
                for i, p in zip(chunk_indices, chunk_paths)
            )

            while batch:
                yield batch.popleft()


class ImageSequenceReader(FrameReader):
    """Sequence reader consuming normalized image paths on disk."""

    def __init__(
        self,
        paths: Sequence[Path],
        reverse: bool = False,
        strategy: ReadStrategy | None = None,
        image_format: ImageFormat = ImageFormat.RGBA,
    ) -> None:
        """Initialize reader with normalized paths, reading strategy, and direction."""
        self._paths: list[Path] = list(reversed(paths)) if reverse else list(paths)
        self.image_format = image_format
        self.strategy = strategy if strategy is not None else self._default_strategy()

    def _default_strategy(self) -> ReadStrategy:
        if anicrop.config.backend == "vips":
            return StreamReadStrategy()
        return BatchedReadStrategy()

    def __len__(self) -> int:
        """Return total number of frames in the sequence."""
        return len(self._paths)

    def __iter__(self) -> Iterator[Frame]:
        """Yield frames by delegating to the configured reading strategy."""
        indices = list(range(len(self._paths)))
        yield from self.strategy.read(self._paths, indices, self.image_format)

    @classmethod
    def from_dir(
        cls,
        dir_path: Path | str,
        start: int = 0,
        frames: int | None = None,
        step: int = 1,
        reverse: bool = False,
        strategy: ReadStrategy | None = None,
        image_format: ImageFormat = ImageFormat.RGBA,
    ) -> Self:
        """Construct reader by resolving image files discovered in a directory with frame sampling.

        Args:
            dir_path: Directory path containing image sequence.
            start: 0-indexed starting frame index (defaults to 0).
            frames: Optional maximum count of frames to read.
            step: Sampling step interval (defaults to 1).
            reverse: Whether to reverse the final selected sequence.
            strategy: Optional custom reading strategy.
            image_format: Desired color/alpha format.
        """
        paths = DirectoryPathResolver(dir_path).resolve()
        stop = start + frames if frames is not None else None
        selected_paths = paths[start:stop:step]
        return cls(
            selected_paths, reverse=reverse, strategy=strategy, image_format=image_format
        )

    @classmethod
    def from_paths(
        cls,
        img_paths: Sequence[Path | str],
        start: int = 0,
        frames: int | None = None,
        step: int = 1,
        reverse: bool = False,
        strategy: ReadStrategy | None = None,
        image_format: ImageFormat = ImageFormat.RGBA,
    ) -> Self:
        """Construct reader by resolving an explicit list of paths with frame sampling.

        Args:
            img_paths: Explicit sequence of file paths.
            start: 0-indexed starting frame index (defaults to 0).
            frames: Optional maximum count of frames to read.
            step: Sampling step interval (defaults to 1).
            reverse: Whether to reverse the final selected sequence.
            strategy: Optional custom reading strategy.
            image_format: Desired color/alpha format.
        """
        paths = ListPathResolver(img_paths).resolve()
        stop = start + frames if frames is not None else None
        selected_paths = paths[start:stop:step]
        return cls(
            selected_paths, reverse=reverse, strategy=strategy, image_format=image_format
        )
