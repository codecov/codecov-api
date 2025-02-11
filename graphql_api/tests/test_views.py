import json
from unittest.mock import Mock, patch

from ariadne import ObjectType, gql, make_executable_schema
from ariadne.validation import cost_directive
from django.test import RequestFactory, TestCase, override_settings
from django.urls import ResolverMatch
from prometheus_client import REGISTRY

from codecov.commands.exceptions import Unauthorized

from ..views import AsyncGraphqlView, QueryMetricsExtension
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


def generate_schema_with_required_variables():
    types = gql(
        """
        type Query {
            person_exists(name: String!): Boolean
            stuff: String
        }
        """
    )
    query_bindable = ObjectType("Query")

    # Add a resolver for the `person_exists` field
    @query_bindable.field("person_exists")
    def resolve_person_exists(_, info, name):
        return name is not None  # Example resolver logic

    return make_executable_schema(types, query_bindable)


class AriadneViewTestCase(GraphQLTestHelper, TestCase):
    async def do_query(self, schema, query="{ failing }", variables=None):
        view = AsyncGraphqlView.as_view(schema=schema)
        data = {"query": query}
        if variables is not None:
            data["variables"] = variables

        request = RequestFactory().post(
            "/graphql/gh", data, content_type="application/json"
        )
        match = ResolverMatch(func=lambda: None, args=(), kwargs={"service": "github"})

        request.resolver_match = match
        request.user = None
        request.current_owner = None
        res = await view(request, service="gh")
        return json.loads(res.content)

    @override_settings(DEBUG=True)
    @patch("logging.Logger.info")
    async def test_when_debug_is_true(self, patched_log):
        before = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "unknown_type", "operation_name": "unknown_name"},
        )
        errors_before = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "unknown_type", "operation_name": "unknown_name"},
        )
        timer_before = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "unknown_type", "operation_name": "unknown_name"},
        )
        schema = generate_schema_that_raise_with(Exception("hello"))
        data = await self.do_query(schema)
        assert data["errors"] is not None
        assert data["errors"][0]["message"] == "hello"
        assert data["errors"][0]["extensions"] is not None
        after = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "unknown_type", "operation_name": "unknown_name"},
        )
        errors_after = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "unknown_type", "operation_name": "unknown_name"},
        )
        timer_after = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "unknown_type", "operation_name": "unknown_name"},
        )
        assert after - before == 1
        assert errors_after - errors_before == 1
        assert timer_after - timer_before == 1
        patched_log.assert_called_with(
            "Could not match gql query format for logging",
            extra=dict(
                query_slice="{ failing }",
            ),
        )

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

    @override_settings(DEBUG=True)
    async def test_when_bad_query(self):
        schema = generate_schema_that_raise_with(Unauthorized())
        data = await self.do_query(schema, " { fieldThatDoesntExist }")
        assert data["errors"] is not None
        assert (
            data["errors"][0]["message"]
            == "Cannot query field 'fieldThatDoesntExist' on type 'Query'."
        )

    @override_settings(DEBUG=False)
    async def test_when_bad_query_and_anonymous(self):
        schema = generate_schema_that_raise_with(Unauthorized())
        data = await self.do_query(schema, " { fieldThatDoesntExist }")
        assert data["errors"] is not None
        assert data["errors"][0]["message"] == "INTERNAL SERVER ERROR"

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

    @patch("logging.Logger.info")
    async def test_query_metrics_extension_set_type_and_name(self, patched_log):
        extension = QueryMetricsExtension()
        sample_named_query = "query MySession { operation body }"
        sample_named_mutation = "mutation($input: CancelTrialInput!) { operation body }"
        sample_unnamed_query = "{ owner(username: me) { continued operation body } }"
        sample_wildcard = "{ failing }"

        assert extension.operation_type is None
        assert extension.operation_name is None

        extension.set_type_and_name(query=sample_named_query)
        assert extension.operation_type == "query"
        assert extension.operation_name == "MySession"

        extension.set_type_and_name(query=sample_named_mutation)
        assert extension.operation_type == "mutation"
        assert extension.operation_name == "CancelTrialInput"

        extension.set_type_and_name(query=sample_unnamed_query)
        assert extension.operation_type == "unknown_type"
        assert extension.operation_name == "owner"

        extension.set_type_and_name(query=sample_wildcard)
        assert extension.operation_type == "unknown_type"
        assert extension.operation_name == "unknown_name"
        patched_log.assert_called_with(
            "Could not match gql query format for logging",
            extra=dict(
                query_slice="{ failing }",
            ),
        )

    @patch("regex.match")
    @patch("logging.Logger.error")
    @patch("logging.Logger.info")
    async def test_query_metrics_extension_set_type_and_name_timeout(
        self, patched_info_log, patched_error_log, patched_regex
    ):
        patched_regex.side_effect = TimeoutError
        extension = QueryMetricsExtension()
        sample_named_query = "query MySession { operation body }"

        extension.set_type_and_name(query=sample_named_query)

        patched_info_log.assert_called_with(
            "Could not match gql query format for logging",
            extra=dict(
                query_slice=sample_named_query[:30],
            ),
        )
        patched_error_log.assert_called_with(
            "Regex Timeout Error",
            extra=dict(
                query_slice=sample_named_query[:30],
            ),
        )
        assert extension.operation_type == "unknown_type"
        assert extension.operation_name == "unknown_name"

    @patch("graphql_api.views.GQL_REQUEST_MADE_COUNTER.labels")
    @patch("graphql_api.views.GQL_ERROR_TYPE_COUNTER.labels")
    @patch("graphql_api.views.AsyncGraphqlView._check_ratelimit")
    @override_settings(DEBUG=False, GRAPHQL_RATE_LIMIT_RPM=1000)
    async def test_when_rate_limit_reached(
        self, mocked_check_ratelimit, mocked_error_counter, mocked_request_counter
    ):
        schema = generate_cost_test_schema()
        mocked_check_ratelimit.return_value = True
        response = await self.do_query(schema, " { stuff }")

        assert response["status"] == 429
        assert (
            response["detail"]
            == "It looks like you've hit the rate limit of 1000 req/min. Try again later."
        )

        mocked_error_counter.assert_called_with(
            error_type="rate_limit", path="/graphql/gh"
        )
        mocked_request_counter.assert_called_with(path="/graphql/gh")

    @override_settings(
        DEBUG=False, GRAPHQL_RATE_LIMIT_RPM=0, GRAPHQL_RATE_LIMIT_ENABLED=False
    )
    def test_rate_limit_disabled(self):
        # rate limit is 0, so any request would cause a rate limit if the GQL rate limit was enabled
        view = AsyncGraphqlView()
        request = Mock()

        result = view._check_ratelimit(request)
        assert result == False

    def test_client_ip_from_x_forwarded_for(self):
        view = AsyncGraphqlView()
        request = Mock()
        request.META = {"HTTP_X_FORWARDED_FOR": "127.0.0.1,blah", "REMOTE_ADDR": "lol"}

        result = view.get_client_ip(request)
        assert result == "127.0.0.1"

    def test_client_ip_from_remote_addr(self):
        view = AsyncGraphqlView()
        request = Mock()
        request.META = {"HTTP_X_FORWARDED_FOR": None, "REMOTE_ADDR": "lol"}

        result = view.get_client_ip(request)
        assert result == "lol"

    async def test_required_variable_present(self):
        schema = generate_schema_with_required_variables()

        query = """
        query ($name: String!) {
            person_exists(name: $name)
        }
        """

        #  Provide the variable
        data = await self.do_query(schema, query=query, variables={"name": "Bob"})

        assert data is not None
        assert "data" in data
        assert data["data"]["person_exists"] is True

    async def test_required_variable_missing(self):
        schema = generate_schema_with_required_variables()

        query = """
        query ($name: String!) {
            person_exists(name: $name)
        }
        """

        # Don't provide the variable
        data = await self.do_query(schema, query=query, variables={})

        assert data == {"detail": "Missing required variables: name", "status": 400}

    async def test_empty_request_body(self):
        schema = generate_schema_with_required_variables()

        request = RequestFactory().post(
            "/graphql/gh", "", content_type="application/json"
        )
        match = ResolverMatch(func=lambda: None, args=(), kwargs={"service": "github"})
        request.resolver_match = match
        request.user = None
        request.current_owner = None

        view = AsyncGraphqlView.as_view(schema=schema)
        response = await view(request, service="gh")

        assert response.status_code == 400
        assert json.loads(response.content) == {
            "status": 400,
            "detail": "Invalid JSON response received.",
        }
