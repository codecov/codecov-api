from django.urls import path
from .views import RepositoryChartHandler, OrganizationChartHandler


urlpatterns = [
    path(
        "<str:service>/<str:owner_username>/coverage/repository/?",
        RepositoryChartHandler.as_view(),
        name="chart-coverage-repository",
    ),
    path(
        "<str:service>/<str:owner_username>/coverage/organization/?",
        OrganizationChartHandler.as_view(),
        name="chart-coverage-organization",
    ),
]
