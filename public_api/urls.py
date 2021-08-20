from django.urls import path, include
from utils.routers import OptionalTrailingSlashRouter


from public_api.views import PullViewSet

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"pulls", PullViewSet, basename="pulls")


urlpatterns = [
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/",
        include(repository_router.urls),
    ),
]
