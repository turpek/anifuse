"""Tests for global configuration instance."""

from anifuse.config import config


def test_config_instance_default_thresholds():
    """Verify default values for rotation, scale, and translation thresholds."""
    assert config.rotate_threshold == 0.20
    assert config.scale_threshold == 0.006
    assert config.translation_threshold == 0.0


def test_config_mutation_is_reflected_globally():
    """Verify that mutating the configuration instance modifies its attributes."""
    original_threshold = config.rotate_threshold
    config.rotate_threshold = 0.45

    assert config.rotate_threshold == 0.45

    config.rotate_threshold = original_threshold
