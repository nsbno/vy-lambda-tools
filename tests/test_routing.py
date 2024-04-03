"""Routing handlers take in a request and sends it to the appropriate handler."""
from typing import Any, Callable
from unittest import mock

import pytest

from vy_lambda_tools import test_helpers
from vy_lambda_tools.routing import (
    Router,
    NoRoutesError,
    Route,
    RoutingError,
    DuplicateRoutesError,
    SQSRoute,
    APIGatewayV1Route,
    DynamoDBStreamsRoute,
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
        """A router with multiple routes should send the event to the correct handler"""
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


class TestSQSRoutes:
    @pytest.mark.parametrize(
        "event, context",
        [
            (
                test_helpers.generate_dynamodb_event(
                    {"test": "event"},
                    "test",
                ),
                {},
            ),
            (test_helpers.generate_api_gateway_event(), {}),
        ],
    )
    def test_never_match_non_sqs_event(self, event, context):
        """An SQS route should not match a non-SQS event."""
        handler = mock.Mock()

        route = SQSRoute(
            handler, queue_arn="arn:aws:sqs:eu-west-1:123456789012:my-queue"
        )

        assert not route.matches_route(event, context)

    def test_has_same_route_is_true_for_same_route(self):
        """The same route should be the same."""
        handler = mock.Mock()

        queue_arn = "arn:aws:sqs:eu-west-1:123456789012:my-queue"

        route = SQSRoute(handler, queue_arn=queue_arn)
        same_route = SQSRoute(handler, queue_arn=queue_arn)

        assert route.has_same_route(same_route)

    def test_has_same_route_is_false_for_different_route(self):
        """Different routes should not be the same."""
        handler = mock.Mock()

        arn_base = "arn:aws:sqs:eu-west-1:123456789012:"

        route = SQSRoute(handler, queue_arn=f"{arn_base}:queue-a")
        different_route = SQSRoute(handler, queue_arn=f"{arn_base}:queue-b")

        assert not route.has_same_route(different_route)


class TestApiGatewayRoute:
    def test_has_same_route_is_false_for_different_route(self):
        """Different routes should not be the same."""
        handler = mock.Mock()

        route = APIGatewayV1Route(
            handler,
            resource="/hello/world",
        )
        different_route = APIGatewayV1Route(
            handler,
            resource="/goodbye/world",
        )

        assert not route.has_same_route(different_route)

    def test_has_same_route_is_true_for_same_route(self):
        """The same route should be the same."""
        handler = mock.Mock()

        route = APIGatewayV1Route(handler, resource="/hello/world")
        same_route = APIGatewayV1Route(handler, resource="/hello/world")

        assert route.has_same_route(same_route)

    def test_detects_duplicate_if_one_route_has_method(self):
        handler = mock.Mock()

        route = APIGatewayV1Route(
            handler,
            resource="/hello/world",
        )

        duplicate_route = APIGatewayV1Route(
            handler,
            resource="/hello/world",
            method="GET",
        )

        assert route.has_same_route(duplicate_route)

    @pytest.mark.parametrize(
        ["event", "context"],
        [
            (test_helpers.generate_dynamodb_event({"test": "event"}, "test"), {}),
            (test_helpers.generate_sqs_event({"Hello": "World"}), {}),
        ],
    )
    def test_does_not_match_non_api_gateway_event(self, event, context):
        """An API Gateway route should not match a non-API Gateway event."""
        handler = mock.Mock()

        route = APIGatewayV1Route(handler, resource="/hello/world")

        assert not route.matches_route(event, context)

    def test_does_match_api_gateway_event(self):
        """An API Gateway route should match an API Gateway event."""
        handler = mock.Mock()

        route = APIGatewayV1Route(handler)

        assert route.matches_route(
            test_helpers.generate_api_gateway_event(), context={}
        )

    @pytest.mark.parametrize(
        ["expected_path", "event"],
        [
            pytest.param(
                "/hello/world",
                test_helpers.generate_api_gateway_event(
                    resource="/hello/world",
                ),
                id="Basic Path",
            ),
            pytest.param(
                "/hello/world",
                test_helpers.generate_api_gateway_event(
                    resource="/hello/world",
                    method="GET",
                ),
                id="Basic Path and Method",
            ),
            pytest.param(
                "/hello/{my_param}",
                test_helpers.generate_api_gateway_event(
                    resource="/hello/{my_param}",
                ),
                id="Path with parameter",
            ),
        ],
    )
    def test_matches_route_with_path(
        self, expected_path: str, event: dict[str, Any]
    ) -> None:
        """An API Gateway route should match an API Gateway event."""
        handler = mock.Mock()

        route = APIGatewayV1Route(handler, resource=expected_path)

        assert route.matches_route(event, context={})


class TestDynamoDBStreamsRoute:
    def test_has_same_route_is_true_for_same_route(self):
        """The same route should be the same."""
        handler = mock.Mock()

        table_arn = "arn:aws:dynamodb:eu-west-1:123456789012:table/my-table"

        route = DynamoDBStreamsRoute(handler, table_arn=table_arn)
        same_route = DynamoDBStreamsRoute(handler, table_arn=table_arn)

        assert route.has_same_route(same_route)

    def test_has_same_route_is_false_for_different_route(self):
        """Different routes should not be the same."""
        handler = mock.Mock()

        arn_base = "arn:aws:dynamodb:eu-west-1:123456789012:table"

        route = DynamoDBStreamsRoute(handler, table_arn=f"{arn_base}/table-a")
        different_route = DynamoDBStreamsRoute(handler, table_arn=f"{arn_base}/table-b")

        assert not route.has_same_route(different_route)

    @pytest.mark.parametrize(
        "event, context",
        [
            (test_helpers.generate_sqs_event({"test": "event"}), {}),
            (test_helpers.generate_api_gateway_event(), {}),
        ],
    )
    def test_never_match_non_dynamodb_event(self, event, context):
        """A DynamoDB Streams route should not match a non-DynamoDB event."""
        handler = mock.Mock()

        route = DynamoDBStreamsRoute(
            handler, table_arn="arn:aws:dynamodb:eu-west-1:123456789012:table/my-table"
        )

        assert not route.matches_route(event, context)

    def test_matches_dynamodb_event(self):
        """A DynamoDB Streams route should match a DynamoDB Streams event."""
        handler = mock.Mock()

        table_name = "my-table"
        account_id = "123456789012"
        region = "eu-west-1"

        route = DynamoDBStreamsRoute(
            handler,
            table_arn=f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}",
        )

        assert route.matches_route(
            test_helpers.generate_dynamodb_event(
                {"any": "value"}, table_name, region, account_id
            ),
            context={},
        )
