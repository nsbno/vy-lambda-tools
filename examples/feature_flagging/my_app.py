import boto3

from vy_lambda_tools.feature_flag import (
    FeatureFlag,
    AWSParameterStoreProvider,
)


class PartyTimeFlag(FeatureFlag):
    key = "party_time"


class PartyVIPFlag(FeatureFlag):
    key = "party_vip"


def handler(event, context):
    provider = AWSParameterStoreProvider(
        application_name="my_app",
        ssm_client=boto3.client("ssm"),
    )

    is_party_time = PartyTimeFlag(provider=provider)
    party_vip_louge_enabled = PartyVIPFlag(provider=provider)

    if not is_party_time:
        return "Sorry, party time is disabled"

    if party_vip_louge_enabled.for_context("Wictor"):
        return "Welcome to the VIP party!"
    else:
        return "Welcome to the party!"
