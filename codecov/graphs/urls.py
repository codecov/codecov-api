from django.urls import path
from .views import BadgeHandler

urlpatterns = [
    path(
        "graphs/badge.<str:ext>",
        BadgeHandler.as_view(),
        name="default-badge",
    ),
    path(
        "branch/<str:branch>/graphs/badge.<str:ext>",
        BadgeHandler.as_view(),
        name="branch-badge",
    ),
]
