from rest_framework.pagination import CursorPagination


class CodecovCursorPagination(CursorPagination):
    ordering = '-updatestamp'
