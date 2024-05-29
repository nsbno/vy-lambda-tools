import abc
import dataclasses
import json
from dataclasses import dataclass
from typing import Any, Optional, Union, ClassVar, Type
from urllib.parse import unquote, parse_qs

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from aws_lambda_powertools.utilities.data_classes.api_gateway_proxy_event import (
    APIGatewayEventAuthorizer,
)

from vy_lambda_tools.handlers.handler import LambdaHandler, HandlerInstrumentation


@dataclass
class HTTPRequest:
    path_parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    query_parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    body: dict[str, Any] = dataclasses.field(default_factory=dict)
    raw_body: Optional[str] = None
    account_id: Optional[str] = None
    jwt: Optional[APIGatewayEventAuthorizer] = None
    headers: dict[str, str] = dataclasses.field(default_factory=dict)


HTTPResponse = tuple[int, Union[Any, dict[str, Any]]]


class JSONEncoderWithSetSupport(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return list(o)

        return super().default(o)


@dataclass
class ApiGatewayHandler(LambdaHandler, abc.ABC):
    allowed_errors: ClassVar[dict[Type[Exception], int]] = {}
    json_encoder: ClassVar[type[json.JSONEncoder]] = JSONEncoderWithSetSupport

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

        query_parameters = (
            {
                key: unquote(value)
                for key, value in api_gw_event.query_string_parameters.items()
            }
            if api_gw_event.query_string_parameters
            else {}
        )

        if not api_gw_event.body:
            body = {}
        elif (
            api_gw_event.headers.get("Content-Type")
            == "application/x-www-form-urlencoded"
        ):
            body = parse_qs(api_gw_event.body)
        elif api_gw_event.decoded_body and _is_json(api_gw_event.decoded_body):
            body = api_gw_event.json_body
        else:
            raise ValueError("Unsupported content type")

        try:
            jwt = api_gw_event.request_context.authorizer
        except KeyError:
            jwt = None

        return HTTPRequest(
            body=body,
            path_parameters=path_parameters,
            query_parameters=query_parameters,
            account_id=api_gw_event.request_context.identity.account_id,
            jwt=jwt,
            headers=api_gw_event.resolved_headers_field,
            raw_body=api_gw_event.body,
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

        return {
            "headers": {
                "Content-Type": "application/json",
            },
            "statusCode": status_code,
            "body": json.dumps(body, cls=self.json_encoder),
        }


def _is_json(decoded_body: str) -> bool:
    try:
        _ = json.loads(decoded_body)
        return True
    except json.JSONDecodeError:
        return False
