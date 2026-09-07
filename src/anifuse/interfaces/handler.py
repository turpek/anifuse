"""Interface for geometric transformation handlers applying motion estimates to layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anicrop.layer import Layer

    from anifuse.interfaces.view_policy import AlignmentResult


class TransformHandler(ABC):
    """Abstract handler applying geometric transformation to a Layer based on alignment metadata."""

    @abstractmethod
    def apply(self, target: Layer, alignment: AlignmentResult) -> None:
        """Apply geometric transformation to target Layer."""
        pass
