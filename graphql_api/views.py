import json
import logging
import os
import socket
import time
from asyncio import iscoroutine
from typing import Any, Collection, Optional

import regex
from ariadne import format_error
from ariadne.types import Extension
from ariadne.validation import cost_validator
from ariadne_django.views import GraphQLAsyncView
from django.conf import settings
from django.http import (
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    JsonResponse,
)
from graphql import DocumentNode
from sentry_sdk import capture_exception
from sentry_sdk import metrics as sentry_metrics
from shared.metrics import Counter, Histogram

from codecov.commands.exceptions import BaseException
from codecov.commands.executor import get_executor_from_request
from codecov.db import sync_to_async
from services import ServiceException
from services.redis_configuration import get_redis_connection

from .schema import schema

log = logging.getLogger(__name__)

GQL_HIT_COUNTER = Counter(
    "api_gql_counts_hits",
    "Number of times API GQL endpoint request starts",
    ["operation_type", "operation_name"],
)

GQL_ERROR_COUNTER = Counter(
    "api_gql_counts_errors",
    "Number of times API GQL endpoint failed with an exception",
    ["operation_type", "operation_name"],
)

GQL_REQUEST_LATENCIES = Histogram(
    "api_gql_timers_full_runtime_seconds",
    "Total runtime in seconds of this query",
    ["operation_type", "operation_name"],
    buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1, 2, 5, 10, 30],
)


# covers named and 3 unnamed operations (see graphql_api/types/query/query.py)
GQL_TYPE_AND_NAME_PATTERN = r"^(query|mutation|subscription)(?:\(\$input:|) (\w+)(?:\(| \(|{| {|!)|^(?:{) (me|owner|config)(?:\(| |{)"


class QueryMetricsExtension(Extension):
    """
    We have named and unnamed operations, we want to collect metrics on both.
        named operations have an operation_type and operation_name,
            ex: "query MySession { operation body }"
            would be tracked as operation_type = query, operation_name = MySession
        we have `me`, `owner`, and `config` as unnamed operations,
            ex: "{ owner(username: "%s") { continued operation body } }"
            this operation would be tracked as operation_type = unknown_type, operation_name = owner

    """

    def __init__(self):
        self.start_timestamp = None
        self.end_timestamp = None
        self.operation_type = None
        self.operation_name = None

    def set_type_and_name(self, query):
        operation_type = "unknown_type"  # default value
        operation_name = "unknown_name"  # default value
        try:
            match_obj = regex.match(GQL_TYPE_AND_NAME_PATTERN, query, timeout=2)
        except TimeoutError:
            # does not block the rest of the gql request, logs and falls back to default values
            query_slice = query[:30] if len(query) > 30 else query
            log.error("Regex Timeout Error", extra=dict(query_slice=query_slice))
            match_obj = None

        if match_obj:
            if match_obj.group(1) is not None:
                operation_type = match_obj.group(1)

            if match_obj.group(2) is not None:
                operation_name = match_obj.group(2)
            elif match_obj.group(3) is not None:
                operation_name = match_obj.group(3)

        self.operation_type = operation_type
        self.operation_name = operation_name
        if operation_type == "unknown_type" and operation_name == "unknown_name":
            query_slice = query[:30] if len(query) > 30 else query
            log.info(
                "Could not match gql query format for logging",
                extra=dict(query_slice=query_slice),
            )

    def request_started(self, context):
        """
        Extension hook executed at request's start.
        """
        self.set_type_and_name(query=context["clean_query"])
        self.start_timestamp = time.perf_counter()
        GQL_HIT_COUNTER.labels(
            operation_type=self.operation_type, operation_name=self.operation_name
        ).inc()

    def request_finished(self, context):
        """
        Extension hook executed at request's end.
        """
        self.end_timestamp = time.perf_counter()
        latency = self.end_timestamp - self.start_timestamp
        GQL_REQUEST_LATENCIES.labels(
            operation_type=self.operation_type, operation_name=self.operation_name
        ).observe(latency)

    def has_errors(self, errors, context):
        """
        Extension hook executed when GraphQL encountered errors.
        """
        GQL_ERROR_COUNTER.labels(
            operation_type=self.operation_type, operation_name=self.operation_name
        ).inc(len(errors))


class RequestFinalizer:
    """
    A context manager class used as a teardown step after the GraphQL request is fully handled.
    """

    # List of keys representing files to be deleted during cleanup
    TO_BE_DELETED_FILES = [
        "bundle_analysis_head_report_db_path",
        "bundle_analysis_base_report_db_path",
    ]

    def __init__(self, request):
        self.request = request

    def _remove_temp_files(self):
        """
        Some requests cause temporary files to be created in /tmp (eg BundleAnalysis)
        This cleanup step clears all contents of the /tmp directory after each request
        """
        for key in RequestFinalizer.TO_BE_DELETED_FILES:
            if hasattr(self.request, key):
                file_path = getattr(self.request, key)
                if file_path:
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                    except Exception as e:
                        log.info(
                            "Failed to delete temp file",
                            extra={"file_path": file_path, "exc": e},
                        )

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._remove_temp_files()


class AsyncGraphqlView(GraphQLAsyncView):
    schema = schema
    extensions = [QueryMetricsExtension]

    def get_validation_rules(
        self,
        context_value: Optional[Any],
        document: DocumentNode,
        data: dict,
    ) -> Optional[Collection]:
        return [
            cost_validator(
                maximum_cost=settings.GRAPHQL_QUERY_COST_THRESHOLD,
                default_cost=1,
                variables=data.get("variables"),
            )
        ]

    validation_rules = get_validation_rules  # type: ignore

    def get_clean_query(self, request_body):
        # clean up graphql query to remove new lines and extra spaces
        if "query" in request_body and isinstance(request_body["query"], str):
            clean_query = request_body["query"].replace("\n", " ")
            clean_query = clean_query.replace("  ", "").strip()
            return clean_query

    async def get(self, *args, **kwargs):
        if settings.GRAPHQL_PLAYGROUND:
            return await super().get(*args, **kwargs)
        # No GraphqlPlayground if no settings.DEBUG
        return HttpResponseNotAllowed(["POST"])

    async def post(self, request, *args, **kwargs):
        await self._get_user(request)
        # get request body information for logging
        req_body = json.loads(request.body.decode("utf-8")) if request.body else {}

        # get request path information for logging
        req_path = request.get_full_path()

        # clean up graphql query for logging, remove new lines and extra spaces
        cleaned_query = self.get_clean_query(req_body)
        if cleaned_query:
            req_body["query"] = cleaned_query

        # put everything together for log
        log_data = {
            "server_hostname": socket.gethostname(),
            "request_method": request.method,
            "request_path": req_path,
            "request_body": req_body,
            "user": request.user,
        }
        log.info("GraphQL Request", extra=log_data)
        sentry_metrics.incr("graphql.info.request_made", tags={"path": req_path})

        if self._check_ratelimit(request=request):
            sentry_metrics.incr("graphql.error.rate_limit", tags={"path": req_path})
            return JsonResponse(
                data={
                    "status": 429,
                    "detail": "It looks like you've hit the rate limit of 1000 req/min. Try again later.",
                },
                status=429,
            )

        with RequestFinalizer(request):
            response = await super().post(request, *args, **kwargs)

            content = response.content.decode("utf-8")
            data = json.loads(content)

            if "errors" in data:
                sentry_metrics.incr("graphql.error.all", tags={"path": req_path})
                try:
                    if data["errors"][0]["extensions"]["cost"]:
                        costs = data["errors"][0]["extensions"]["cost"]
                        log.error(
                            "Query Cost Exceeded",
                            extra=dict(
                                requested_cost=costs.get("requestedQueryCost"),
                                maximum_cost=costs.get("maximumAvailable"),
                                request_body=req_body,
                            ),
                        )
                        sentry_metrics.incr(
                            "graphql.error.query_cost_exceeded",
                            tags={"path": req_path},
                        )
                        return HttpResponseBadRequest(
                            JsonResponse("Your query is too costly.")
                        )
                except Exception:
                    pass
            return response

    def context_value(self, request, *_):
        request_body = json.loads(request.body.decode("utf-8")) if request.body else {}
        return {
            "request": request,
            "service": request.resolver_match.kwargs["service"],
            "executor": get_executor_from_request(request),
            "clean_query": self.get_clean_query(request_body) if request_body else "",
        }

    def error_formatter(self, error, debug=False):
        # the only way to check for a malformed query
        is_bad_query = "Cannot query field" in error.formatted["message"]
        if debug or is_bad_query:
            return format_error(error, debug)
        formatted = error.formatted
        formatted["message"] = "INTERNAL SERVER ERROR"
        formatted["type"] = "ServerError"
        # if this is one of our own command exception, we can tell a bit more
        original_error = error.original_error
        if isinstance(original_error, BaseException) or isinstance(
            original_error, ServiceException
        ):
            formatted["message"] = original_error.message
            formatted["type"] = type(original_error).__name__
        else:
            # otherwise it's not supposed to happen, so we log it
            log.error("GraphQL internal server error", exc_info=original_error)
            capture_exception(original_error)
        return formatted

    @sync_to_async
    def _get_user(self, request):
        # force eager evaluation of `request.user` (a lazy object)
        # while we're in a sync context
        if request.user:
            request.user.pk

    def _check_ratelimit(self, request):
        redis = get_redis_connection()
        user_ip = self.get_client_ip(request)
        try:
            # eagerly try to get user_id from request object
            user_id = request.user.pk
        except AttributeError:
            user_id = None

        if user_id:
            key = f"rl-user:{user_id}"
        else:
            key = f"rl-ip:{user_ip}"

        limit = 1000  # requests per minute
        window = 60  # seconds

        current_count = redis.get(key)
        if current_count is None:
            redis.setex(key, window, 1)
        elif int(current_count) >= limit:
            return True
        else:
            redis.incr(key)
        return False

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


BaseAriadneView = AsyncGraphqlView.as_view()


async def ariadne_view(request, service):
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
