from django.urls import include, path

from public_api.views import PullViewSet
from utils.routers import OptionalTrailingSlashRouter

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"pulls", PullViewSet, basename="pulls")


urlpatterns = [
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/",
        include(repository_router.urls),
    ),
]
