"""Job execution runner orchestrating readers, progress reporting, and output saving."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from anicrop.image import Image
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from anifuse.cli.factories import EffectFactory, ReaderFactory, StitcherFactory
from anifuse.cli.models import SourceType, StitchJob
from anifuse.cli.naming import resolve_output_path
from anifuse.interfaces.reader import FrameReader
from anifuse.interfaces.stitcher import StackOrder
from anifuse.reader import DirectoryPathResolver


class JobRunner:
    """Executes StitchJob specifications, managing progress presentation and output storage."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize JobRunner with optional Rich Console instance."""
        self.console = console or Console()

    def run_jobs(self, jobs: Sequence[StitchJob]) -> list[Path]:
        """Execute a sequence of StitchJob specifications and return all generated output paths."""
        saved_paths: list[Path] = []
        for job in jobs:
            saved_paths.extend(self.run_job(job))
        return saved_paths

    def run_job(self, job: StitchJob) -> list[Path]:
        """Execute a single StitchJob across all its configured source targets."""
        if job.source.source_type == SourceType.DIR:
            return self._run_dir_job(job)

        if job.source.source_type == SourceType.IMAGE:
            return self._run_image_job(job)

        if job.source.source_type == SourceType.VIDEO:
            raise NotImplementedError("Execução de fontes de vídeo será implementada no módulo de vídeo.")

        raise ValueError(f"Tipo de fonte desconhecido: '{job.source.source_type}'")

    def _run_dir_job(self, job: StitchJob) -> list[Path]:
        saved_paths: list[Path] = []
        for dir_path in job.source.paths:
            all_images = DirectoryPathResolver(dir_path).resolve()
            if not all_images:
                self.console.print(
                    f"[yellow]Aviso: nenhuma imagem suportada encontrada em '{dir_path}'.[/yellow]"
                )
                continue

            reader = ReaderFactory.create_for_path(job.source, dir_path)
            if len(reader) < 2:
                self.console.print(
                    f"[yellow]Menos de 2 frames selecionados ({len(reader)}) em '{dir_path}'. Mínimo necessário: 2.[/yellow]"
                )
                continue

            paths = self._execute_stitch(job, reader, target_name=dir_path.name)
            saved_paths.extend(paths)

        return saved_paths

    def _run_image_job(self, job: StitchJob) -> list[Path]:
        if not job.source.paths:
            self.console.print("[yellow]Aviso: nenhum arquivo de imagem fornecido.[/yellow]")
            return []

        reader = ReaderFactory.create(job.source)
        if len(reader) < 2:
            self.console.print(
                f"[yellow]Menos de 2 frames selecionados ({len(reader)}). Mínimo necessário: 2.[/yellow]"
            )
            return []

        target_name = job.source.paths[0].parent.name or "composite"
        return self._execute_stitch(job, reader, target_name=target_name)

    def _execute_stitch(
        self,
        job: StitchJob,
        reader: FrameReader,
        target_name: str,
    ) -> list[Path]:
        effects = EffectFactory.create(job.effects, job.motion)
        sections_cls = StitcherFactory.resolve_sections(job.composition.sections)

        self.console.print(
            f"[bold blue]Costurando:[/bold blue] {target_name} "
            f"([cyan]{len(reader)} frames[/cyan], modo: [magenta]{job.motion.motion_mode.value}[/magenta])"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            disable=job.output.quiet,
            console=self.console,
        ) as progress:
            task = progress.add_task("Alinhando e fundindo frames...", total=len(reader))

            def on_progress(current: int, total: int, alignment: object = None) -> None:
                progress.update(task, completed=current, total=total)

            stitcher = StitcherFactory.create(job, on_progress=on_progress)
            result = stitcher.stitch(
                reader,
                stack_order=job.composition.stack_order,
                effects=effects,
                blend_mode=job.composition.blend_mode,
                interp=job.composition.interp,
                sections_cls=sections_cls,
            )

        return self._save_result(job, result, target_name)

    def _save_result(
        self,
        job: StitchJob,
        result: Image | tuple[Image, Image],
        target_name: str,
    ) -> list[Path]:
        saved_paths: list[Path] = []

        if isinstance(result, tuple):
            top1_img, top2_img = result
            out1 = resolve_output_path(
                output_dir=job.output.output_dir,
                input_name=target_name,
                top_id=1,
                template=job.output.name_template,
                force=job.output.force,
            )
            out2 = resolve_output_path(
                output_dir=job.output.output_dir,
                input_name=target_name,
                top_id=2,
                template=job.output.name_template,
                force=job.output.force,
            )
            top1_img.save(out1)
            top2_img.save(out2)
            saved_paths.extend([out1, out2])

            self.console.print(f"  [green]✓ Salvo (top1):[/green] {out1}")
            self.console.print(f"  [green]✓ Salvo (top2):[/green] {out2}")

        elif isinstance(result, Image):
            top_id = 1 if job.composition.stack_order == StackOrder.FIRST_ON_TOP else 2
            dest = resolve_output_path(
                output_dir=job.output.output_dir,
                input_name=target_name,
                top_id=top_id,
                template=job.output.name_template,
                force=job.output.force,
            )
            result.save(dest)
            saved_paths.append(dest)

            self.console.print(f"  [green]✓ Salvo:[/green] {dest}")

        return saved_paths
