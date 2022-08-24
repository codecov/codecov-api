from django.urls import include, path

from internal_api.repo.views import RepositoryViewSet
from internal_api.self_hosted.views import SettingsViewSet, UserViewSet
from utils.routers import OptionalTrailingSlashRouter, RetrieveUpdateDestroyRouter

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"repos", RepositoryViewSet, basename="repos")

self_hosted_router = OptionalTrailingSlashRouter()
self_hosted_router.register(r"users", UserViewSet, basename="selfhosted-users")

settings_router = RetrieveUpdateDestroyRouter()
settings_router.register("settings", SettingsViewSet, basename="selfhosted-settings")

urlpatterns = [
    path("charts/", include("internal_api.chart.urls")),
    path("license/", include("internal_api.license.urls")),
    path("self_hosted/", include(self_hosted_router.urls)),
    path("", include(settings_router.urls)),
    path("<str:service>/<str:owner_username>/", include(repository_router.urls)),
]
