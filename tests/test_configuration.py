from typing import Iterator

import boto3
import moto
import pytest

from vy_lambda_tools.configuration import SSMStringConfiguration


@pytest.fixture
def session() -> Iterator[boto3.Session]:
    with moto.mock_ssm():
        yield boto3.Session()


def test_ssm_string_configuration(session: boto3.Session):
    value_to_put = "test-value"

    class MyTestConfiguration(SSMStringConfiguration):
        parameter_prefix = "/test-prefix"
        parameter_name = "test-parameter"

    ssm_client = session.client("ssm")
    ssm_client.put_parameter(
        Name=f"{MyTestConfiguration.parameter_prefix}/{MyTestConfiguration.parameter_name}",
        Value=value_to_put,
        Type="String",
    )

    configuration = MyTestConfiguration(session=session)

    assert configuration.data == value_to_put
