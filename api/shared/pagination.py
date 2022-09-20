from rest_framework.pagination import CursorPagination, PageNumberPagination


class CodecovCursorPagination(CursorPagination):
    ordering = "-updatestamp"


class StandardPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        response = super(StandardPageNumberPagination, self).get_paginated_response(
            data
        )
        response.data["total_pages"] = self.page.paginator.num_pages
        return response
