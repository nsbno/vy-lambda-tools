import abc
from dataclasses import dataclass
from typing import ClassVar, Self, Optional


class FlagNotFound(Exception):
    """Raised when a flag is not found"""

    key: str
    """The key of the flag that was not found"""

    def __init__(self, key: str):
        self.key = key

        super().__init__(f"Flag {key} not found")


@dataclass
class FlagValue:
    """The current value for a flag"""

    enabled: bool
    """Whether the flag is enabled or not"""

    context: Optional[list[str]]
    """The objects the flag is enabled for"""


class FlagProvider(abc.ABC):
    """A provider for feature flags"""

    @abc.abstractmethod
    def get_flag(self, key: str) -> FlagValue:
        """Get the value of a flag

        :raises FlagNotFound: If the flag is not found
        """
        ...


class FeatureFlag(abc.ABC):
    """A feature flag that can be used to control the behavior of the application"""

    key: ClassVar[str]
    """The key for the flag"""

    provider: FlagProvider
    """The provider that will be used to fetch the value of the flag"""

    default: ClassVar[bool] = False
    """The default value of the flag"""

    def __init__(self, provider: FlagProvider) -> None:
        self.provider = provider

    def __bool__(self):
        return self.evaluate()

    @abc.abstractmethod
    def evaluate(self, *args, **kwargs) -> bool:
        """Evaluate the flag given a condition

        Implementations must always support zero arguments.
        """
        ...

    def _value(self) -> FlagValue:
        try:
            return self.provider.get_flag(self.key)
        except FlagNotFound:
            return FlagValue(enabled=self.default, context=None)


class ToggleFlag(FeatureFlag):
    """A simple toggle to turn a feature on or off

    It ignores any context in which it is evaluated
    """

    def evaluate(self, *args, **kwargs) -> bool:
        return self._value().enabled


class ContextAwareFlag(FeatureFlag):
    """A flag that is aware of the context in which it is evaluated

    Useful when you want to enable a feature for a specific context, like an account.
    """

    def evaluate(
        self: Self, *args, for_context: Optional[str] = None, **kwargs
    ) -> bool:
        value = self._value()

        if value.context is None:
            return value.enabled

        if for_context is None:
            return False

        return for_context in value.context
