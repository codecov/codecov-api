from django.urls import include, path

from internal_api.repo.views import RepositoryViewSet
from utils.routers import OptionalTrailingSlashRouter

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"repos", RepositoryViewSet, basename="repos")

urlpatterns = [
    path("charts/", include("internal_api.chart.urls")),
    path("license/", include("internal_api.license.urls")),
    path("<str:service>/<str:owner_username>/", include(repository_router.urls)),
]
