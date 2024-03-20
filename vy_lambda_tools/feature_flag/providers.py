from dataclasses import dataclass
from typing import Any

from vy_lambda_tools.feature_flag.base import FlagProvider, FlagValue, FlagNotFound


@dataclass
class InMemoryProvider(FlagProvider):
    """A provider for feature flags that uses an in-memory dictionary"""

    flags: dict[str, FlagValue]

    def __init__(self, flags: dict[str, dict[str, Any]]) -> None:
        self.flags = {
            key: FlagValue(enabled=value["enabled"], context=value.get("context", None))
            for key, value in flags.items()
        }

    def get_flag(self, key: str) -> FlagValue:
        try:
            return self.flags[key]
        except KeyError:
            raise FlagNotFound(key)
