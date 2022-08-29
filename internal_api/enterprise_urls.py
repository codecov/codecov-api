from django.urls import include, path

from internal_api.self_hosted.views import SettingsViewSet, UserViewSet
from utils.routers import OptionalTrailingSlashRouter, RetrieveUpdateDestroyRouter

self_hosted_router = OptionalTrailingSlashRouter()
self_hosted_router.register(r"users", UserViewSet, basename="selfhosted-users")

settings_router = RetrieveUpdateDestroyRouter()
settings_router.register("settings", SettingsViewSet, basename="selfhosted-settings")

urlpatterns = [
    path("license/", include("internal_api.license.urls")),
    path("", include(settings_router.urls)),
    path("", include(self_hosted_router.urls)),
]
