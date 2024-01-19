import dataclasses
import json
import logging
from dataclasses import dataclass
from typing import Any, Optional, Union, Type, Callable
from unittest.mock import Mock

import pytest
from _pytest.fixtures import fixture

from vy_lambda_tools.handlers import api_gateway
from vy_lambda_tools.handlers import sqs
from vy_lambda_tools import test_helpers
from vy_lambda_tools.handlers.sqs import (
    EnvelopeDecoder,
    SNSEnvelope,
    EventBridgeEnvelope,
)
from vy_lambda_tools.handlers.api_gateway import HTTPRequest, HTTPResponse
from vy_lambda_tools.instrumentation import HandlerInstrumentation


@dataclass
class _ApiGatewayHandlerTestStub(api_gateway.ApiGatewayHandler):
    return_code: int
    response: Union[dict[str, Any], Any]

    allowed_errors = {}

    def handler(self, request: HTTPRequest) -> tuple[int, Union[dict[str, Any], Any]]:
        return self.return_code, self.response


class TestApiGatewayHandler:
    @fixture
    def instrumentation(self) -> HandlerInstrumentation:
        return HandlerInstrumentation(logger=logging.getLogger(__name__))

    def test_should_return_response_and_status_code(
        self, instrumentation: HandlerInstrumentation
    ) -> None:
        expected_status = 200
        expected_response = {"hello": "world"}

        handler = _ApiGatewayHandlerTestStub(
            return_code=expected_status,
            response=expected_response,
            instrumentation=instrumentation,
        )

        response = handler(
            test_helpers.generate_api_gateway_event(),
            {},
        )

        assert response["statusCode"] == expected_status
        assert json.loads(response["body"]) == expected_response

    def test_should_allow_request_without_jwt(
        self, instrumentation: HandlerInstrumentation
    ) -> None:
        """To test without jwt authorization"""
        expected_status = 200
        expected_response = {"hello": "world"}

        handler = _ApiGatewayHandlerTestStub(
            return_code=expected_status,
            response=expected_response,
            instrumentation=instrumentation,
        )

        response = handler(
            test_helpers.generate_api_gateway_event_without_jwt(),
            {},
        )

        assert response["statusCode"] == expected_status
        assert json.loads(response["body"]) == expected_response

    def test_should_handle_dataclass_responses(
        self, instrumentation: HandlerInstrumentation
    ) -> None:
        @dataclass
        class Hello:
            test: str

        expected_status = 200
        expected_response = Hello(test="hello")

        handler = _ApiGatewayHandlerTestStub(
            return_code=expected_status,
            response=expected_response,
            instrumentation=instrumentation,
        )

        response = handler(test_helpers.generate_api_gateway_event(), {})

        assert response["statusCode"] == expected_status
        assert json.loads(response["body"]) == dataclasses.asdict(expected_response)

    @pytest.mark.parametrize(
        ("body", "path_parameters", "caller"),
        (
            pytest.param({}, {}, None, id="No data"),
            pytest.param({"my": "portal"}, {}, None, id="Only Body"),
            pytest.param({}, {"test": "hello! there"}, None, id="Only Path Parameters"),
            pytest.param({}, {}, "1234567890", id="Only Caller"),
            pytest.param({"my": "portal"}, {"test": "hello!"}, "1234567890", id="All"),
        ),
    )
    def test_should_handle_various_per_mutations_of_requests(
        self,
        body: Optional[dict[str, Any]],
        path_parameters: Optional[dict[str, str]],
        caller: Optional[str],
        instrumentation: HandlerInstrumentation,
    ) -> None:
        class _MyApi(api_gateway.ApiGatewayHandler):
            def handler(self, request: HTTPRequest) -> HTTPResponse:
                return 200, {
                    "body": request.body,
                    "path_parameters": request.path_parameters,
                    "caller": request.account_id,
                }

        handler = _MyApi(instrumentation=instrumentation)
        response = handler(
            test_helpers.generate_api_gateway_event(
                body=body, path_parameters=path_parameters, caller_account_id=caller
            ),
            {},
        )

        response_body = json.loads(response["body"])

        assert response_body["body"] == body
        assert response_body["path_parameters"] == path_parameters
        assert response_body["caller"] == caller

    def test_should_handle_form_urlencoded_requests(
        self, instrumentation: HandlerInstrumentation
    ) -> None:
        class _MyApi(api_gateway.ApiGatewayHandler):
            def handler(self, request: HTTPRequest) -> HTTPResponse:
                return 200, {
                    "body": request.body,
                    "path_parameters": request.path_parameters,
                    "caller": request.account_id,
                }

        handler = _MyApi(instrumentation=instrumentation)

        body = "my=portal&test=hello!"
        expected_request = {"my": ["portal"], "test": ["hello!"]}

        response = handler(
            test_helpers.generate_api_gateway_event(
                body=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ),
            {},
        )

        response_body = json.loads(response["body"])

        assert response_body["body"] == expected_request

    @pytest.mark.parametrize(
        ("registered_errors", "exception", "expected_status_code", "expected_message"),
        (
            pytest.param(
                {KeyError: 404},
                KeyError("Item does not exist"),
                404,
                "Item does not exist",
                id="Registered Error",
            ),
            pytest.param(
                {},
                KeyError("Item does not exist"),
                500,
                "An unexpected error happened",
                id="Unregistered Error",
            ),
        ),
    )
    def test_should_allow_for_custom_exception_handling(
        self,
        registered_errors: dict[Type[Exception], int],
        exception: Exception,
        expected_status_code: int,
        expected_message: str,
        instrumentation: HandlerInstrumentation,
    ) -> None:
        class _MyExceptionalApi(api_gateway.ApiGatewayHandler):
            allowed_errors = registered_errors

            def handler(self, *_: Any, **__: Any) -> Any:
                raise exception

        handler = _MyExceptionalApi(instrumentation=instrumentation)
        response = handler(test_helpers.generate_api_gateway_event(), {})

        assert response["statusCode"] == expected_status_code
        assert json.loads(response["body"]) == {
            "message": expected_message,
            "error_type": type(exception).__name__,
        }


class TestSQSHandler:
    @fixture
    def instrumentation(self) -> HandlerInstrumentation:
        return HandlerInstrumentation(logger=logging.getLogger(__name__))

    def test_should_return_nothing_on_success(
        self, instrumentation: HandlerInstrumentation
    ) -> None:
        class _Handler(sqs.SQSHandler):
            envelope = SNSEnvelope()

            def handler(self, body: dict[str, Any], metadata: dict[str, Any]) -> None:
                return None

        sqs_handler = _Handler(instrumentation=instrumentation)

        response = sqs_handler(
            test_helpers.generate_sqs_event({"message": "Hello World. I don't care"}),
            {},
        )

        assert len(response["batchItemFailures"]) == 0

    def test_should_return_batch_item_failures_on_exception(
        self, instrumentation: HandlerInstrumentation
    ) -> None:
        class _ExceptionalHandler(sqs.SQSHandler):
            envelope = SNSEnvelope()

            def handler(self, body: dict[str, Any], metadata: dict[str, Any]) -> None:
                raise Exception("Opsie Dopsie")

        sqs_handler = _ExceptionalHandler(instrumentation=instrumentation)

        event = test_helpers.generate_sqs_event(
            {"message": "Hello World. I don't care"}
        )
        response = sqs_handler(event, {})

        assert len(response["batchItemFailures"]) == 1
        assert (
            response["batchItemFailures"][0]["itemIdentifier"]
            == event["Records"][0]["messageId"]
        )

    def test_should_error_if_no_envelope_is_present(
        self, instrumentation: HandlerInstrumentation
    ) -> None:
        class _Handler(sqs.SQSHandler):
            handler = Mock()

        with pytest.raises(NotImplementedError):
            _ = _Handler(instrumentation=instrumentation)

    @pytest.mark.parametrize(
        ("envelope_handler", "generate_envelope", "metadata"),
        (
            pytest.param(SNSEnvelope(), test_helpers.generate_sns_envelope, {}),
            pytest.param(
                EventBridgeEnvelope(),
                test_helpers.generate_eventbridge_envelope,
                {"account_id": "123456789123"},
            ),
        ),
    )
    def test_with_multiple_envelopes(
        self,
        envelope_handler: EnvelopeDecoder,
        generate_envelope: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        metadata: dict[str, Any],
        instrumentation: HandlerInstrumentation,
    ) -> None:
        class _EnvelopedHandler(sqs.SQSHandler):
            envelope = envelope_handler
            handler = Mock()

        sqs_handler = _EnvelopedHandler(instrumentation=instrumentation)

        event_body = {"message": "Hello World. I don't care"}
        event = test_helpers.generate_sqs_event(
            body=event_body, envelope=generate_envelope, metadata=metadata
        )

        sqs_handler(event, {})

        assert sqs_handler.handler.call_args.args[0] == event_body
