import json
from typing import cast

from django.conf import settings
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from graphql import GraphQLSchema

from ariadne.exceptions import HttpBadRequestError
from ariadne.format_error import format_error
from ariadne.graphql import graphql
from ariadne.types import GraphQLResult

from ariadne.contrib.django.views import GraphQLView as BaseGraphQLView


class GraphQLView(BaseGraphQLView):
    async def __call__(self, *args, **kwargs):
        return super().__call__(self, *args, **kwargs)

    async def post(
        self, request: HttpRequest, *args, **kwargs
    ):  # pylint: disable=unused-argument
        if not self.schema:
            raise ValueError("GraphQLView was initialized without schema.")

        try:
            data = self.extract_data_from_request(request)
        except HttpBadRequestError as error:
            return HttpResponseBadRequest(error.message)

        success, result = await self.execute_query(request, data)
        status_code = 200 if success else 400
        return JsonResponse(result, status=status_code)

    def execute_query(self, request: HttpRequest, data: dict) -> GraphQLResult:
        context_value = self.get_context_for_request(request)
        extensions = self.get_extensions_for_request(request, context_value)

        return graphql(
            cast(GraphQLSchema, self.schema),
            data,
            context_value=context_value,
            root_value=self.root_value,
            validation_rules=self.validation_rules,
            debug=settings.DEBUG,
            introspection=self.introspection,
            logger=self.logger,
            error_formatter=self.error_formatter or format_error,
            extensions=extensions,
            middleware=self.middleware,
        )
