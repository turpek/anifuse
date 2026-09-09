"""Output file path resolution and auto-increment naming strategy."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_output_path(
    output_dir: Path,
    input_name: str,
    top_id: int,
    template: str | None = None,
    force: bool = False,
    **extra_kwargs: Any,
) -> Path:
    """Resolve destination path using template or default naming with auto-increment.

    Args:
        output_dir: Target directory where image will be saved.
        input_name: Stem or name of the input source.
        top_id: Identifier of the top layer (e.g. 1 for first-on-top, 2 for last-on-top).
        template: Optional format string (placeholders: {name}, {top}, {ext}).
        force: If True, overwrite existing target instead of auto-incrementing.
        **extra_kwargs: Additional template variables.

    Returns:
        Resolved Path guaranteed to be unique unless force is True.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if template is not None:
        filename = template.format(name=input_name, top=top_id, ext="png", **extra_kwargs)
    else:
        filename = f"{input_name}_top{top_id}.png"

    target = output_dir / filename
    if force or not target.exists():
        return target

    stem = target.stem
    ext = target.suffix
    idx = 1
    while True:
        candidate = output_dir / f"{stem}_{idx}{ext}"
        if not candidate.exists():
            return candidate
        idx += 1
