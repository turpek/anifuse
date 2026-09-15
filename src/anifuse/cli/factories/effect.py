"""Declarative factory for building border cut effects."""

from __future__ import annotations

from anifuse.cli.models import EffectsConfig, MotionConfig, MotionMode
from anifuse.effects import LinearBorderCutEffect, RotatedBorderCutEffect
from anifuse.interfaces.effect import AnifuseEffect

EFFECT_MAP: dict[MotionMode, type[AnifuseEffect]] = {
    MotionMode.TRANSLATION: LinearBorderCutEffect,
    MotionMode.SCALE: RotatedBorderCutEffect,
    MotionMode.ROTATION: RotatedBorderCutEffect,
    MotionMode.AFFINE: RotatedBorderCutEffect,
}


class EffectFactory:
    """Factory responsible for constructing composition effects based on configuration."""

    @staticmethod
    def create(effects: EffectsConfig, motion: MotionConfig) -> list[AnifuseEffect]:
        """Build border cut effects matching the configured motion mode."""
        if not effects.has_cut:
            return []

        effect_cls = EFFECT_MAP.get(motion.motion_mode, RotatedBorderCutEffect)
        return [
            effect_cls(
                all=effects.border_cut,
                left=effects.border_cut_left,
                right=effects.border_cut_right,
                top=effects.border_cut_top,
                bottom=effects.border_cut_bottom,
            )
        ]
