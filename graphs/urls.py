from django.urls import path, re_path

from .views import BadgeHandler, GraphHandler

urlpatterns = [
    re_path(
        "branch/(?P<branch>.+)/(graph|graphs)/badge.(?P<ext>[^/]+)",
        BadgeHandler.as_view(),
        name="branch-badge",
    ),
    re_path(
        "(graph|graphs)/badge.(?P<ext>[^/]+)",
        BadgeHandler.as_view(),
        name="default-badge",
    ),
    re_path(
        "pull/(?P<pullid>[^/]+)/(graph|graphs)/(?P<graph>tree|icicle|sunburst|commits).(?P<ext>[^/]+)",
        GraphHandler.as_view(),
        name="pull-graph",
    ),
    re_path(
        "branch/(?P<branch>[^/].+)/(graph|graphs)/(?P<graph>tree|icicle|sunburst|commits).(?P<ext>[^/]+)",
        GraphHandler.as_view(),
        name="branch-graph",
    ),
    re_path(
        "(graph|graphs)/(?P<graph>tree|icicle|sunburst|commits).(?P<ext>[^/]+)",
        GraphHandler.as_view(),
        name="default-graph",
    ),
]
