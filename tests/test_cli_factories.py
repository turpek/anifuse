"""Tests for declarative CLI component factories."""

from __future__ import annotations

from pathlib import Path

import pytest

from anifuse.cli.factories import (
    EffectFactory,
    EstimatorFactory,
    HandlerFactory,
    ReaderFactory,
    StitcherFactory,
)
from anifuse.cli.models import (
    CompositionConfig,
    DirectionConstraint,
    EffectsConfig,
    MotionConfig,
    MotionMode,
    ReadStrategyType,
    SectionStrategy,
    SourceConfig,
    SourceType,
    StitchJob,
)
from anifuse.detection.orb import (
    OrbRotationEstimator,
    OrbScaleEstimator,
    OrbTransformEstimator,
    OrbTranslationEstimator,
)
from anifuse.effects import LinearBorderCutEffect, RotatedBorderCutEffect
from anifuse.handlers import (
    HorizontalTranslationHandler,
    RotationHandler,
    ScaleHandler,
    TranslationHandler,
    VerticalTranslationHandler,
)
from anifuse.reader import (
    BatchedReadStrategy,
    ImageSequenceReader,
    StreamReadStrategy,
)
from anifuse.stitcher import SceneStitcher
from anifuse.view_policy import CrossSections, GlobalSections


@pytest.mark.parametrize(
    ("motion_mode", "expected_cls"),
    [
        (MotionMode.TRANSLATION, OrbTranslationEstimator),
        (MotionMode.SCALE, OrbScaleEstimator),
        (MotionMode.ROTATION, OrbRotationEstimator),
        (MotionMode.AFFINE, OrbTransformEstimator),
    ],
    ids=["translation", "scale", "rotation", "affine"],
)
def test_estimator_factory_creates_expected_estimator_instance(
    motion_mode: MotionMode, expected_cls: type
):
    """Verify EstimatorFactory instantiates the correct estimator class per motion mode."""
    motion = MotionConfig(motion_mode=motion_mode)
    composition = CompositionConfig()

    estimator = EstimatorFactory.create(motion, composition)

    assert isinstance(estimator, expected_cls)


@pytest.mark.parametrize(
    ("motion_mode", "direction", "expected_handler_classes"),
    [
        (
            MotionMode.TRANSLATION,
            DirectionConstraint.AUTO,
            [TranslationHandler],
        ),
        (
            MotionMode.TRANSLATION,
            DirectionConstraint.HORIZONTAL,
            [HorizontalTranslationHandler],
        ),
        (
            MotionMode.TRANSLATION,
            DirectionConstraint.VERTICAL,
            [VerticalTranslationHandler],
        ),
        (
            MotionMode.SCALE,
            DirectionConstraint.AUTO,
            [ScaleHandler, TranslationHandler],
        ),
        (
            MotionMode.ROTATION,
            DirectionConstraint.AUTO,
            [RotationHandler, TranslationHandler],
        ),
        (
            MotionMode.AFFINE,
            DirectionConstraint.AUTO,
            [ScaleHandler, RotationHandler, TranslationHandler],
        ),
    ],
    ids=[
        "trans_auto",
        "trans_horizontal",
        "trans_vertical",
        "scale_chain",
        "rotation_chain",
        "affine_chain",
    ],
)
def test_handler_factory_creates_expected_handler_chain(
    motion_mode: MotionMode,
    direction: DirectionConstraint,
    expected_handler_classes: list[type],
):
    """Verify HandlerFactory builds the expected sequence of transform handlers."""
    motion = MotionConfig(motion_mode=motion_mode, direction=direction)

    handlers = HandlerFactory.create(motion)

    assert [type(h) for h in handlers] == expected_handler_classes


def test_handler_factory_raises_error_on_invalid_direction_constraint():
    """Verify HandlerFactory rejects horizontal/vertical direction on non-translation mode."""
    motion = MotionConfig(
        motion_mode=MotionMode.AFFINE, direction=DirectionConstraint.HORIZONTAL
    )

    with pytest.raises(ValueError, match="só é suportada quando o modo de movimento"):
        HandlerFactory.create(motion)


def test_effect_factory_returns_empty_list_when_no_cut_configured():
    """Verify EffectFactory yields no effects when border cutting is disabled."""
    effects_config = EffectsConfig()
    motion_config = MotionConfig()

    effects = EffectFactory.create(effects_config, motion_config)

    assert effects == []


@pytest.mark.parametrize(
    ("motion_mode", "expected_cls"),
    [
        (MotionMode.TRANSLATION, LinearBorderCutEffect),
        (MotionMode.SCALE, RotatedBorderCutEffect),
        (MotionMode.ROTATION, RotatedBorderCutEffect),
        (MotionMode.AFFINE, RotatedBorderCutEffect),
    ],
    ids=["trans_linear", "scale_rotated", "rot_rotated", "affine_rotated"],
)
def test_effect_factory_creates_correct_border_cut_class_per_mode(
    motion_mode: MotionMode, expected_cls: type
):
    """Verify EffectFactory creates the suitable cut effect based on camera motion type."""
    effects_config = EffectsConfig(border_cut=5)
    motion_config = MotionConfig(motion_mode=motion_mode)

    effects = EffectFactory.create(effects_config, motion_config)

    assert len(effects) == 1
    assert isinstance(effects[0], expected_cls)


@pytest.mark.parametrize(
    ("strategy_type", "expected_cls"),
    [
        (ReadStrategyType.STREAM, StreamReadStrategy),
        (ReadStrategyType.BATCHED, BatchedReadStrategy),
    ],
    ids=["stream_strategy", "batched_strategy"],
)
def test_reader_factory_creates_configured_reading_strategy(
    strategy_type: ReadStrategyType, expected_cls: type
):
    """Verify ReaderFactory instantiates the requested reading strategy."""
    source = SourceConfig(read_strategy=strategy_type)

    strategy = ReaderFactory.create_strategy(source)

    assert isinstance(strategy, expected_cls)


def test_reader_factory_creates_image_sequence_reader_from_dir(tmp_path: Path):
    """Verify ReaderFactory instantiates ImageSequenceReader for a target directory."""
    source = SourceConfig(source_type=SourceType.DIR, paths=(tmp_path,))

    reader = ReaderFactory.create(source)

    assert isinstance(reader, ImageSequenceReader)


def test_reader_factory_creates_image_sequence_reader_from_image_paths(tmp_path: Path):
    """Verify ReaderFactory instantiates ImageSequenceReader for explicit image paths."""
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    img1.touch()
    img2.touch()
    source = SourceConfig(source_type=SourceType.IMAGE, paths=(img1, img2))

    reader = ReaderFactory.create(source)

    assert isinstance(reader, ImageSequenceReader)


@pytest.mark.parametrize(
    ("section_strategy", "expected_cls"),
    [
        (SectionStrategy.CROSS, CrossSections),
        (SectionStrategy.GLOBAL, GlobalSections),
    ],
    ids=["cross_sections", "global_sections"],
)
def test_stitcher_factory_resolves_expected_section_strategy(
    section_strategy: SectionStrategy, expected_cls: type
):
    """Verify StitcherFactory maps sectioning strategy enums to their generator types."""
    resolved = StitcherFactory.resolve_sections(section_strategy)

    assert resolved is expected_cls


def test_stitcher_factory_creates_scene_stitcher_instance():
    """Verify StitcherFactory creates a fully configured SceneStitcher orchestrator."""
    job = StitchJob()

    stitcher = StitcherFactory.create(job)

    assert isinstance(stitcher, SceneStitcher)
