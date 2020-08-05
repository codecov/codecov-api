from django.urls import path, re_path
from .views import BadgeHandler

urlpatterns = [
    re_path(
        'branch/(?P<branch>[^/]+)/(graph|graphs)/badge.(?P<ext>[^/]+)',
        BadgeHandler.as_view(),
        name="branch-badge",
    ),
    re_path(
        '(graph|graphs)/badge.(?P<ext>[^/]+)',
        BadgeHandler.as_view(),
        name="default-badge",
    ),
]
