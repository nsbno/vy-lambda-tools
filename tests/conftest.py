import os

import pytest


@pytest.fixture(autouse=True)
def aws_testing_envvars():
    """Set environment variables for AWS testing."""
    os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
