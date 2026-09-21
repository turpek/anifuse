"""Tests for anifuse modern command-line interface, subcommands, and chaining."""

from __future__ import annotations

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


def test_cli_stitch_dir_single_directory(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch dir command stitches frames and generates output images."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
        ],
    )

    assert result.exit_code == 0
    assert "Costurando: scene_01" in result.output
    assert (out_dir / "scene_01_top1.png").exists()
    assert (out_dir / "scene_01_top2.png").exists()


def test_cli_stitch_dir_multiple_directories(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch dir command stitches multiple directories in batch."""
    dir1, dir2 = synthetic_scene_dirs
    out_dir = tmp_path / "output_dirs"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
            str(dir2),
        ],
    )

    assert result.exit_code == 0
    assert "Costurando: scene_01" in result.output
    assert "Costurando: scene_02" in result.output
    assert (out_dir / "scene_01_top1.png").exists()
    assert (out_dir / "scene_02_top1.png").exists()


def test_cli_stitch_image_explicit_files(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch image command stitches an explicit list of image files."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output_images"
    img1 = dir1 / "frame_01.png"
    img2 = dir1 / "frame_02.png"

    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--quiet",
            "image",
            str(img1),
            str(img2),
        ],
    )

    assert result.exit_code == 0
    assert "Costurando: scene_01" in result.output
    assert (out_dir / "scene_01_top1.png").exists()


def test_cli_stitch_multi_command_chaining(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that chained stitch commands execute sequentially in a single process."""
    dir1, dir2 = synthetic_scene_dirs
    out1 = tmp_path / "chain_out1"
    out2 = tmp_path / "chain_out2"

    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out1),
            "--motion-mode",
            "translation",
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
            "stitch",
            "-o",
            str(out2),
            "--motion-mode",
            "rotation",
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir2),
        ],
    )

    assert result.exit_code == 0
    assert "Costurando: scene_01" in result.output
    assert "Costurando: scene_02" in result.output
    assert (out1 / "scene_01_top1.png").exists()
    assert (out2 / "scene_02_top1.png").exists()


def test_cli_stitch_validates_direction_and_motion_mode(
    synthetic_scene_dirs: tuple[Path, Path],
):
    """Verify that specifying horizontal/vertical direction on non-translation mode errors."""
    dir1, _ = synthetic_scene_dirs
    result = runner.invoke(
        app,
        [
            "stitch",
            "--motion-mode",
            "scale",
            "--direction",
            "horizontal",
            "dir",
            str(dir1),
        ],
    )

    assert result.exit_code != 0
    assert "--direction 'horizontal' só é suportada" in result.output


def test_cli_stitch_warns_on_empty_directory(tmp_path: Path):
    """Verify that stitch dir prints a warning when directory has no supported images."""
    empty_dir = tmp_path / "empty_scene"
    empty_dir.mkdir()
    result = runner.invoke(app, ["stitch", "dir", str(empty_dir)])

    assert result.exit_code == 0
    assert "nenhuma imagem suportada encontrada" in result.output


def test_cli_stitch_with_rotation_motion_mode_stitches(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch command stitches frames when --motion-mode rotation is specified."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output_rot"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--motion-mode",
            "rotation",
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "scene_01_top1.png").exists()


def test_cli_stitch_with_scale_motion_mode_stitches(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch command stitches frames when --motion-mode scale is specified."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output_scale"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--motion-mode",
            "scale",
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "scene_01_top1.png").exists()


def test_cli_stitch_with_linear_border_cut_stitches(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch command stitches frames with linear border cut on translation mode."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output_linear_cut"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "-b",
            "5",
            "--motion-mode",
            "translation",
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "scene_01_top1.png").exists()


def test_cli_stitch_with_rotated_border_cut_stitches(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch command stitches frames with rotated border cut on rotation mode."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output_rot_cut"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--motion-mode",
            "rotation",
            "-b",
            "5",
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "scene_01_top1.png").exists()


def test_cli_stitch_with_rotated_custom_border_cut_sides(
    synthetic_scene_dirs: tuple[Path, Path],
    tmp_path: Path,
):
    """Verify that stitch command stitches frames with selective border cut sides on rotation mode."""
    dir1, _ = synthetic_scene_dirs
    out_dir = tmp_path / "output_rot_sides"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--motion-mode",
            "rotation",
            "--border-cut-left",
            "5",
            "--quiet",
            "dir",
            "-s",
            "0",
            "-n",
            "2",
            str(dir1),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "scene_01_top1.png").exists()


def test_cli_stitch_video_end_and_duration_mutually_exclusive(tmp_path: Path):
    """Verify that specifying both --end and --duration for stitch video errors."""
    fake_video = tmp_path / "fake.mp4"
    fake_video.touch()
    result = runner.invoke(
        app,
        [
            "stitch",
            "video",
            "--end",
            "10",
            "--duration",
            "5",
            str(fake_video),
        ],
    )

    assert result.exit_code != 0
    assert "mutuamente exclusivas" in result.output


def test_cli_stitch_video_invalid_indices(tmp_path: Path):
    """Verify that passing non-integer values to --indices errors with bad parameter."""
    fake_video = tmp_path / "fake.mp4"
    fake_video.touch()
    result = runner.invoke(
        app,
        [
            "stitch",
            "video",
            "--indices",
            "abc,def",
            str(fake_video),
        ],
    )

    assert result.exit_code != 0
    assert "Formato inválido para --indices" in result.output


def test_cli_stitch_video_with_synthetic_video(tmp_path: Path):
    """Verify that stitch video processes frames from video and writes composite outputs."""
    video_path = tmp_path / "test_pan.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 10.0, (200, 200))
    for f_idx in range(4):
        arr = np.zeros((200, 200, 3), dtype=np.uint8)
        for k in range(6):
            x = 20 + (k % 3) * 50 + f_idx * 10
            y = 20 + (k // 3) * 60
            cv2.rectangle(arr, (x, y), (x + 20, y + 20), (255, 255, 255), -1)
        writer.write(arr)
    writer.release()

    out_dir = tmp_path / "output_video"
    result = runner.invoke(
        app,
        [
            "stitch",
            "-o",
            str(out_dir),
            "--motion-mode",
            "translation",
            "--quiet",
            "video",
            "--start",
            "0",
            "--duration",
            "3",
            str(video_path),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "test_pan_top1.png").exists()
