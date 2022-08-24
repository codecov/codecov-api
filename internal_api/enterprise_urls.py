from django.urls import include, path

from internal_api.repo.views import RepositoryViewSet
from internal_api.self_hosted.views import UserViewSet
from utils.routers import OptionalTrailingSlashRouter

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"repos", RepositoryViewSet, basename="repos")

self_hosted_router = OptionalTrailingSlashRouter()
self_hosted_router.register(r"users", UserViewSet, basename="selfhosted-users")

urlpatterns = [
    path("charts/", include("internal_api.chart.urls")),
    path("license/", include("internal_api.license.urls")),
    path("self_hosted/", include(self_hosted_router.urls)),
    path("<str:service>/<str:owner_username>/", include(repository_router.urls)),
]
