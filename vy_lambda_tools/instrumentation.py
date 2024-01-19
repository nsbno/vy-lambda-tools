import logging
from dataclasses import dataclass
from typing import Any, MutableMapping, TYPE_CHECKING, Union

from pythonjsonlogger import jsonlogger

import vy_lambda_tools.handlers.handler

# https://github.com/python/typeshed/issues/7855
# Fixed in Python 3.11
if TYPE_CHECKING:
    _LoggerAdapter = logging.LoggerAdapter[logging.Logger]
else:
    _LoggerAdapter = logging.LoggerAdapter


class JsonLogger(_LoggerAdapter):
    """Makes the stack level correct for log calls inside instrumentation classes"""

    def __init__(self) -> None:
        base_logger = logging.getLogger(__name__)
        supported_keys = [
            "asctime",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "name",
            "pathname",
            "relativeCreated",
        ]

        custom_format = " ".join(self.log_format(supported_keys))
        json_formatter = jsonlogger.JsonFormatter(custom_format)  # type: ignore

        json_handler = logging.StreamHandler()
        json_handler.setFormatter(json_formatter)

        base_logger.addHandler(json_handler)
        base_logger.propagate = False

        base_logger.setLevel(logging.DEBUG)

        super().__init__(base_logger, {})

    def log_format(self, keys: list[str]) -> list[str]:
        return ["%({0:s})s".format(i) for i in keys]

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        kwargs["stacklevel"] = 4

        return msg, kwargs


@dataclass
class HandlerInstrumentation(vy_lambda_tools.handlers.handler.HandlerInstrumentation):
    logger: Union[JsonLogger, logging.Logger]

    def handling_api_gateway_error(self, exception: Exception) -> None:
        self.logger.error("An unexpected error happened", exc_info=exception)

    def handling_dynamodb_streams_error(self, exception: Exception) -> None:
        self.logger.error(
            "Something unexpected happened during event processing",
            exc_info=exception,
        )

    def handling_sqs_error(self, exception: Exception) -> None:
        self.logger.error(
            "There was an exception while handling the request",
            exc_info=exception,
        )
