import pytest

from vy_lambda_tools import feature_flag


class TestSimpleFeatureToggle:
    class SimpleFeatureToggle(feature_flag.ToggleFlag):
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
        assert flag.evaluate() is True

    def test_not_found_uses_default(self):
        provider = feature_flag.InMemoryProvider(flags={})

        flag = self.SimpleFeatureToggle(provider=provider)

        assert not flag
        assert flag.evaluate() is False

    def test_ignores_any_context(self):
        provider = feature_flag.InMemoryProvider(
            flags={
                self.SimpleFeatureToggle.key: {
                    "enabled": True,
                    "context": ["account1"],
                },
            }
        )

        flag = self.SimpleFeatureToggle(provider=provider)

        assert flag
        assert flag.evaluate() is True


class TestFeatureToggleWithContext:
    class FeatureToggleWithContext(feature_flag.ContextAwareFlag):
        key = "context_enabled"

    class ContextToggleWithContextRemoved(feature_flag.ContextAwareFlag):
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

        assert flag.evaluate(for_context=enabled_account) is True

    def test_wrong_context(self, provider, disabled_account):
        flag = self.FeatureToggleWithContext(provider=provider)

        # But should be false when the context is wrong
        assert flag.evaluate(for_context=disabled_account) is False

    def test_boolean_evaluation_is_true_when_context_is_missing(self, provider):
        flag = self.ContextToggleWithContextRemoved(provider=provider)

        assert flag

    def test_no_context_in_value_returns_enabled_state(self, provider):
        flag = self.ContextToggleWithContextRemoved(provider=provider)

        assert flag.evaluate() is True
