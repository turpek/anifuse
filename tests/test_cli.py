"""Tests for anifuse command-line interface and reader dispatching."""

from pathlib import Path

import cv2
import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image
from typer.testing import CliRunner

from anifuse.cli.app import app

runner = CliRunner()


@pytest.fixture
def synthetic_scene_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create two temporary directories with synthetic textured frame sequences."""
    dir1 = tmp_path / "scene_01"
    dir1.mkdir()
    for f_idx in range(1, 4):
        arr = np.zeros((300, 300, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        for k in range(8):
            x = 30 + (k % 4) * 60 + (f_idx - 1) * 10
            y = 30 + (k // 4) * 80
            cv2.rectangle(arr, (x, y), (x + 30, y + 30), (255, 255, 255, 255), -1)
            cv2.putText(
                arr, f"A{k}", (x + 5, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0, 255), 1
            )
        Image(arr, ImageFormat.RGBA).save(dir1 / f"frame_{f_idx:02d}.png")

    dir2 = tmp_path / "scene_02"
    dir2.mkdir()
    for f_idx in range(1, 4):
        arr = np.zeros((300, 300, 4), dtype=np.uint8)
        arr[:, :, 3] = 255
        for k in range(8):
            x = 30 + (k % 4) * 60 + (f_idx - 1) * 10
            y = 30 + (k // 4) * 80
            cv2.rectangle(arr, (x, y), (x + 30, y + 30), (255, 255, 255, 255), -1)
            cv2.putText(
                arr, f"B{k}", (x + 5, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0, 255), 1
            )
        Image(arr, ImageFormat.RGBA).save(dir2 / f"frame_{f_idx:02d}.png")

    return dir1, dir2


def test_cli_dir_single_directory_stitches_and_saves(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that dir command stitches frames and generates output image."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        ["dir", "-s", "0", "-n", "2", "-o", str(out_dir), "--quiet", str(dir1)],
    )

    assert result.exit_code == 0
    assert "Costurando: scene_01" in result.output
    assert (out_dir / "scene_01_top2.png").exists()


def test_cli_dirs_multiple_directories_stitches_all(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that dirs command stitches multiple directories to target folder."""
    dir1, dir2 = synthetic_scene_dirs
    out_dir = tmp_path / "output_dirs"
    result = runner.invoke(
        app,
        ["dirs", "-s", "0", "-n", "2", "-o", str(out_dir), "--quiet", str(dir1), str(dir2)],
    )

    assert result.exit_code == 0
    assert "Costurando: scene_01" in result.output
    assert "Costurando: scene_02" in result.output
    assert (out_dir / "scene_01_top2.png").exists()
    assert (out_dir / "scene_02_top2.png").exists()


def test_cli_dir_validates_direction_and_motion_mode(
    synthetic_scene_dirs: tuple[Path, Path],
):
    """Verify that specifying horizontal/vertical direction on non-translation mode errors."""
    dir1, _ = synthetic_scene_dirs
    result = runner.invoke(
        app,
        ["dir", "--motion-mode", "scale", "--direction", "horizontal", str(dir1)],
    )

    assert result.exit_code != 0
    assert "--direction 'horizontal' só é suportada" in result.output


def test_cli_dir_warns_on_empty_directory(tmp_path: Path):
    """Verify that dir command prints a warning when directory has no supported images."""
    empty_dir = tmp_path / "empty_scene"
    empty_dir.mkdir()
    result = runner.invoke(app, ["dir", str(empty_dir)])

    assert result.exit_code == 0
    assert "nenhuma imagem suportada encontrada" in result.output
