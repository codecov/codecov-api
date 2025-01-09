from typing import Any

from django.http import HttpResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response


class GraphBadgeAPIMixin(object):
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        ext = self.kwargs.get("ext")
        if ext not in self.extensions:
            return Response(
                {
                    "detail": f"File extension should be one of [ {' || '.join(self.extensions)} ]"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        graph = self.get_object(
            request, *args, **kwargs
        )  # for badge handler this will get the badge, for graph it will get the graph
        # do all the header stuff and return the response

        response = HttpResponse(graph)
        if self.kwargs.get("ext") == "svg":
            response["Content-Disposition"] = ' inline; filename="{}.svg"'.format(
                self.filename
            )
            response["Content-Type"] = "image/svg+xml"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
            response["Access-Control-Expose-Headers"] = (
                "Content-Type, Cache-Control, Expires, Etag, Last-Modified"
            )
            response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        return response
