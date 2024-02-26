import json
import os
import tempfile
from unittest.mock import patch

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

    async def test_teardown_delete_temp_files(self):
        os.system("rm -rf /tmp/*")
        # Will be deleted
        tempfile.mkstemp(prefix="bundle_analysis_")
        tempfile.mkdtemp(prefix="bundle_analysis_")

        # Will not be deleted
        tempfile.mkstemp(prefix="something_else")
        tempfile.mkdtemp(prefix="something_else")

        before_files = os.listdir("/tmp")
        assert len(before_files) == 4

        schema = generate_schema_that_raise_with(Unauthorized())
        await self.do_query(schema)

        after_files = os.listdir("/tmp")
        assert len(after_files) == 2
        os.system("rm -rf /tmp/*")

    @patch("graphql_api.views.shutil.rmtree")
    async def test_teardown_delete_temp_files_exception(self, rmtree_mock):
        rmtree_mock.side_effect = Exception("something went wrong")

        os.system("rm -rf /tmp/*")
        tempfile.mkstemp(prefix="bundle_analysis_")
        tempfile.mkdtemp(prefix="bundle_analysis_")

        before_files = os.listdir("/tmp")
        assert len(before_files) == 2

        schema = generate_schema_that_raise_with(Unauthorized())
        await self.do_query(schema)

        after_files = os.listdir("/tmp")
        assert len(after_files) == 1
        os.system("rm -rf /tmp/*")

    @override_settings(IS_ENTERPRISE=True)
    @override_settings(GUEST=False)
    async def test_post_when_enterprise_and_guest_user(self):
        schema = generate_schema_that_raise_with(Unauthorized())
        view = AsyncGraphqlView.as_view(schema=schema)
        request = RequestFactory().post(
            "/graphql/gh", {"query": "{ failing }"}, content_type="application/json"
        )
        match = ResolverMatch(func=lambda: None, args=(), kwargs={"service": "github"})

        request.resolver_match = match
        request.user = None
        request.current_owner = None
        res = await view(request, service="gh")
        assert res.status_code == 405
        os.system("rm -rf /tmp/*")

    @override_settings(IS_ENTERPRISE=True)
    @override_settings(GUEST=True)
    async def test_post_when_enterprise_and_not_guest_user(self):
        schema = generate_schema_that_raise_with(Unauthorized())
        view = AsyncGraphqlView.as_view(schema=schema)
        request = RequestFactory().post(
            "/graphql/gh", {"query": "{ failing }"}, content_type="application/json"
        )
        match = ResolverMatch(func=lambda: None, args=(), kwargs={"service": "github"})

        request.resolver_match = match
        request.user = None
        request.current_owner = None
        res = await view(request, service="gh")
        assert res.status_code == 200
        os.system("rm -rf /tmp/*")
