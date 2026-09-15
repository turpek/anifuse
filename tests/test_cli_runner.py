"""Tests for CLI JobRunner execution orchestration."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from anicrop.enums import ImageFormat
from anicrop.image import Image
from rich.console import Console

from anifuse.cli.models import (
    CompositionConfig,
    MotionConfig,
    MotionMode,
    OutputConfig,
    SourceConfig,
    SourceType,
    StitchJob,
)
from anifuse.cli.runner import JobRunner
from anifuse.interfaces.stitcher import StackOrder


@pytest.fixture
def synthetic_scene(tmp_path: Path) -> Path:
    """Create a temporary directory with synthetic textured frames."""
    scene_dir = tmp_path / "scene_alpha"
    scene_dir.mkdir()
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
        Image(arr, ImageFormat.RGBA).save(scene_dir / f"frame_{f_idx:02d}.png")
    return scene_dir


def test_runner_executes_dir_job_with_both_stack_order(
    synthetic_scene: Path, tmp_path: Path
):
    """Verify JobRunner processes a directory job and outputs both top1 and top2 composites."""
    out_dir = tmp_path / "out_both"
    job = StitchJob(
        motion=MotionConfig(motion_mode=MotionMode.TRANSLATION),
        composition=CompositionConfig(stack_order=StackOrder.BOTH),
        output=OutputConfig(output_dir=out_dir, quiet=True),
        source=SourceConfig(source_type=SourceType.DIR, paths=(synthetic_scene,)),
    )
    runner = JobRunner(console=Console(quiet=True))

    saved = runner.run_job(job)

    assert len(saved) == 2
    assert (out_dir / "scene_alpha_top1.png").exists()
    assert (out_dir / "scene_alpha_top2.png").exists()


def test_runner_executes_dir_job_with_single_stack_order(
    synthetic_scene: Path, tmp_path: Path
):
    """Verify JobRunner processes a directory job and outputs a single composite."""
    out_dir = tmp_path / "out_single"
    job = StitchJob(
        motion=MotionConfig(motion_mode=MotionMode.TRANSLATION),
        composition=CompositionConfig(stack_order=StackOrder.LAST_ON_TOP),
        output=OutputConfig(output_dir=out_dir, quiet=True),
        source=SourceConfig(source_type=SourceType.DIR, paths=(synthetic_scene,)),
    )
    runner = JobRunner(console=Console(quiet=True))

    saved = runner.run_job(job)

    assert len(saved) == 1
    assert (out_dir / "scene_alpha_top2.png").exists()


def test_runner_warns_and_skips_empty_directory(tmp_path: Path):
    """Verify JobRunner skips empty directories without failing."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    job = StitchJob(
        output=OutputConfig(output_dir=tmp_path / "out", quiet=True),
        source=SourceConfig(source_type=SourceType.DIR, paths=(empty_dir,)),
    )
    runner = JobRunner(console=Console(quiet=True))

    saved = runner.run_job(job)

    assert saved == []


def test_runner_warns_and_skips_insufficient_frames(tmp_path: Path):
    """Verify JobRunner skips directory with fewer than 2 frames."""
    one_frame_dir = tmp_path / "one_frame"
    one_frame_dir.mkdir()
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    Image(arr, ImageFormat.RGBA).save(one_frame_dir / "f1.png")

    job = StitchJob(
        output=OutputConfig(output_dir=tmp_path / "out", quiet=True),
        source=SourceConfig(source_type=SourceType.DIR, paths=(one_frame_dir,)),
    )
    runner = JobRunner(console=Console(quiet=True))

    saved = runner.run_job(job)

    assert saved == []


def test_runner_executes_explicit_image_paths_job(
    synthetic_scene: Path, tmp_path: Path
):
    """Verify JobRunner processes explicit image files passed via SourceType.IMAGE."""
    img1 = synthetic_scene / "frame_01.png"
    img2 = synthetic_scene / "frame_02.png"
    out_dir = tmp_path / "out_images"

    job = StitchJob(
        motion=MotionConfig(motion_mode=MotionMode.TRANSLATION),
        composition=CompositionConfig(stack_order=StackOrder.LAST_ON_TOP),
        output=OutputConfig(output_dir=out_dir, quiet=True),
        source=SourceConfig(source_type=SourceType.IMAGE, paths=(img1, img2)),
    )
    runner = JobRunner(console=Console(quiet=True))

    saved = runner.run_job(job)

    assert len(saved) == 1
    assert saved[0].exists()


def test_runner_executes_batch_of_multiple_jobs(synthetic_scene: Path, tmp_path: Path):
    """Verify JobRunner run_jobs executes multiple jobs sequentially."""
    out1 = tmp_path / "batch_out1"
    out2 = tmp_path / "batch_out2"

    job1 = StitchJob(
        motion=MotionConfig(motion_mode=MotionMode.TRANSLATION),
        composition=CompositionConfig(stack_order=StackOrder.LAST_ON_TOP),
        output=OutputConfig(output_dir=out1, quiet=True),
        source=SourceConfig(source_type=SourceType.DIR, paths=(synthetic_scene,)),
    )
    job2 = StitchJob(
        motion=MotionConfig(motion_mode=MotionMode.TRANSLATION),
        composition=CompositionConfig(stack_order=StackOrder.FIRST_ON_TOP),
        output=OutputConfig(output_dir=out2, quiet=True),
        source=SourceConfig(source_type=SourceType.DIR, paths=(synthetic_scene,)),
    )
    runner = JobRunner(console=Console(quiet=True))

    saved = runner.run_jobs([job1, job2])

    assert len(saved) == 2
    assert (out1 / "scene_alpha_top2.png").exists()
    assert (out2 / "scene_alpha_top1.png").exists()
