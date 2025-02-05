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
from django.core.handlers.wsgi import WSGIRequest
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    JsonResponse,
)
from graphql import DocumentNode
from sentry_sdk import capture_exception
from shared.metrics import Counter, Histogram, inc_counter

from codecov.commands.exceptions import BaseException
from codecov.commands.executor import get_executor_from_request
from codecov.db import sync_to_async
from services import ServiceException
from services.redis_configuration import get_redis_connection

from .schema import schema
from .validation import (
    MissingVariablesError,
    create_max_aliases_rule,
    create_max_depth_rule,
    create_required_variables_rule,
)

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

GQL_REQUEST_MADE_COUNTER = Counter(
    "api_gql_requests_made",
    "Total API GQL requests made",
    ["path"],
)

GQL_ERROR_TYPE_COUNTER = Counter(
    "api_gql_errors",
    "Number of times API GQL endpoint failed with an exception by type",
    ["error_type", "path"],
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

    def __init__(self) -> None:
        self.start_timestamp: float = 0
        self.end_timestamp: float = 0
        self.operation_type: str | None = None
        self.operation_name: str | None = None

    def set_type_and_name(self, query: str) -> None:
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

    def request_started(self, context: dict[str, Any]) -> None:
        """
        Extension hook executed at request's start.
        """
        self.set_type_and_name(query=context["clean_query"])
        self.start_timestamp = time.perf_counter()
        inc_counter(
            GQL_HIT_COUNTER,
            labels=dict(
                operation_type=self.operation_type,
                operation_name=self.operation_name,
            ),
        )

    def request_finished(self, context: dict[str, Any]) -> None:
        """
        Extension hook executed at request's end.
        """
        self.end_timestamp = time.perf_counter()
        latency = self.end_timestamp - self.start_timestamp
        GQL_REQUEST_LATENCIES.labels(
            operation_type=self.operation_type, operation_name=self.operation_name
        ).observe(latency)

    def has_errors(self, errors: list[dict[str, Any]], context: dict[str, Any]) -> None:
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

    def __init__(self, request: WSGIRequest) -> None:
        self.request = request

    def _remove_temp_files(self) -> None:
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

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
        self._remove_temp_files()


class AsyncGraphqlView(GraphQLAsyncView):
    schema = schema
    extensions = [QueryMetricsExtension]
    introspection = settings.GRAPHQL_INTROSPECTION_ENABLED

    def get_validation_rules(
        self,
        context_value: Optional[Any],
        document: DocumentNode,
        data: dict,
    ) -> Optional[Collection]:
        return [
            create_required_variables_rule(variables=data.get("variables", {})),
            create_max_aliases_rule(max_aliases=settings.GRAPHQL_MAX_ALIASES),
            create_max_depth_rule(max_depth=settings.GRAPHQL_MAX_DEPTH),
            cost_validator(
                maximum_cost=settings.GRAPHQL_QUERY_COST_THRESHOLD,
                default_cost=1,
                variables=data.get("variables"),
            ),
        ]

    validation_rules = get_validation_rules  # type: ignore

    def get_clean_query(self, request_body: dict[str, Any]) -> str | None:
        # clean up graphql query to remove new lines and extra spaces
        if "query" in request_body and isinstance(request_body["query"], str):
            clean_query = request_body["query"].replace("\n", " ")
            clean_query = clean_query.replace("  ", "").strip()
            return clean_query

    async def get(self, *args: Any, **kwargs: Any) -> HttpResponse:
        if settings.GRAPHQL_PLAYGROUND:
            return await super().get(*args, **kwargs)
        # No GraphqlPlayground if no settings.DEBUG
        return HttpResponseNotAllowed(["POST"])

    async def post(
        self, request: WSGIRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
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
        inc_counter(GQL_REQUEST_MADE_COUNTER, labels=dict(path=req_path))
        if self._check_ratelimit(request=request):
            inc_counter(
                GQL_ERROR_TYPE_COUNTER,
                labels=dict(error_type="rate_limit", path=req_path),
            )
            return JsonResponse(
                data={
                    "status": 429,
                    "detail": f"It looks like you've hit the rate limit of {settings.GRAPHQL_RATE_LIMIT_RPM} req/min. Try again later.",
                },
                status=429,
            )

        with RequestFinalizer(request):
            try:
                response = await super().post(request, *args, **kwargs)
            except MissingVariablesError as e:
                return JsonResponse(
                    data={
                        "status": 400,
                        "detail": str(e),
                    },
                    status=400,
                )

            content = response.content.decode("utf-8")
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                log.error(
                    "Failed to decode JSON response",
                    extra={"content": content, "request_body": req_body},
                )
                return JsonResponse(
                    data={
                        "status": 400,
                        "detail": "Invalid JSON response received.",
                    },
                    status=400,
                )

            if "errors" in data:
                inc_counter(
                    GQL_ERROR_TYPE_COUNTER,
                    labels=dict(error_type="all", path=req_path),
                )
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
                        inc_counter(
                            GQL_ERROR_TYPE_COUNTER,
                            labels=dict(
                                error_type="query_cost_exceeded",
                                path=req_path,
                            ),
                        )
                        return HttpResponseBadRequest(
                            JsonResponse("Your query is too costly.")
                        )
                except Exception:
                    pass
            return response

    def context_value(self, request: WSGIRequest, *_args: Any) -> dict[str, Any]:
        request_body = json.loads(request.body.decode("utf-8")) if request.body else {}
        self.request = request

        return {
            "request": request,
            "service": request.resolver_match.kwargs["service"],
            "executor": get_executor_from_request(request),
            "clean_query": self.get_clean_query(request_body) if request_body else "",
        }

    def error_formatter(self, error: Any, debug: bool = False) -> dict[str, Any]:
        user = self.request.user
        is_anonymous = user.is_anonymous if user else True
        # the only way to check for a malformed query
        is_bad_query = "Cannot query field" in error.formatted["message"]
        if debug or (not is_anonymous and is_bad_query):
            return format_error(error, debug)
        formatted = error.formatted
        formatted["message"] = "INTERNAL SERVER ERROR"
        formatted["type"] = "ServerError"
        # if this is one of our own command exception, we can tell a bit more
        original_error = error.original_error
        if isinstance(original_error, BaseException) or isinstance(
            original_error, ServiceException
        ):
            formatted["message"] = original_error.message  # type: ignore
            formatted["type"] = type(original_error).__name__
        else:
            # otherwise it's not supposed to happen, so we log it
            log.error("GraphQL internal server error", exc_info=original_error)
            capture_exception(original_error)
        return formatted

    @sync_to_async
    def _get_user(self, request: WSGIRequest) -> None:
        # force eager evaluation of `request.user` (a lazy object)
        # while we're in a sync context
        if request.user:
            request.user.pk

    def _check_ratelimit(self, request: WSGIRequest) -> bool:
        if not settings.GRAPHQL_RATE_LIMIT_ENABLED:
            return False

        redis = get_redis_connection()

        try:
            # eagerly try to get user_id from request object
            user_id = request.user.pk
        except AttributeError:
            user_id = None

        if user_id:
            key = f"rl-user:{user_id}"
        else:
            user_ip = self.get_client_ip(request)
            key = f"rl-ip:{user_ip}"

        limit = settings.GRAPHQL_RATE_LIMIT_RPM
        window = 60  # in seconds

        current_count = redis.get(key)
        if current_count is None:
            log.info(
                "[GQL Rate Limit] - Setting new key",
                extra=dict(key=key, user_id=user_id),
            )
            redis.set(name=key, ex=window, value=1)
        elif int(current_count) >= limit:
            log.warning(
                "[GQL Rate Limit] - Rate limit reached for key",
                extra=dict(key=key, limit=limit, count=current_count, user_id=user_id),
            )
            return True
        else:
            log.warning(
                "[GQL Rate Limit] - Incrementing rate limit for key",
                extra=dict(key=key, limit=limit, count=current_count, user_id=user_id),
            )
            redis.incr(key)
        return False

    def get_client_ip(self, request: WSGIRequest) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


BaseAriadneView = AsyncGraphqlView.as_view()


async def ariadne_view(request: WSGIRequest, service: str) -> HttpResponse:
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
