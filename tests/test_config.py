"""Tests for global configuration instance."""

import anicrop

from anifuse.config import config


def test_config_instance_default_thresholds():
    """Verify default values for rotation, scale, and translation thresholds."""
    assert config.rotate_threshold == 0.10
    assert config.scale_threshold == 0.0010
    assert config.translation_threshold == 0.0
    assert config.fast_threshold == 10
    assert config.batch_size == 15
    assert config.hard_mask_threshold == 150
    assert anicrop.config.hard_mask_threshold == 150


def test_config_mutation_is_reflected_globally():
    """Verify that mutating the configuration instance modifies its attributes."""
    original_threshold = config.rotate_threshold
    config.rotate_threshold = 0.45

    assert config.rotate_threshold == 0.45

    config.rotate_threshold = original_threshold


def test_config_hard_mask_threshold_syncs_with_anicrop():
    """Verify that mutating hard_mask_threshold updates anicrop.config immediately."""
    original_threshold = config.hard_mask_threshold
    config.hard_mask_threshold = 180

    assert config.hard_mask_threshold == 180
    assert anicrop.config.hard_mask_threshold == 180

    config.hard_mask_threshold = original_threshold
