"""Declarative factory for instantiating sequence frame readers and I/O strategies."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aniseek.time_utils import time_to_seconds

from anifuse.cli.models import ReadStrategyType, SourceConfig, SourceType
from anifuse.detection.boundary import SceneBoundaryResolver
from anifuse.interfaces.reader import FrameReader, ReadStrategy
from anifuse.reader import (
    BatchedReadStrategy,
    ImageSequenceReader,
    StreamReadStrategy,
    VideoReader,
)

if TYPE_CHECKING:
    pass


class ReaderFactory:
    """Factory responsible for instantiating FrameReader implementations from source configuration."""

    @staticmethod
    def create_strategy(source: SourceConfig) -> ReadStrategy:
        """Instantiate the configured frame reading and caching strategy."""
        if source.read_strategy == ReadStrategyType.STREAM:
            return StreamReadStrategy()
        return BatchedReadStrategy(batch_size=source.batch_size)

    @staticmethod
    def resolve_video_bounds(
        start: int | float | str | None,
        end: int | float | str | None,
        duration: int | float | str | None,
    ) -> tuple[int | float | str | None, int | float | str | None]:
        """Resolve start and end bounds, calculating end from duration when provided."""
        if end is not None and duration is not None:
            raise ValueError("As opções 'end' e 'duration' são mutuamente exclusivas.")

        if duration is None:
            return start, end

        if isinstance(duration, int) and (start is None or isinstance(start, int)):
            calc_start = start if start is not None else 0
            return start, calc_start + duration

        start_sec = time_to_seconds(start) if start is not None else 0.0
        dur_sec = time_to_seconds(duration)
        return start, start_sec + dur_sec

    @classmethod
    def create_for_path(cls, source: SourceConfig, target_path: Path) -> FrameReader:
        """Create a FrameReader for a single target directory or media file."""
        strategy = cls.create_strategy(source)

        if source.source_type == SourceType.DIR:
            start_idx = source.start if isinstance(source.start, int) else 0
            return ImageSequenceReader.from_dir(
                dir_path=target_path,
                start=start_idx,
                frames=source.frames,
                step=source.step,
                reverse=source.reverse,
                strategy=strategy,
            )

        if source.source_type == SourceType.VIDEO:
            start, end = cls.resolve_video_bounds(
                start=source.start,
                end=source.end,
                duration=source.duration if source.duration is not None else source.frames,
            )
            reader = VideoReader(
                video=target_path,
                indices=source.indices,
                start=start,
                end=end,
                step=source.step,
                reverse=source.reverse,
                buffersize=source.batch_size,
            )
            has_timestamp = isinstance(source.start, (str, float)) or isinstance(source.end, (str, float))
            if has_timestamp and source.indices is None:
                SceneBoundaryResolver.resolve_and_adjust(reader)
            return reader

        raise ValueError(f"Tipo de fonte não suportado para caminho individual: '{source.source_type}'")

    @classmethod
    def create(cls, source: SourceConfig) -> FrameReader:
        """Create a FrameReader from the configured source specifications."""
        strategy = cls.create_strategy(source)

        if source.source_type == SourceType.IMAGE:
            if not source.paths:
                raise ValueError("Nenhum caminho de imagem fornecido na configuração da fonte.")
            start_idx = source.start if isinstance(source.start, int) else 0
            return ImageSequenceReader.from_paths(
                img_paths=source.paths,
                start=start_idx,
                frames=source.frames,
                step=source.step,
                reverse=source.reverse,
                strategy=strategy,
            )

        if source.source_type == SourceType.DIR:
            if not source.paths:
                raise ValueError("Nenhum caminho de diretório fornecido na configuração da fonte.")
            return cls.create_for_path(source, source.paths[0])

        if source.source_type == SourceType.VIDEO:
            if not source.paths:
                raise ValueError("Nenhum caminho de vídeo fornecido na configuração da fonte.")
            return cls.create_for_path(source, source.paths[0])

        raise ValueError(f"Tipo de fonte não suportado: '{source.source_type}'")
