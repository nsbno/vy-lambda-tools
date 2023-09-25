import abc
import dataclasses
import json
from dataclasses import dataclass
from typing import Optional, Union, Any, Type, NamedTuple, ClassVar
from urllib.parse import unquote, parse_qs

from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEvent,
    DynamoDBStreamEvent,
    SQSEvent,
)
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import (
    DynamoDBRecord,
)


class HandlerInstrumentation(abc.ABC):
    @abc.abstractmethod
    def handling_api_gateway_error(self, exception: Exception) -> None:
        pass

    @abc.abstractmethod
    def handling_dynamodb_streams_error(self, exception: Exception) -> None:
        pass

    @abc.abstractmethod
    def handling_sqs_error(self, exception: Exception) -> None:
        pass


class LambdaHandler(abc.ABC):
    """A handler used to work with AWS Lambda"""

    @abc.abstractmethod
    def handler(self, *args: Any, **kwargs: Any) -> Any:
        """The implementor's application logic"""
        pass

    @abc.abstractmethod
    def __call__(
        self, event: dict[str, Any], context: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """The spesific implementation for a spesific event type"""
        pass


@dataclass
class HTTPRequest:
    path_parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    body: dict[str, Any] = dataclasses.field(default_factory=dict)
    identity: Optional[str] = None


HTTPResponse = tuple[int, Union[Any, dict[str, Any]]]


def _is_json(decoded_body: str) -> bool:
    try:
        _ = json.loads(decoded_body)
        return True
    except json.JSONDecodeError:
        return False


@dataclass
class ApiGatewayHandler(LambdaHandler, abc.ABC):
    allowed_errors: ClassVar[dict[Type[Exception], int]]

    instrumentation: HandlerInstrumentation

    @abc.abstractmethod
    def handler(self, request: HTTPRequest) -> tuple[int, Union[dict[str, Any], Any]]:
        pass

    def _prepare_request(self, event: dict[str, Any]) -> HTTPRequest:
        api_gw_event = APIGatewayProxyEvent(event)

        path_parameters = (
            {key: unquote(value) for key, value in api_gw_event.path_parameters.items()}
            if api_gw_event.path_parameters
            else {}
        )

        if not api_gw_event.body:
            body = {}
        elif (
            api_gw_event.headers.get("Content-Type")
            == "application/x-www-form-urlencoded"
        ):
            body = parse_qs(api_gw_event.body)
        elif _is_json(api_gw_event.decoded_body):
            body = api_gw_event.json_body
        else:
            raise ValueError("Unsupported content type")

        return HTTPRequest(
            body=body,
            path_parameters=path_parameters,
            identity=api_gw_event.request_context.identity.account_id,
        )

    def handle_error(self, exception: Exception) -> HTTPResponse:
        status_code = self.allowed_errors.get(type(exception), 500)

        if status_code == 500:
            message = "An unexpected error happened"
            self.instrumentation.handling_api_gateway_error(exception=exception)
        else:
            message = str(exception).strip("'")

        return status_code, {"message": message, "error_type": type(exception).__name__}

    def __call__(
        self, event: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        request = self._prepare_request(event)

        try:
            status_code, body = self.handler(request)
        except Exception as e:
            status_code, body = self.handle_error(e)

        if dataclasses.is_dataclass(body):
            body = dataclasses.asdict(body)  # type: ignore

        return {"statusCode": status_code, "body": json.dumps(body)}


@dataclass
class DynamoDBStreamsHandler(LambdaHandler, abc.ABC):
    instrumentation: HandlerInstrumentation

    @abc.abstractmethod
    def handler(self, record: DynamoDBRecord) -> None:
        pass

    def __call__(
        self, event: dict[str, Any], context: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        stream_event = DynamoDBStreamEvent(event)
        last_sequence_number = None
        try:
            for record in stream_event.records:
                if not record.dynamodb:
                    continue
                last_sequence_number = record.dynamodb.sequence_number
                self.handler(record)
            return None
        except Exception as e:
            self.instrumentation.handling_dynamodb_streams_error(exception=e)
            return {"batchItemFailures": [{"itemIdentifier": last_sequence_number}]}


class DecodedOutput(NamedTuple):
    body: dict[str, Any]
    metadata: dict[str, Any]


class EnvelopeDecoder(abc.ABC):
    """Decodes a single record in an SQS request"""

    @abc.abstractmethod
    def decode(self, event: dict[str, Any]) -> DecodedOutput:
        pass


class SNSEnvelope(EnvelopeDecoder):
    """Envelope decoder used for when passing SNS events to SQS"""

    def decode(self, event: dict[str, Any]) -> DecodedOutput:
        return DecodedOutput(
            body=json.loads(event["Message"]),
            metadata={key: value for key, value in event.items() if key != "Message"},
        )


class EventBridgeEnvelope(EnvelopeDecoder):
    """Envelope decoder used for when passing EventBridge events to SQS"""

    def decode(self, event: dict[str, Any]) -> DecodedOutput:
        return DecodedOutput(
            body=event["detail"],
            metadata={key: value for key, value in event.items() if key != "detail"},
        )


@dataclass
class SQSHandler(LambdaHandler, abc.ABC):
    """Lambda handler for API Gateway events

    Architected for one function per method.
    """

    envelope: ClassVar[EnvelopeDecoder]

    instrumentation: HandlerInstrumentation

    @abc.abstractmethod
    def handler(self, body: dict[str, Any], metadata: dict[str, Any]) -> None:
        """The implementor puts their application logic here"""
        pass

    def __new__(cls, *args: Any, **kwargs: Any) -> "SQSHandler":
        if not hasattr(cls, "envelope"):
            raise NotImplementedError(
                "Subclasses of SQSHandler needs to specify an envelope decoder"
            )

        return super().__new__(cls)

    def __call__(
        self, event: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        sqs_event = SQSEvent(event)

        failed_items = []
        for record in sqs_event.records:
            try:
                record_event = json.loads(record.body)
                response_body, metadata = self.envelope.decode(record_event)
                self.handler(response_body, metadata)
            except Exception as e:
                self.instrumentation.handling_sqs_error(exception=e)
                failed_items.append(record.message_id)

        return {
            "batchItemFailures": [{"itemIdentifier": item} for item in failed_items]
        }
