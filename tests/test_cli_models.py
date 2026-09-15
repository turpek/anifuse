"""Tests for CLI domain configuration models and enums."""

from __future__ import annotations

from pathlib import Path

import pytest
from anicrop.enums import BlendMode, InterpMode

from anifuse.cli.models import (
    CompositionConfig,
    DirectionConstraint,
    EffectsConfig,
    MotionConfig,
    MotionMode,
    OutputConfig,
    ReadStrategyType,
    SectionStrategy,
    SourceConfig,
    SourceType,
    StitchJob,
)
from anifuse.interfaces.stitcher import StackOrder


def test_output_config_defaults():
    """Verify default attribute values for OutputConfig."""
    config = OutputConfig()

    assert config.output_dir == Path(".")
    assert config.name_template is None
    assert config.force is False
    assert config.quiet is False


def test_motion_config_defaults():
    """Verify default attribute values for MotionConfig."""
    config = MotionConfig()

    assert config.motion_mode == MotionMode.AFFINE
    assert config.direction == DirectionConstraint.AUTO
    assert config.confidence_threshold == 0.80
    assert config.fast_threshold == 10
    assert config.rotate_threshold == 0.10
    assert config.scale_threshold == 0.0010
    assert config.translation_threshold == 0.0
    assert config.max_features == 5000
    assert config.distance_threshold == 40.0
    assert config.nbest is None
    assert config.mask_roi is None


def test_composition_config_defaults():
    """Verify default attribute values for CompositionConfig."""
    config = CompositionConfig()

    assert config.stack_order == StackOrder.BOTH
    assert config.blend_mode == BlendMode.HARD_MASKING
    assert config.hard_mask_threshold == 150
    assert config.interp == InterpMode.LANCZOS
    assert config.sections == SectionStrategy.CROSS


def test_effects_config_defaults():
    """Verify default attribute values and has_cut for EffectsConfig."""
    config = EffectsConfig()

    assert config.border_cut is None
    assert config.border_cut_left == 0
    assert config.border_cut_right == 0
    assert config.border_cut_top == 0
    assert config.border_cut_bottom == 0
    assert config.has_cut is False


@pytest.mark.parametrize(
    ("kwargs", "expected_has_cut"),
    [
        ({"border_cut": 5}, True),
        ({"border_cut_left": 3}, True),
        ({"border_cut_right": 2}, True),
        ({"border_cut_top": 1}, True),
        ({"border_cut_bottom": 4}, True),
        ({}, False),
    ],
    ids=["uniform_cut", "left_cut", "right_cut", "top_cut", "bottom_cut", "no_cut"],
)
def test_effects_config_has_cut_detection(
    kwargs: dict[str, int], expected_has_cut: bool
):
    """Verify has_cut property accurately identifies active cut configurations."""
    config = EffectsConfig(**kwargs)

    assert config.has_cut is expected_has_cut


def test_source_config_defaults():
    """Verify default attribute values for SourceConfig."""
    config = SourceConfig()

    assert config.source_type == SourceType.DIR
    assert config.paths == ()
    assert config.start == 0
    assert config.frames is None
    assert config.step == 1
    assert config.reverse is False
    assert config.read_strategy == ReadStrategyType.BATCHED
    assert config.batch_size == 15
    assert config.fps is None


def test_stitch_job_default_aggregation():
    """Verify StitchJob aggregates default sub-configurations into a cohesive job."""
    job = StitchJob()

    assert isinstance(job.motion, MotionConfig)
    assert isinstance(job.composition, CompositionConfig)
    assert isinstance(job.effects, EffectsConfig)
    assert isinstance(job.output, OutputConfig)
    assert isinstance(job.source, SourceConfig)
