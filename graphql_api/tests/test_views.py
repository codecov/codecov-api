import json

from ariadne import ObjectType, make_executable_schema
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


class ArianeViewTestCase(GraphQLTestHelper, TestCase):
    async def do_query(self, schema, query="{ failing }"):
        view = AsyncGraphqlView.as_view(schema=schema)
        request = RequestFactory().post(
            "/graphql/gh", {"query": query}, content_type="application/json"
        )
        match = ResolverMatch(func=lambda: None, args=(), kwargs={"service": "github"})

        request.resolver_match = match
        request.user = None
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
