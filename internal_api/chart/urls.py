from django.urls import path
from .views import RepositoryChartHandler, OrganizationChartHandler


urlpatterns = [
    path(
        "coverage/repository",
        RepositoryChartHandler.as_view(),
        name="chart-coverage-repository",
    ),
    path(
        "coverage/organization",
        OrganizationChartHandler.as_view(),
        name="chart-coverage-organization",
    ),
]
