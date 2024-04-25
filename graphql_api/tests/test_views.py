import json
from unittest.mock import patch

from ariadne import ObjectType, make_executable_schema
from ariadne.validation import cost_directive
from django.test import RequestFactory, TestCase, override_settings
from django.urls import ResolverMatch

from codecov.commands.exceptions import Unauthorized

from ..views import AsyncGraphqlView
from .helper import GraphQLTestHelper


def generate_schema_that_raise_with(exception):
    types = """
    type Query {
        failing: Boolean
    }
    """
    query_bindable = ObjectType("Query")

    @query_bindable.field("failing")
    def failing_bindable(*_):
        raise exception

    return make_executable_schema(types, query_bindable)


def generate_cost_test_schema():
    types = """
    type Query {
        stuff: String @cost(complexity: 2000)
    }
    """
    query_bindable = ObjectType("Query")

    return make_executable_schema([types, cost_directive], query_bindable)


class ArianeViewTestCase(GraphQLTestHelper, TestCase):
    async def do_query(self, schema, query="{ failing }"):
        view = AsyncGraphqlView.as_view(schema=schema)
        request = RequestFactory().post(
            "/graphql/gh", {"query": query}, content_type="application/json"
        )
        match = ResolverMatch(func=lambda: None, args=(), kwargs={"service": "github"})

        request.resolver_match = match
        request.user = None
        request.current_owner = None
        res = await view(request, service="gh")
        return json.loads(res.content)

    @override_settings(DEBUG=True)
    async def test_when_debug_is_true(self):
        schema = generate_schema_that_raise_with(Exception("hello"))
        data = await self.do_query(schema)
        assert data["errors"] is not None
        assert data["errors"][0]["message"] == "hello"
        assert data["errors"][0]["extensions"] is not None

    @override_settings(DEBUG=False)
    async def test_when_debug_is_false_and_random_exception(self):
        schema = generate_schema_that_raise_with(Exception("hello"))
        data = await self.do_query(schema)
        assert data["errors"] is not None
        assert data["errors"][0]["message"] == "INTERNAL SERVER ERROR"
        assert data["errors"][0]["type"] == "ServerError"
        assert data["errors"][0].get("extensions") is None

    @override_settings(DEBUG=False)
    async def test_when_debug_is_false_and_exception_we_know(self):
        schema = generate_schema_that_raise_with(Unauthorized())
        data = await self.do_query(schema)
        assert data["errors"] is not None
        assert data["errors"][0]["message"] == "You are not authorized"
        assert data["errors"][0]["type"] == "Unauthorized"
        assert data["errors"][0].get("extensions") is None

    @override_settings(DEBUG=False)
    async def test_when_bad_query(self):
        schema = generate_schema_that_raise_with(Unauthorized())
        data = await self.do_query(schema, " { fieldThatDoesntExist }")
        assert data["errors"] is not None
        assert (
            data["errors"][0]["message"]
            == "Cannot query field 'fieldThatDoesntExist' on type 'Query'."
        )

    @override_settings(DEBUG=False, GRAPHQL_QUERY_COST_THRESHOLD=1000)
    @patch("logging.Logger.error")
    async def test_when_costly_query(self, mock_error_logger):
        schema = generate_cost_test_schema()
        data = await self.do_query(schema, " { stuff }")

        assert data["errors"] is not None
        assert data["errors"][0]["extensions"]["cost"]["requestedQueryCost"] == 2000
        assert data["errors"][0]["extensions"]["cost"]["maximumAvailable"] == 1000
        mock_error_logger.assert_called_with(
            "Query Cost Exceeded",
            extra=dict(
                requested_cost=2000,
                maximum_cost=1000,
                request_body=dict(query="{ stuff }"),
            ),
        )
