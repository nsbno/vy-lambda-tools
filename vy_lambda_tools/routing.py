"""Routing in this framework is essentially handlers that take in a request,
and sends it to the appropriate handler.

"""
import abc
from dataclasses import dataclass, field
from typing import Any, Optional, Callable


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

    handler: Callable[[dict[str, Any], dict[str, Any]], ...]
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
    """A handler used to route requests to the appropriate handler."""

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
