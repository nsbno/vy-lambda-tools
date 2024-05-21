import json
import uuid
from datetime import datetime
from hashlib import md5
from typing import Any, Optional, Callable, Union

from boto3.dynamodb.types import TypeSerializer


def generate_sns_envelope(body: dict[str, Any], _: Any) -> dict[str, Any]:
    """Generate an envelope for an SNS message to SQS"""
    return {"Message": json.dumps(body)}


def generate_eventbridge_envelope(
    body: dict[str, Any], metadata: dict[str, Any]
) -> dict[str, Any]:
    """Generate an envelope for an EventBridge event to SQS"""
    return {
        "version": "0",
        "id": str(uuid.uuid4()),
        "account": metadata["account_id"],
        "time": datetime.now().isoformat(),
        "region": "eu-west-1",
        "detail": body,
    }


def generate_no_envelope(body: dict[str, Any], _: Any) -> dict[str, Any]:
    """No envelope is used for SQS messages that are sent directly to the queue"""
    return body


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
                "eventSource": "aws:sqs",
                "messageId": md5(json.dumps(body).encode()),
                "body": json.dumps(envelope(body, metadata)),
            }
        ]
    }


def generate_api_gateway_event(
    resource: Optional[str] = None,
    method: Optional[str] = None,
    body: Optional[Union[dict[str, Any], str]] = None,
    path_parameters: Optional[dict[str, str]] = None,
    query_parameters: Optional[dict[str, str]] = None,
    caller_account_id: Optional[str] = None,
    jwt_claims: Optional[dict[str, Any]] = None,
    jwt_scopes: Optional[list[str]] = None,
    jwt_context: Optional[dict[str, Any]] = None,
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

    event = {
        "resource": resource,
        "httpMethod": method,
        "body": body,
        "pathParameters": path_parameters,
        "queryStringParameters": query_parameters,
        "requestContext": {
            "identity": {"accountId": caller_account_id},
            "authorizer": {
                "claims": jwt_claims,
                "scopes": jwt_scopes,
                # authorization context details injected by a Lambda Authorizer
                **(jwt_context if jwt_context is not None else {}),
            },
        },
        "headers": headers,
    }

    return event


def generate_api_gateway_event_without_jwt(
    resource: Optional[str] = None,
    method: Optional[str] = None,
    body: Optional[Union[dict[str, Any], str]] = None,
    path_parameters: Optional[dict[str, str]] = None,
    query_parameters: Optional[dict[str, str]] = None,
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
        "resource": resource,
        "httpMethod": method,
        "body": body,
        "pathParameters": path_parameters,
        "queryStringParameters": query_parameters,
        "requestContext": {
            "identity": {"accountId": caller_account_id},
        },
        "headers": headers,
    }


def generate_dynamodb_event(
    old_value: Optional[dict[str, Any]],
    table_name: str,
    aws_region: str = "eu-west-1",
    aws_account_id: str = "123456789012",
) -> dict[str, Any]:
    ts = TypeSerializer()

    stream_arn = (
        f"arn:aws:dynamodb:{aws_region}:{aws_account_id}"
        f":table/{table_name}/stream/2024-12-01T00:00:00.000"
    )

    return {
        "Records": [
            {
                "eventSource": "aws:dynamodb",
                "eventSourceARN": stream_arn,
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
                },
            }
        ]
    }
