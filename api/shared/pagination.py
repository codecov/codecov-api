from rest_framework.pagination import CursorPagination, PageNumberPagination


class CodecovCursorPagination(CursorPagination):
    page_size_query_param = "page_size"


class StandardPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        response = super(StandardPageNumberPagination, self).get_paginated_response(
            data
        )
        response.data["total_pages"] = self.page.paginator.num_pages
        return response


class PaginationMixin:
    """
    Allows dynamicly switching between the default page number based pagination (above)
    and cursor based pagination.

    Specifying a `cursor` query string parameter will switch to the cursor-based pagination.
    """

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            if self.pagination_class is None:
                self._paginator = None
            else:
                if "cursor" in self.request.query_params:
                    self._paginator = CodecovCursorPagination()
                else:
                    self._paginator = self.pagination_class()
        return self._paginator
