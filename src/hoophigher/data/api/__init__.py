"""API providers for game data."""

from hoophigher.data.api.base import StatsProvider
from hoophigher.data.api.mock_provider import MockProvider

__all__ = ["MockProvider", "StatsProvider"]
