"""Command-line interface for anifuse panoramic reconstruction."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from anifuse.cli.batch import BatchTyperGroup
from anifuse.cli.models import (
    BlendChoice,
    CompositionConfig,
    DirectionConstraint,
    EffectsConfig,
    InterpChoice,
    MotionConfig,
    MotionMode,
    OutputConfig,
    ReadStrategyType,
    SectionStrategy,
    SourceConfig,
    SourceType,
    StackOrderChoice,
    StitchJob,
)
from anifuse.cli.runner import JobRunner

console = Console()

app = typer.Typer(
    cls=BatchTyperGroup,
    name="anifuse",
    help="anifuse — Motor inteligente para detecção e fusão de cenas panorâmicas de animes.",
    no_args_is_help=True,
)

stitch_app = typer.Typer(
    name="stitch",
    help="Configuração do motor e parâmetros de costura panorâmica.",
    no_args_is_help=True,
)
app.add_typer(stitch_app, name="stitch")


@stitch_app.callback()
def stitch_callback(
    ctx: typer.Context,
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Diretório de saída para salvar as imagens finais.",
        ),
    ] = Path("."),
    name_template: Annotated[
        str | None,
        typer.Option(
            "--name-template",
            help="Template do nome do arquivo (variáveis: {name}, {top}, {ext}).",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Sobrescrever imagem de saída existente em vez de auto-incrementar.",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Ocultar barra de progresso interativa."),
    ] = False,
    motion_mode: Annotated[
        MotionMode,
        typer.Option(
            "--motion-mode",
            help="Modo de movimento de câmera.",
        ),
    ] = MotionMode.AFFINE,
    direction: Annotated[
        DirectionConstraint,
        typer.Option(
            "--direction",
            help="Restrição de eixo no modo translation (auto, horizontal, vertical).",
        ),
    ] = DirectionConstraint.AUTO,
    confidence_thresh: Annotated[
        float,
        typer.Option(
            "--confidence-thresh", help="Limiar mínimo de confiança para alinhamento."
        ),
    ] = 0.25,
    fast_thresh: Annotated[
        int,
        typer.Option(
            "--fast-thresh", help="Limiar do detector FAST para traços de anime."
        ),
    ] = 10,
    rotate_thresh: Annotated[
        float,
        typer.Option(
            "--rotate-thresh", help="Ângulo mínimo em graus para considerar rotação."
        ),
    ] = 0.10,
    scale_thresh: Annotated[
        float,
        typer.Option(
            "--scale-thresh", help="Variação mínima de escala para considerar zoom."
        ),
    ] = 0.0010,
    trans_thresh: Annotated[
        float,
        typer.Option(
            "--trans-thresh", help="Zona morta de translação em pixels."
        ),
    ] = 0.0,
    max_features: Annotated[
        int,
        typer.Option(
            "--max-features", help="Número máximo de pontos-chave ORB detectados."
        ),
    ] = 5000,
    distance_thresh: Annotated[
        float,
        typer.Option(
            "--distance-thresh", help="Distância Hamming máxima aceita entre descritores."
        ),
    ] = 40.0,
    nbest: Annotated[
        int | None,
        typer.Option(
            "--nbest", help="Quantidade de melhores correspondências para estimativa."
        ),
    ] = None,
    stack_order: Annotated[
        StackOrderChoice,
        typer.Option(
            "--stack-order", help="Ordem das camadas: both, last-on-top, first-on-top."
        ),
    ] = StackOrderChoice.BOTH,
    blend_mode: Annotated[
        BlendChoice,
        typer.Option(
            "--blend-mode",
            help="Modo de mesclagem (hard-masking, solid-fill, normal, multiply, clip).",
        ),
    ] = BlendChoice.HARD_MASKING,
    hard_mask_thresh: Annotated[
        int,
        typer.Option(
            "--hard-mask-thresh",
            help="Limiar do canal alfa para o modo hard-masking.",
        ),
    ] = 150,
    interp: Annotated[
        InterpChoice,
        typer.Option(
            "--interp",
            help="Modo de interpolação afim (lanczos, cubic, linear, nearest, area).",
        ),
    ] = InterpChoice.LANCZOS,
    sections: Annotated[
        SectionStrategy,
        typer.Option(
            "--sections",
            help="Estratégia de janela ativa do canvas (cross, global).",
        ),
    ] = SectionStrategy.CROSS,
    border_cut: Annotated[
        int | None,
        typer.Option(
            "--border-cut",
            "-b",
            help="Espessura uniforme de corte de borda na sobreposição.",
        ),
    ] = None,
    border_cut_left: Annotated[
        int,
        typer.Option("--border-cut-left", help="Corte na borda esquerda em pixels."),
    ] = 0,
    border_cut_right: Annotated[
        int,
        typer.Option("--border-cut-right", help="Corte na borda direita em pixels."),
    ] = 0,
    border_cut_top: Annotated[
        int,
        typer.Option("--border-cut-top", help="Corte na borda superior em pixels."),
    ] = 0,
    border_cut_bottom: Annotated[
        int,
        typer.Option("--border-cut-bottom", help="Corte na borda inferior em pixels."),
    ] = 0,
) -> None:
    """Configura os parâmetros globais de visão, composição e saída do motor de costura."""
    if motion_mode != MotionMode.TRANSLATION and direction in (
        DirectionConstraint.HORIZONTAL,
        DirectionConstraint.VERTICAL,
    ):
        raise typer.BadParameter(
            f"A flag --direction '{direction.value}' só é suportada quando --motion-mode for 'translation'. "
            f"Para '{motion_mode.value}', utilize '--direction auto'."
        )

    motion = MotionConfig(
        motion_mode=motion_mode,
        direction=direction,
        confidence_threshold=confidence_thresh,
        fast_threshold=fast_thresh,
        rotate_threshold=rotate_thresh,
        scale_threshold=scale_thresh,
        translation_threshold=trans_thresh,
        max_features=max_features,
        distance_threshold=distance_thresh,
        nbest=nbest,
    )
    composition = CompositionConfig(
        stack_order=stack_order.to_stack_order(),
        blend_mode=blend_mode.to_blend_mode(),
        hard_mask_threshold=hard_mask_thresh,
        interp=interp.to_interp_mode(),
        sections=sections,
    )
    effects = EffectsConfig(
        border_cut=border_cut,
        border_cut_left=border_cut_left,
        border_cut_right=border_cut_right,
        border_cut_top=border_cut_top,
        border_cut_bottom=border_cut_bottom,
    )
    output = OutputConfig(
        output_dir=output_dir,
        name_template=name_template,
        force=force,
        quiet=quiet,
    )
    ctx.obj = (motion, composition, effects, output)


@stitch_app.command("dir")
def stitch_dir_cmd(
    ctx: typer.Context,
    dirs: Annotated[
        list[Path],
        typer.Argument(
            help="Um ou mais diretórios contendo os frames da cena.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
    start: Annotated[
        int,
        typer.Option("--start", "-s", help="Índice inicial do frame."),
    ] = 0,
    frames: Annotated[
        int | None,
        typer.Option(
            "--frames", "-n", help="Quantidade máxima de frames para processar."
        ),
    ] = None,
    step: Annotated[
        int,
        typer.Option("--step", help="Passo de amostragem de frames."),
    ] = 1,
    reverse: Annotated[
        bool,
        typer.Option("--reverse", help="Inverter a ordem temporal dos frames."),
    ] = False,
    read_strategy: Annotated[
        ReadStrategyType,
        typer.Option("--read-strategy", help="Estratégia de leitura: stream ou batched."),
    ] = ReadStrategyType.BATCHED,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Tamanho do lote de leitura em memória."),
    ] = 15,
) -> None:
    """Funde cenas panorâmicas a partir de um ou mais diretórios de imagens."""
    motion, composition, effects, output = ctx.obj
    source = SourceConfig(
        source_type=SourceType.DIR,
        paths=tuple(dirs),
        start=start,
        frames=frames,
        step=step,
        reverse=reverse,
        read_strategy=read_strategy,
        batch_size=batch_size,
    )
    job = StitchJob(
        motion=motion,
        composition=composition,
        effects=effects,
        output=output,
        source=source,
    )
    runner = JobRunner(console=console)
    runner.run_job(job)


@stitch_app.command("image")
def stitch_image_cmd(
    ctx: typer.Context,
    images: Annotated[
        list[Path],
        typer.Argument(
            help="Dois ou mais arquivos de imagem que compõem a cena.",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    start: Annotated[
        int,
        typer.Option("--start", "-s", help="Índice inicial do frame."),
    ] = 0,
    frames: Annotated[
        int | None,
        typer.Option(
            "--frames", "-n", help="Quantidade máxima de frames para processar."
        ),
    ] = None,
    step: Annotated[
        int,
        typer.Option("--step", help="Passo de amostragem de frames."),
    ] = 1,
    reverse: Annotated[
        bool,
        typer.Option("--reverse", help="Inverter a ordem temporal dos frames."),
    ] = False,
    read_strategy: Annotated[
        ReadStrategyType,
        typer.Option("--read-strategy", help="Estratégia de leitura: stream ou batched."),
    ] = ReadStrategyType.BATCHED,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Tamanho do lote de leitura em memória."),
    ] = 15,
) -> None:
    """Funde cenas panorâmicas a partir de uma lista explícita de arquivos de imagem."""
    motion, composition, effects, output = ctx.obj
    source = SourceConfig(
        source_type=SourceType.IMAGE,
        paths=tuple(images),
        start=start,
        frames=frames,
        step=step,
        reverse=reverse,
        read_strategy=read_strategy,
        batch_size=batch_size,
    )
    job = StitchJob(
        motion=motion,
        composition=composition,
        effects=effects,
        output=output,
        source=source,
    )
    runner = JobRunner(console=console)
    runner.run_job(job)


@stitch_app.command("video")
def stitch_video_cmd(
    ctx: typer.Context,
    videos: Annotated[
        list[Path],
        typer.Argument(
            help="Um ou mais arquivos de vídeo contendo a cena.",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    start: Annotated[
        str | None,
        typer.Option(
            "--start",
            "-s",
            help="Ponto inicial: aceita frame (int), segundos (float) ou timestamp (str ex: '01:30').",
        ),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            "-e",
            help="Ponto final limite: aceita frame (int), segundos (float) ou timestamp (str ex: '02:45').",
        ),
    ] = None,
    duration: Annotated[
        str | None,
        typer.Option(
            "--duration",
            "-d",
            help="Duração da cena: aceita quantidade de frames (int), segundos (float) ou tempo (str). Mutuamente exclusivo com --end.",
        ),
    ] = None,
    step: Annotated[
        int,
        typer.Option("--step", help="Passo de amostragem de frames."),
    ] = 1,
    indices: Annotated[
        str | None,
        typer.Option(
            "--indices",
            help="Lista explícita de índices de frames separados por vírgula (ex: '10,15,20').",
        ),
    ] = None,
    reverse: Annotated[
        bool,
        typer.Option("--reverse", help="Inverter o sentido de leitura do vídeo."),
    ] = False,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Capacidade máxima da fila em memória para pré-carregamento."),
    ] = 15,
) -> None:
    """Funde cenas panorâmicas a partir de um ou mais arquivos de vídeo."""
    if end is not None and duration is not None:
        raise typer.BadParameter("As opções '--end' e '--duration' são mutuamente exclusivas.")

    def _parse_val(val: str | None) -> int | float | str | None:
        if val is None:
            return None
        stripped = val.strip()
        if stripped.isdigit():
            return int(stripped)
        try:
            return float(stripped)
        except ValueError:
            return stripped

    parsed_start = _parse_val(start)
    parsed_end = _parse_val(end)
    parsed_duration = _parse_val(duration)

    parsed_indices: tuple[int, ...] | None = None
    if indices:
        try:
            parsed_indices = tuple(int(x.strip()) for x in indices.split(",") if x.strip())
        except ValueError as err:
            raise typer.BadParameter(f"Formato inválido para --indices: '{indices}'") from err

    motion, composition, effects, output = ctx.obj
    source = SourceConfig(
        source_type=SourceType.VIDEO,
        paths=tuple(videos),
        start=parsed_start,
        end=parsed_end,
        duration=parsed_duration,
        indices=parsed_indices,
        step=step,
        reverse=reverse,
        batch_size=batch_size,
    )
    job = StitchJob(
        motion=motion,
        composition=composition,
        effects=effects,
        output=output,
        source=source,
    )
    runner = JobRunner(console=console)
    runner.run_job(job)
