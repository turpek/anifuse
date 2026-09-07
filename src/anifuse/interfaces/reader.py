"""Interfaces and data structures for frame reading and sequencing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from anicrop.enums import ImageFormat
    from anicrop.image import Image


@dataclass(frozen=True)
class Frame:
    """Container pairing a decoded image frame with its sequential index and timestamp."""

    idx: int
    image: Image
    timestamp: float = 0.0


class PathResolver(ABC):
    """Abstract strategy for discovering and ordering image paths."""

    @abstractmethod
    def resolve(self) -> Sequence[Path]:
        """Return a sorted sequence of valid Path objects."""
        pass


class ReadStrategy(ABC):
    """Abstract strategy for reading frames from an indexed sequence of paths."""

    @abstractmethod
    def read(
        self,
        paths: Sequence[Path],
        indices: Sequence[int],
        image_format: ImageFormat,
    ) -> Iterator[Frame]:
        """Iterate over frames yielded by this reading strategy."""
        pass


class FrameReader(ABC):
    """Abstract base class for reading frame sequences."""

    @abstractmethod
    def __iter__(self) -> Iterator[Frame]:
        """Iterate over frames in the configured sequence."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Total number of frames available in the reader."""
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Release underlying resources or handles."""
        pass
