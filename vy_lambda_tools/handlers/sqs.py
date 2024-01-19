import abc
import json
from dataclasses import dataclass
from typing import NamedTuple, Any, ClassVar

from aws_lambda_powertools.utilities.data_classes import SQSEvent

from vy_lambda_tools.handlers.handler import LambdaHandler, HandlerInstrumentation


class DecodedOutput(NamedTuple):
    body: dict[str, Any]
    metadata: dict[str, Any]


class EnvelopeDecoder(abc.ABC):
    """Decodes a single record in an SQS request"""

    @abc.abstractmethod
    def decode(self, event: dict[str, Any]) -> DecodedOutput:
        pass


class NoEnvelope(EnvelopeDecoder):
    """Envelope decoder used for when passing raw JSON to SQS"""

    def decode(self, event: dict[str, Any]) -> DecodedOutput:
        return DecodedOutput(
            body=event,
            metadata={},
        )


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
