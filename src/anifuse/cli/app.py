"""Command-line interface for anifuse panoramic reconstruction."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from anicrop.enums import BlendMode, InterpMode
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

from anifuse.cli.naming import resolve_output_path
from anifuse.config import StackOrder
from anifuse.detection.orb import (
    OrbRotationEstimator,
    OrbScaleEstimator,
    OrbTransformEstimator,
    OrbTranslationEstimator,
)
from anifuse.effects.border import BorderCutEffect
from anifuse.handlers import (
    HorizontalTranslationHandler,
    TranslationHandler,
    VerticalTranslationHandler,
)
from anifuse.interfaces.effect import AnifuseEffect
from anifuse.interfaces.estimator import Estimator
from anifuse.interfaces.handler import TransformHandler
from anifuse.interfaces.view_policy import SectionGenerator
from anifuse.reader import DirectoryPathResolver, ImageSequenceReader
from anifuse.stitcher import SceneStitcher
from anifuse.view_policy import CrossSections, GlobalSections

console = Console()

app = typer.Typer(
    name="anifuse",
    help="anifuse — Motor inteligente para detecção e fusão de cenas panorâmicas de animes.",
    no_args_is_help=True,
)


def _resolve_blend_mode(mode: str) -> BlendMode:
    normalized = mode.strip().lower().replace("-", "_")
    try:
        return BlendMode(normalized)
    except ValueError:
        valid = ", ".join(m.value.replace("_", "-") for m in BlendMode)
        raise typer.BadParameter(
            f"Modo de mesclagem desconhecido: '{mode}'. Opções válidas: {valid}."
        )


def _resolve_interp(interp: str) -> InterpMode:
    normalized = interp.strip().lower()
    mapping = {
        "lanczos": InterpMode.LANCZOS,
        "cubic": InterpMode.CUBIC,
        "bicubic": InterpMode.CUBIC,
        "linear": InterpMode.LINEAR,
        "bilinear": InterpMode.LINEAR,
        "nearest": InterpMode.NEAREST,
        "area": InterpMode.AREA,
    }
    if normalized in mapping:
        return mapping[normalized]
    valid = "lanczos, cubic, linear, nearest, area"
    raise typer.BadParameter(
        f"Interpolação desconhecida: '{interp}'. Opções válidas: {valid}."
    )


def _resolve_stack_order(order: str) -> tuple[StackOrder, int]:
    normalized = order.strip().lower()
    if normalized in ("last-on-top", "last", "2"):
        return StackOrder.LAST_ON_TOP, 2
    if normalized in ("first-on-top", "first", "1"):
        return StackOrder.FIRST_ON_TOP, 1
    if normalized in ("both", "dual"):
        return StackOrder.BOTH, 0
    raise typer.BadParameter(
        f"Ordem de empilhamento desconhecida: '{order}'. Opções: last-on-top, first-on-top, both."
    )


def _resolve_sections(sections: str) -> type[SectionGenerator]:
    normalized = sections.strip().lower()
    if normalized in ("cross", "cross-sections", "local"):
        return CrossSections
    if normalized in ("global", "full"):
        return GlobalSections
    raise typer.BadParameter(
        f"Gerador de seções desconhecido: '{sections}'. Opções: cross, global."
    )


def _resolve_estimator_and_handlers(
    motion_mode: str,
    direction: str,
    interp: InterpMode,
    rotate_thresh: float,
    scale_thresh: float,
    fast_thresh: int,
    trans_thresh: float,
) -> tuple[Estimator, list[TransformHandler]]:
    norm_motion = motion_mode.strip().lower()
    norm_dir = direction.strip().lower()

    if norm_motion != "translation" and norm_dir in ("horizontal", "vertical"):
        raise typer.BadParameter(
            f"A flag --direction '{direction}' só é suportada quando --motion-mode for 'translation'. "
            f"Para '{motion_mode}', utilize '--direction auto'."
        )

    handlers: list[TransformHandler]
    if norm_dir in ("horizontal", "h"):
        handlers = [HorizontalTranslationHandler(threshold=trans_thresh)]
    elif norm_dir in ("vertical", "v"):
        handlers = [VerticalTranslationHandler(threshold=trans_thresh)]
    else:
        handlers = [TranslationHandler(threshold=trans_thresh)]

    estimator: Estimator
    if norm_motion in ("translation", "trans"):
        estimator = OrbTranslationEstimator(fast_threshold=fast_thresh)
    elif norm_motion == "scale":
        estimator = OrbScaleEstimator(
            interp=interp,
            scale_threshold=scale_thresh,
            fast_threshold=fast_thresh,
        )
    elif norm_motion in ("rotation", "rot"):
        estimator = OrbRotationEstimator(
            interp=interp,
            rotate_threshold=rotate_thresh,
            fast_threshold=fast_thresh,
        )
    elif norm_motion in ("affine", "transform"):
        estimator = OrbTransformEstimator(
            interp=interp,
            rotate_threshold=rotate_thresh,
            scale_threshold=scale_thresh,
            fast_threshold=fast_thresh,
        )
    else:
        raise typer.BadParameter(
            f"Modo de movimento desconhecido: '{motion_mode}'. Opções: translation, scale, rotation, affine."
        )

    return estimator, handlers


def _process_dir_stitch(
    target_dir: Path,
    start: int,
    frames: int | None,
    step: int,
    reverse: bool,
    output_dir: Path,
    name_template: str | None,
    force: bool,
    stack_order: str,
    blend_mode: str,
    interp: str,
    motion_mode: str,
    direction: str,
    sections: str,
    confidence_thresh: float,
    fast_thresh: int,
    rotate_thresh: float,
    scale_thresh: float,
    trans_thresh: float,
    border_cut: int | None,
    border_cut_left: int,
    border_cut_right: int,
    border_cut_top: int,
    border_cut_bottom: int,
    quiet: bool,
) -> None:
    all_paths = DirectoryPathResolver(target_dir).resolve()
    if not all_paths:
        console.print(
            f"[yellow]Aviso: nenhuma imagem suportada encontrada em '{target_dir}'.[/yellow]"
        )
        return

    reader = ImageSequenceReader.from_dir(
        target_dir,
        start=start,
        frames=frames,
        step=step,
        reverse=reverse,
    )

    if len(reader) < 2:
        console.print(
            f"[yellow]Menos de 2 frames selecionados ({len(reader)}) em '{target_dir}'. Mínimo necessário: 2.[/yellow]"
        )
        return

    resolved_order, top_id = _resolve_stack_order(stack_order)
    resolved_blend = _resolve_blend_mode(blend_mode)
    resolved_interp = _resolve_interp(interp)
    sections_cls = _resolve_sections(sections)
    estimator, handlers = _resolve_estimator_and_handlers(
        motion_mode=motion_mode,
        direction=direction,
        interp=resolved_interp,
        rotate_thresh=rotate_thresh,
        scale_thresh=scale_thresh,
        fast_thresh=fast_thresh,
        trans_thresh=trans_thresh,
    )

    effects: list[AnifuseEffect] = []
    has_custom = any(
        (border_cut_left, border_cut_right, border_cut_top, border_cut_bottom)
    )
    if border_cut is not None or has_custom:
        effects.append(
            BorderCutEffect(
                all=border_cut,
                left=border_cut_left,
                right=border_cut_right,
                top=border_cut_top,
                bottom=border_cut_bottom,
            )
        )

    console.print(
        f"[bold blue]Costurando:[/bold blue] {target_dir.name} "
        f"([cyan]{len(reader)} frames[/cyan], modo: [magenta]{motion_mode}[/magenta])"
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        disable=quiet,
    ) as progress:
        task = progress.add_task("Alinhando e fundindo frames...", total=len(reader))

        def on_prog(current: int, total: int, alignment: object = None) -> None:
            progress.update(task, completed=current, total=total)

        stitcher = SceneStitcher.from_default(
            estimator=estimator,
            handlers=handlers,
            confidence_threshold=confidence_thresh,
            on_progress=on_prog,
        )

        result = stitcher.stitch(
            reader,
            stack_order=resolved_order,
            effects=effects,
            blend_mode=resolved_blend,
            interp=resolved_interp,
            sections_cls=sections_cls,
        )

    if isinstance(result, tuple):
        top1_img, top2_img = result
        out1 = resolve_output_path(
            output_dir, target_dir.name, 1, name_template, force=force
        )
        out2 = resolve_output_path(
            output_dir, target_dir.name, 2, name_template, force=force
        )
        top1_img.save(out1)
        top2_img.save(out2)
        console.print(f"  [green]✓ Salvo (top1):[/green] {out1}")
        console.print(f"  [green]✓ Salvo (top2):[/green] {out2}")
    elif isinstance(result, Image):
        dest = resolve_output_path(
            output_dir, target_dir.name, top_id, name_template, force=force
        )
        result.save(dest)
        console.print(f"  [green]✓ Salvo:[/green] {dest}")


@app.command("dir")
def dir_cmd(
    dir_path: Annotated[
        Path,
        typer.Argument(
            help="Diretório contendo os frames da cena.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
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
    stack_order: Annotated[
        str,
        typer.Option(
            "--stack-order", help="Ordem das camadas: last-on-top, first-on-top, both."
        ),
    ] = "last-on-top",
    blend_mode: Annotated[
        str,
        typer.Option(
            "--blend-mode",
            help="Modo de mesclagem (hard-masking, solid-fill, normal, normal-linear, multiply, clip).",
        ),
    ] = "hard-masking",
    interp: Annotated[
        str,
        typer.Option(
            "--interp",
            help="Modo de interpolação afim (lanczos, bicubic, bilinear, nearest).",
        ),
    ] = "lanczos",
    motion_mode: Annotated[
        str,
        typer.Option(
            "--motion-mode",
            help="Modo de movimento de câmera (translation, scale, rotation, affine).",
        ),
    ] = "translation",
    direction: Annotated[
        str,
        typer.Option(
            "--direction",
            help="Restrição de eixo no modo translation (auto, horizontal, vertical).",
        ),
    ] = "auto",
    sections: Annotated[
        str,
        typer.Option(
            "--sections",
            help="Estratégia de janela ativa do canvas (cross, global).",
        ),
    ] = "cross",
    confidence_thresh: Annotated[
        float,
        typer.Option(
            "--confidence-thresh", help="Limiar mínimo de confiança para alinhamento."
        ),
    ] = 0.80,
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
    border_cut: Annotated[
        int | None,
        typer.Option(
            "--border-cut",
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
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Ocultar barra de progresso."),
    ] = False,
) -> None:
    """Funde cenas panorâmicas a partir de um único diretório de imagens."""
    _process_dir_stitch(
        target_dir=dir_path,
        start=start,
        frames=frames,
        step=step,
        reverse=reverse,
        output_dir=output_dir,
        name_template=name_template,
        force=force,
        stack_order=stack_order,
        blend_mode=blend_mode,
        interp=interp,
        motion_mode=motion_mode,
        direction=direction,
        sections=sections,
        confidence_thresh=confidence_thresh,
        fast_thresh=fast_thresh,
        rotate_thresh=rotate_thresh,
        scale_thresh=scale_thresh,
        trans_thresh=trans_thresh,
        border_cut=border_cut,
        border_cut_left=border_cut_left,
        border_cut_right=border_cut_right,
        border_cut_top=border_cut_top,
        border_cut_bottom=border_cut_bottom,
        quiet=quiet,
    )


@app.command("dirs")
def dirs_cmd(
    dirs: Annotated[
        list[Path],
        typer.Argument(
            help="Múltiplos diretórios contendo os frames das cenas.",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
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
    stack_order: Annotated[
        str,
        typer.Option(
            "--stack-order", help="Ordem das camadas: last-on-top, first-on-top, both."
        ),
    ] = "last-on-top",
    blend_mode: Annotated[
        str,
        typer.Option(
            "--blend-mode",
            help="Modo de mesclagem (hard-masking, solid-fill, normal, normal-linear, multiply, clip).",
        ),
    ] = "hard-masking",
    interp: Annotated[
        str,
        typer.Option(
            "--interp",
            help="Modo de interpolação afim (lanczos, bicubic, bilinear, nearest).",
        ),
    ] = "lanczos",
    motion_mode: Annotated[
        str,
        typer.Option(
            "--motion-mode",
            help="Modo de movimento de câmera (translation, scale, rotation, affine).",
        ),
    ] = "translation",
    direction: Annotated[
        str,
        typer.Option(
            "--direction",
            help="Restrição de eixo no modo translation (auto, horizontal, vertical).",
        ),
    ] = "auto",
    sections: Annotated[
        str,
        typer.Option(
            "--sections",
            help="Estratégia de janela ativa do canvas (cross, global).",
        ),
    ] = "cross",
    confidence_thresh: Annotated[
        float,
        typer.Option(
            "--confidence-thresh", help="Limiar mínimo de confiança para alinhamento."
        ),
    ] = 0.80,
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
    border_cut: Annotated[
        int | None,
        typer.Option(
            "--border-cut",
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
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Ocultar barra de progresso."),
    ] = False,
) -> None:
    """Funde cenas panorâmicas a partir de múltiplos diretórios com os mesmos parâmetros."""
    for d in dirs:
        _process_dir_stitch(
            target_dir=d,
            start=start,
            frames=frames,
            step=step,
            reverse=reverse,
            output_dir=output_dir,
            name_template=name_template,
            force=force,
            stack_order=stack_order,
            blend_mode=blend_mode,
            interp=interp,
            motion_mode=motion_mode,
            direction=direction,
            sections=sections,
            confidence_thresh=confidence_thresh,
            fast_thresh=fast_thresh,
            rotate_thresh=rotate_thresh,
            scale_thresh=scale_thresh,
            trans_thresh=trans_thresh,
            border_cut=border_cut,
            border_cut_left=border_cut_left,
            border_cut_right=border_cut_right,
            border_cut_top=border_cut_top,
            border_cut_bottom=border_cut_bottom,
            quiet=quiet,
        )
