import abc
from collections import UserString
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar

import boto3
from mypy_boto3_ssm import SSMClient


@dataclass
class _SSMConfiguration(abc.ABC):
    """Used to fetch configuration from SSM"""

    parameter_prefix: ClassVar[str]
    parameter_name: ClassVar[str]

    session: boto3.Session

    @cached_property
    def client(self) -> SSMClient:
        return self.session.client("ssm")


class SSMStringConfiguration(_SSMConfiguration, UserString, abc.ABC):
    """Used to fetch string configuration from SSM"""

    @property
    def data(self) -> str:
        return self.client.get_parameter(
            Name=f"{self.parameter_prefix}/{self.parameter_name}"
        )["Parameter"]["Value"]

    @data.setter
    def data(self, value: str) -> None:
        raise NotImplementedError("Not Allowed")
