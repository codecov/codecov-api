import json
import logging
import os
import shutil
import socket
from asyncio import iscoroutine
from typing import Any, Collection, Optional, Type

from ariadne import format_error
from ariadne.validation import cost_validator
from ariadne_django.views import GraphQLAsyncView
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from graphql import DocumentNode
from graphql.error.graphql_error import GraphQLError
from sentry_sdk import capture_exception

from codecov.commands.exceptions import BaseException
from codecov.commands.executor import get_executor_from_request
from codecov.db import sync_to_async
from services import ServiceException

from .schema import schema

log = logging.getLogger(__name__)


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
        Some requests causes temporary files to be created in /tmp (eg BundleAnalysis)
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
    extensions = []

    def get_validation_rules(
        self,
        context_value: Optional[Any],
        document: DocumentNode,
        data: dict,
    ) -> Optional[Collection]:
        return [
            cost_validator(
                maximum_cost=150,
                default_cost=1,
                variables=data.get("variables"),
            )
        ]

    validation_rules = get_validation_rules  # type: ignore

    async def get(self, *args, **kwargs):
        if settings.GRAPHQL_PLAYGROUND:
            return await super().get(*args, **kwargs)
        # No GraphqlPlayground if no settings.DEBUG
        return HttpResponseNotAllowed(["POST"])

    async def post(self, request, *args, **kwargs):
        await self._get_user(request)

        # get request body information
        req_body = json.loads(request.body.decode("utf-8")) if request.body else {}

        # clean up graphql query to remove new lines and extra spaces
        if "query" in req_body and isinstance(req_body["query"], str):
            req_body["query"] = req_body["query"].replace("\n", " ")
            req_body["query"] = req_body["query"].replace("  ", "").strip()

        # put everything together for log
        log_data = {
            "server_hostname": socket.gethostname(),
            "request_method": request.method,
            "request_path": request.get_full_path(),
            "request_body": req_body,
            "user": request.user,
        }
        log.info("GraphQL Request", extra=log_data)

        # request.user = await get_user(request) or AnonymousUser()
        with RequestFinalizer(request):
            response = await super().post(request, *args, **kwargs)

            content = response.content.decode("utf-8")
            data = json.loads(content)

            if "errors" in data:
                error_message = data["errors"][0]["message"]
                if "The query exceeds the maximum cost" in error_message:
                    costs = data["errors"][0]["extensions"]["cost"]
                    log.error(
                        "Query Cost Exceeded",
                        extra=dict(
                            requested_cost=costs["requestedQueryCost"],
                            maximum_cost=costs["maximumAvailable"],
                        ),
                    )
                    return HttpResponseBadRequest("Your query is too costly.")
            return response

    def context_value(self, request):
        return {
            "request": request,
            "service": request.resolver_match.kwargs["service"],
            "executor": get_executor_from_request(request),
        }

    def error_formatter(self, error, debug=False):
        # the only way to check for a malformatted query
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


BaseAriadneView = AsyncGraphqlView.as_view()


async def ariadne_view(request, service):
    response = BaseAriadneView(request, service)
    if iscoroutine(response):
        response = await response
    return response


ariadne_view.csrf_exempt = True
