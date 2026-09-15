"""Declarative factory for instantiating sequence frame readers and I/O strategies."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from anifuse.cli.models import ReadStrategyType, SourceConfig, SourceType
from anifuse.interfaces.reader import FrameReader, ReadStrategy
from anifuse.reader import (
    BatchedReadStrategy,
    ImageSequenceReader,
    StreamReadStrategy,
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

    @classmethod
    def create_for_path(cls, source: SourceConfig, target_path: Path) -> FrameReader:
        """Create a FrameReader for a single target directory or media file."""
        strategy = cls.create_strategy(source)

        if source.source_type == SourceType.DIR:
            return ImageSequenceReader.from_dir(
                dir_path=target_path,
                start=source.start,
                frames=source.frames,
                step=source.step,
                reverse=source.reverse,
                strategy=strategy,
            )

        if source.source_type == SourceType.VIDEO:
            raise NotImplementedError(
                "O leitor de vídeo nativo será implementado no pipeline de I/O de vídeo."
            )

        raise ValueError(f"Tipo de fonte não suportado para caminho individual: '{source.source_type}'")

    @classmethod
    def create(cls, source: SourceConfig) -> FrameReader:
        """Create a FrameReader from the configured source specifications."""
        strategy = cls.create_strategy(source)

        if source.source_type == SourceType.IMAGE:
            if not source.paths:
                raise ValueError("Nenhum caminho de imagem fornecido na configuração da fonte.")
            return ImageSequenceReader.from_paths(
                img_paths=source.paths,
                start=source.start,
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
            raise NotImplementedError(
                "O leitor de vídeo nativo será implementado no pipeline de I/O de vídeo."
            )

        raise ValueError(f"Tipo de fonte não suportado: '{source.source_type}'")
