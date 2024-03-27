"""Routing handlers take in a request and sends it to the appropriate handler."""
from dataclasses import dataclass
from typing import Any, Callable
from unittest import mock

import pytest

from vy_lambda_tools.routing import (
    Router,
    NoRoutesError,
    Route,
    RoutingError,
    DuplicateRoutesError,
)


class TestRoutingHandler:
    def test_router_without_routes_gives_runtime_error(self):
        """Any router that is created without any routes should is invalid."""
        router = Router()

        with pytest.raises(NoRoutesError):
            router({}, {})

    def test_events_without_matching_route_gives_routing_error(self):
        """Events that do not match any route should give a routing error."""
        router = Router()

        class NonMatchingRoute(Route):
            def has_same_route(self, other: "Route") -> bool:
                return False

            def matches_route(self, event, context) -> bool:
                return False

        router.add_route(NonMatchingRoute(lambda event, context: None))

        with pytest.raises(RoutingError):
            router({}, {})

    def test_router_with_one_route_sends_correct_event_to_handler(self):
        """A router with one route should send the event to the correct handler."""
        router = Router()

        expected_response = {
            "message": "This was a thriumph! I'm making a note here: huge success."
        }

        class AlwaysMatchingRoute(Route):
            def has_same_route(self, other: "Route") -> bool:
                return True

            def matches_route(
                self, event: dict[str, Any], context: dict[str, Any]
            ) -> bool:
                return True

        handler = mock.Mock()
        router.add_route(AlwaysMatchingRoute(handler))

        router({}, {})

        assert handler.called

    def test_router_with_multiple_routes_sends_correct_event_to_handler(self):
        """A router with multiple routes should send the event to the correct handler."""
        router = Router()

        class ConditionalMatchingRoute(Route):
            match_on_message: str
            """Message that matches the route"""

            def __init__(self, match_on_message: str, handler: Callable):
                self.match_on_message = match_on_message
                super().__init__(handler)

            def has_same_route(self, other: "Route") -> bool:
                return False

            def matches_route(
                self, event: dict[str, Any], context: dict[str, Any]
            ) -> bool:
                return event["message"] == self.match_on_message

        handler_a = mock.Mock()
        handler_b = mock.Mock()

        router.add_route(ConditionalMatchingRoute("A", handler_a))
        router.add_route(ConditionalMatchingRoute("B", handler_b))

        router({"message": "A"}, {})

        assert handler_a.called
        assert not handler_b.called

    def test_router_with_duplicate_routes_gives_routing_error(self):
        """A router with duplicate routes should give a routing error."""
        router = Router()

        class AlwaysDuplicatedRoute(Route):
            def has_same_route(self, other: "Route") -> bool:
                return True

            def matches_route(
                self, event: dict[str, Any], context: dict[str, Any]
            ) -> bool:
                return False

        router.add_route(AlwaysDuplicatedRoute(lambda event, context: None))

        with pytest.raises(DuplicateRoutesError):
            router.add_route(AlwaysDuplicatedRoute(lambda event, context: None))
