import json
from typing import Generator

import boto3
import pytest
from moto import mock_ssm
from mypy_boto3_ssm import SSMClient

from vy_lambda_tools import feature_flag
from vy_lambda_tools.feature_flag.base import FlagNotFound


class TestSimpleFeatureToggle:
    class SimpleFeatureToggle(feature_flag.FeatureFlag):
        key = "simple_enabled"
        default = False

    def test_normal_use(self):
        provider = feature_flag.InMemoryProvider(
            flags={
                self.SimpleFeatureToggle.key: {"enabled": True},
            }
        )

        flag = self.SimpleFeatureToggle(provider=provider)

        assert flag

    def test_not_found_uses_default(self):
        provider = feature_flag.InMemoryProvider(flags={})

        flag = self.SimpleFeatureToggle(provider=provider)

        assert not flag


class TestFeatureToggleWithContext:
    class FeatureToggleWithContext(feature_flag.FeatureFlag):
        key = "context_enabled"

    class ContextToggleWithContextRemoved(feature_flag.FeatureFlag):
        key = "context_removed"

    @pytest.fixture
    def enabled_account(self) -> str:
        return "account1"

    @pytest.fixture
    def disabled_account(self) -> str:
        return "account2"

    @pytest.fixture
    def provider(self, enabled_account: str):
        return feature_flag.InMemoryProvider(
            flags={
                self.FeatureToggleWithContext.key: {
                    "enabled": True,
                    "context": [enabled_account],
                },
                self.ContextToggleWithContextRemoved.key: {
                    "enabled": True,
                },
            }
        )

    def test_boolean_evaluation_is_false_when_context_exists(self, provider):
        flag = self.FeatureToggleWithContext(provider=provider)

        assert not flag

    def test_normal_use(self, provider, enabled_account):
        flag = self.FeatureToggleWithContext(provider=provider)

        assert flag._evaluate(for_context=enabled_account) is True

    def test_wrong_context(self, provider, disabled_account):
        flag = self.FeatureToggleWithContext(provider=provider)

        # But should be false when the context is wrong
        assert flag._evaluate(for_context=disabled_account) is False

    def test_boolean_evaluation_is_true_when_context_is_missing(self, provider):
        flag = self.ContextToggleWithContextRemoved(provider=provider)

        assert flag

    def test_no_context_in_value_returns_enabled_state(self, provider):
        flag = self.ContextToggleWithContextRemoved(provider=provider)

        assert flag._evaluate() is True


class TestAWSParameterStoreProvider:
    @pytest.fixture
    def ssm_client(self) -> Generator[SSMClient, None, None]:
        with mock_ssm():
            yield boto3.client("ssm")

    def test_different_applications_have_different_flags(self, ssm_client: SSMClient):
        provider_a = feature_flag.AWSParameterStoreProvider(
            application_name="app_a",
            ssm_client=ssm_client,
        )
        provider_b = feature_flag.AWSParameterStoreProvider(
            application_name="app_b",
            ssm_client=ssm_client,
        )

        ssm_client.put_parameter(
            Name=(
                f"/{provider_a.prefix}/{provider_a.application_name}/flags/"
                f"test_flag/enabled"
            ),
            Type="String",
            Value="true",
        )

        ssm_client.put_parameter(
            Name=(
                f"/{provider_b.prefix}/{provider_b.application_name}/flags/"
                f"test_flag/enabled"
            ),
            Type="String",
            Value="false",
        )

        flag_a = provider_a.get_flag("test_flag")
        flag_b = provider_b.get_flag("test_flag")

        assert flag_a.enabled is True
        assert flag_b.enabled is False

    @pytest.fixture
    def aws_parameter_store_provider(self, ssm_client):
        return feature_flag.AWSParameterStoreProvider(
            application_name="test_app",
            ssm_client=ssm_client,
        )

    @pytest.mark.parametrize(
        "enabled",
        [
            pytest.param(
                True,
                id="enabled-flag",
            ),
            pytest.param(
                False,
                id="disabled-flag",
            ),
        ],
    )
    @pytest.mark.parametrize(
        "context",
        [
            pytest.param(
                None,
                id="without-context",
            ),
            pytest.param(
                [],
                id="empty-context",
            ),
            pytest.param(
                ["account1"],
                id="with-context",
            ),
        ],
    )
    def test_get_flag(self, ssm_client, aws_parameter_store_provider, enabled, context):
        ssm_client.put_parameter(
            Name=(
                f"/{aws_parameter_store_provider.prefix}/"
                f"{aws_parameter_store_provider.application_name}/"
                f"flags/test_flag/enabled"
            ),
            Type="String",
            Value=json.dumps(enabled),
        )
        ssm_client.put_parameter(
            Name=(
                f"/{aws_parameter_store_provider.prefix}/"
                f"{aws_parameter_store_provider.application_name}/"
                f"flags/test_flag/context"
            ),
            Type="String",
            Value=json.dumps(context),
        )

        flag_value = aws_parameter_store_provider.get_flag("test_flag")

        assert flag_value.enabled is enabled
        assert flag_value.context == context

    def test_get_flag_not_found(self, aws_parameter_store_provider):
        with pytest.raises(FlagNotFound):
            aws_parameter_store_provider.get_flag("test_flag")

    def test_missing_enabled_parameter_gives_not_found_error(
        self, ssm_client, aws_parameter_store_provider
    ):
        ssm_client.put_parameter(
            Name=(
                f"/{aws_parameter_store_provider.prefix}/"
                f"{aws_parameter_store_provider.application_name}/"
                f"flags/test_flag/context"
            ),
            Type="String",
            Value=json.dumps(["account1"]),
        )

        with pytest.raises(FlagNotFound):
            aws_parameter_store_provider.get_flag("test_flag")

    def test_none_value_on_enabled_parameter_gives_not_found_error(
        self, ssm_client, aws_parameter_store_provider
    ):
        ssm_client.put_parameter(
            Name=(
                f"/{aws_parameter_store_provider.prefix}/"
                f"{aws_parameter_store_provider.application_name}/"
                f"flags/test_flag/enabled"
            ),
            Type="String",
            Value=json.dumps(None),
        )

        with pytest.raises(FlagNotFound):
            aws_parameter_store_provider.get_flag("test_flag")
