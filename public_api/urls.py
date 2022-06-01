from email.mime import base

from django.urls import include, path

from utils.routers import OptionalTrailingSlashRouter

from .views import PullViewSet

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"pulls", PullViewSet, basename="pulls")

urlpatterns = [
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/",
        include(repository_router.urls),
    )
]
