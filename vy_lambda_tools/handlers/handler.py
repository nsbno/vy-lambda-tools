import abc
from typing import Any, Optional


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
