"""Routing in this framework is essentially handlers that take in a request,
and sends it to the appropriate handler.

"""
import abc
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, ClassVar


class NoRoutesError(Exception):
    """Raised when a router is created without any routes."""

    def __init__(self):
        super().__init__("No routes found in the router.")


class RoutingError(Exception):
    """Raised when a router cannot route a request."""

    def __init__(self):
        super().__init__("No route found for the request.")


class DuplicateRoutesError(Exception):
    """Raised when a router is created with duplicate routes."""

    def __init__(self):
        super().__init__("Duplicate routes found in the router.")


class Route(abc.ABC):
    """A route that maps a request to a handler."""

    handler: Callable[[dict[str, Any], dict[str, Any]], Any]
    """A lambda handler to be called when the route matches the request."""

    def __init__(self, handler: Callable[[dict[str, Any], dict[str, Any]], Any]):
        self.handler = handler

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Route) and self.has_same_route(other)

    @abc.abstractmethod
    def has_same_route(self, other: "Route") -> bool:
        pass

    @abc.abstractmethod
    def matches_route(self, event: dict[str, Any], context: dict[str, Any]) -> bool:
        pass


@dataclass
class Router:
    """A handler used to route requests to the appropriate handler.

    This router is totally agnostic to the type of request it is handling,
    and is transparent to the handler that is being called.
    """

    _routes: list[Route] = field(default_factory=list)
    """The routes that the router will use to route requests"""

    def __call__(self, event: dict[str, Any], context: dict[str, Any]) -> Any:
        if len(self._routes) == 0:
            raise NoRoutesError()

        for route in self._routes:
            if route.matches_route(event, context):
                return route.handler(event, context)

        raise RoutingError()

    def add_route(self, route: Route) -> None:
        """Add a route to the router."""
        if any(route == r for r in self._routes):
            raise DuplicateRoutesError()

        self._routes.append(route)


class EventRouteBase(Route, abc.ABC):
    """A base class for routes that match on an event."""

    event_source: ClassVar[str]
    """The name of the event source that this route matches on."""

    def _is_event_source(self, event: dict[str, Any], context: dict[str, Any]) -> bool:
        if "Records" not in event:
            return False

        return any(
            record["eventSource"] == self.event_source for record in event["Records"]
        )


class SQSRoute(EventRouteBase):
    """A route that matches an SQS event."""

    event_source = "aws:sqs"

    queue_arn: str
    """The ARN of the queue that this route matches on."""

    def __init__(
        self, handler: Callable[[dict[str, Any], dict[str, Any]], Any], queue_arn: str
    ):
        super().__init__(handler)
        self.queue_arn = queue_arn

    def has_same_route(self, other: "Route") -> bool:
        return isinstance(other, SQSRoute) and self.queue_arn == other.queue_arn

    def matches_route(self, event: dict[str, Any], context: dict[str, Any]) -> bool:
        if not self._is_event_source(event, context):
            return False

        return any(
            record["eventSourceARN"] == self.queue_arn for record in event["Records"]
        )


class DynamoDBStreamsRoute(EventRouteBase):
    """A route that matches a DynamoDB Streams event."""

    event_source = "aws:dynamodb"

    table_arn: str
    """The ARN of the table that this route matches on."""

    def __init__(
        self, handler: Callable[[dict[str, Any], dict[str, Any]], Any], table_arn: str
    ):
        super().__init__(handler)
        self.table_arn = table_arn

    def has_same_route(self, other: "Route") -> bool:
        return (
            isinstance(other, DynamoDBStreamsRoute)
            and self.table_arn == other.table_arn
        )

    def matches_route(self, event: dict[str, Any], context: dict[str, Any]) -> bool:
        if not self._is_event_source(event, context):
            return False

        return any(
            record["eventSourceARN"].startswith(self.table_arn)
            for record in event["Records"]
        )


@dataclass
class APIRouteRequest:
    """A request for an API route.

    It is used to match a route to a request, regardless of the caller.
    """

    resource: str
    """The API Gateway resource of the request."""

    method: str
    """The HTTP method of the request."""


class APIRouteBase(Route, abc.ABC):
    resource: Optional[str]
    """The API Gateway resource that this route matches on."""

    method: Optional[str]
    """The HTTP method that this route matches on."""

    def __init__(
        self,
        handler: Callable[[dict[str, Any], dict[str, Any]], Any],
        resource: Optional[str] = None,
        method: Optional[str] = None,
    ):
        super().__init__(handler)
        self.resource = resource
        self.method = method

    @abc.abstractmethod
    def create_request(
        self, event: dict[str, Any], context: dict[str, Any]
    ) -> APIRouteRequest:
        pass

    @abc.abstractmethod
    def _is_event_source(self, event: dict[str, Any], context: dict[str, Any]) -> bool:
        pass

    def has_same_route(self, other: "Route") -> bool:
        if not isinstance(other, APIRouteBase):
            return False

        if self.resource == other.resource:
            if not self.method and not other.method:
                # If both methods are None, they are the both matching the same path
                return True
            if (self.method is None and other.method is not None) or (
                other.method is None and self.method is not None
            ):
                # If one method is None and the other is not,
                # one would be covering the other.
                return True

            return self.method == other.method

        return False

    def matches_route(self, event: dict[str, Any], context: dict[str, Any]) -> bool:
        if not self._is_event_source(event, context):
            return False

        request = self.create_request(event, context)

        if self.resource and self.resource != request.resource:
            return False
        if self.method and self.method != request.method:
            return False

        return True


class APIGatewayV1Route(APIRouteBase):
    """A route that matches an API Gateway v1 event."""

    def _is_event_source(self, event: dict[str, Any], context: dict[str, Any]) -> bool:
        if "resource" not in event:
            return False
        if "version" in event and event["version"] == "2.0":
            return False

        return True

    def create_request(
        self, event: dict[str, Any], context: dict[str, Any]
    ) -> APIRouteRequest:
        return APIRouteRequest(
            resource=event["resource"],
            method=event["httpMethod"],
        )
