from django.urls import include, path

from api.internal.self_hosted.views import UserViewSet
from utils.routers import OptionalTrailingSlashRouter

self_hosted_router = OptionalTrailingSlashRouter()
self_hosted_router.register(r"users", UserViewSet, basename="selfhosted-users")

urlpatterns = [
    path("license/", include("api.internal.license.urls")),
    path("", include(self_hosted_router.urls)),
]
