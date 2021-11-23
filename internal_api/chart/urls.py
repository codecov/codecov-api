from django.urls import path, re_path

from .views import OrganizationChartHandler, RepositoryChartHandler

urlpatterns = [
    re_path(
        r"^(?P<service>\w+)/(?P<owner_username>[\w|-]+)/coverage/repository\/?$",
        RepositoryChartHandler.as_view(),
        name="chart-coverage-repository",
    ),
    re_path(
        r"^(?P<service>\w+)/(?P<owner_username>[\w|-]+)/coverage/organization\/?$",
        OrganizationChartHandler.as_view(),
        name="chart-coverage-organization",
    ),
]
