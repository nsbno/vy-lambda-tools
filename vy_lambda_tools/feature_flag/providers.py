import json
import logging
from dataclasses import dataclass
from typing import Any

from mypy_boto3_ssm import SSMClient

from vy_lambda_tools.feature_flag.base import FlagProvider, FlagValue, FlagNotFound

logger = logging.getLogger(__name__)


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


@dataclass
class AWSParameterStoreProvider(FlagProvider):
    """A provider for feature flags that uses AWS Parameter Store

    Flags are stored as parameters in the AWS Parameter Store.
    We expect the flags to be stored in the following format:
     - /applications/{application_name}/flags/{flag_name}/enabled
     - /applications/{application_name}/flags/{flag_name}/context

    All values must be stored as JSON types.
    The value of the `enabled` parameter should be a boolean or null for not initalized.
    The value of the `context` parameter should be a list of strings, null or missing.
    """

    application_name: str
    """The name of the application"""

    ssm_client: SSMClient
    """The SSM client to use"""

    prefix: str = "applications"
    """The prefix for the parameter store"""

    flag_prefix: str = "flags"
    """The prefix for the flags"""

    @property
    def _base_path(self) -> str:
        """Full base path for flags"""
        return f"/{self.prefix}/{self.application_name}/{self.flag_prefix}"

    def get_flag(self, key: str) -> FlagValue:
        try:
            response = self.ssm_client.get_parameters_by_path(
                Path=f"{self._base_path}/{key}", Recursive=False, WithDecryption=False
            )
        except Exception as e:
            raise FlagNotFound(key) from e

        if not response["Parameters"]:
            raise FlagNotFound(key)

        try:
            enabled_parameter = next(
                parameter["Value"]
                for parameter in response["Parameters"]
                if parameter["Name"].endswith("enabled")
            )
        except StopIteration:
            raise FlagNotFound(key)

        try:
            enabled = json.loads(enabled_parameter)
        except json.JSONDecodeError:
            logger.exception("Could not load enabled state")
            enabled = None

        if enabled is None:
            raise FlagNotFound(key)
        if enabled not in (True, False):
            raise ValueError(f"Invalid value for flag {key}: {enabled}")

        context_parameter = next(
            (
                parameter["Value"]
                for parameter in response["Parameters"]
                if parameter["Name"].endswith("context")
            ),
            None,
        )
        try:
            context = json.loads(context_parameter) if context_parameter else None
        except json.JSONDecodeError:
            logger.exception("Could not load context")
            context = None

        if context is not None and not isinstance(context, list):
            raise ValueError(f"Invalid value for flag {key}: {context}")

        return FlagValue(enabled=enabled, context=context)
