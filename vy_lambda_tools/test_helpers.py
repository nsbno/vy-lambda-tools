import json
import uuid
from datetime import datetime
from hashlib import md5
from typing import Any, Optional, Callable, Union

from boto3.dynamodb.types import TypeSerializer


def generate_sns_envelope(body: dict[str, Any], _: Any) -> dict[str, Any]:
    return {"Message": json.dumps(body)}


def generate_eventbridge_envelope(
    body: dict[str, Any], metadata: dict[str, Any]
) -> dict[str, Any]:
    return {
        "version": "0",
        "id": str(uuid.uuid4()),
        "account": metadata["account_id"],
        "time": datetime.now().isoformat(),
        "region": "eu-west-1",
        "detail": body,
    }


def generate_sqs_event(
    body: dict[str, Any],
    envelope: Callable[
        [dict[str, Any], dict[str, Any]], dict[str, Any]
    ] = generate_sns_envelope,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if metadata is None:
        metadata = {}
    return {
        "Records": [
            {
                "messageId": md5(json.dumps(body).encode()),
                "body": json.dumps(envelope(body, metadata)),
            }
        ]
    }


def generate_api_gateway_event(
    body: Optional[Union[dict[str, Any], str]] = None,
    path_parameters: Optional[dict[str, str]] = None,
    caller_account_id: Optional[str] = None,
    jwt_claims: Optional[dict[str, Any]] = None,
    jwt_scopes: Optional[list[str]] = None,
    headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    headers = headers or {}

    if body is None:
        body = ""
    elif "application/x-www-form-urlencoded" not in headers.get("Content-Type", ""):
        try:
            body = json.dumps(body)
        except json.JSONDecodeError:
            body = body

    return {
        "body": body,
        "pathParameters": path_parameters,
        "requestContext": {
            "identity": {"accountId": caller_account_id},
            "authorizer": {"claims": jwt_claims, "scopes": jwt_scopes},
        },
        "headers": headers,
    }


def generate_api_gateway_event_without_jwt(
    body: Optional[Union[dict[str, Any], str]] = None,
    path_parameters: Optional[dict[str, str]] = None,
    caller_account_id: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    headers = headers or {}

    if body is None:
        body = ""
    elif "application/x-www-form-urlencoded" not in headers.get("Content-Type", ""):
        try:
            body = json.dumps(body)
        except json.JSONDecodeError:
            body = body

    return {
        "body": body,
        "pathParameters": path_parameters,
        "requestContext": {
            "identity": {"accountId": caller_account_id},
        },
        "headers": headers,
    }


def generate_dynamodb_event(old_value: Optional[dict[str, Any]]) -> dict[str, Any]:
    ts = TypeSerializer()
    return {
        "Records": [
            {
                "dynamodb": {
                    # We don't care about the sequence number, but it is needed
                    "SequenceNumber": md5(str(datetime.now()).encode()),
                    "OldImage": {
                        key: ts.serialize(
                            value
                            if not isinstance(value, datetime)
                            else int(value.timestamp())
                        )
                        for key, value in old_value.items()
                    }
                    if old_value is not None
                    else {},
                }
            }
        ]
    }
