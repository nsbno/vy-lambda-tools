import abc
from dataclasses import dataclass
from typing import Any, Optional

from aws_lambda_powertools.utilities.data_classes import DynamoDBStreamEvent
from aws_lambda_powertools.utilities.data_classes.dynamo_db_stream_event import (
    DynamoDBRecord,
)

from vy_lambda_tools.handlers.handler import LambdaHandler, HandlerInstrumentation


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
