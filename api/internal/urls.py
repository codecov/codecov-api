from django.conf import settings, urls
from django.urls import include, path
from rest_framework.exceptions import server_error

from api.internal.branch.views import BranchViewSet
from api.internal.commit.views import CommitsViewSet
from api.internal.compare.views import CompareViewSet
from api.internal.coverage.views import CoverageViewSet
from api.internal.enterprise_urls import urlpatterns as enterprise_urlpatterns
from api.internal.feature.views import FeaturesView
from api.internal.owner.views import (
    AccountDetailsViewSet,
    OwnerViewSet,
    UserViewSet,
)
from api.internal.pull.views import PullViewSet
from api.internal.repo.views import RepositoryViewSet
from api.internal.user.views import CurrentUserView
from api.shared.error_views import not_found
from utils.routers import OptionalTrailingSlashRouter, RetrieveUpdateDestroyRouter

urls.handler404 = not_found
urls.handler500 = server_error


owners_router = OptionalTrailingSlashRouter()
owners_router.register(r"owners", OwnerViewSet, basename="owners")

owner_artifacts_router = OptionalTrailingSlashRouter()
owner_artifacts_router.register(r"users", UserViewSet, basename="users")

account_details_router = RetrieveUpdateDestroyRouter()
account_details_router.register(
    r"account-details", AccountDetailsViewSet, basename="account_details"
)

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"repos", RepositoryViewSet, basename="repos")

repository_artifacts_router = OptionalTrailingSlashRouter()
repository_artifacts_router.register(r"pulls", PullViewSet, basename="pulls")
repository_artifacts_router.register(r"commits", CommitsViewSet, basename="commits")
repository_artifacts_router.register(r"branches", BranchViewSet, basename="branches")
repository_artifacts_router.register(r"coverage", CoverageViewSet, basename="coverage")

compare_router = RetrieveUpdateDestroyRouter()
compare_router.register(r"compare", CompareViewSet, basename="compare")

urlpatterns = []

if settings.IS_ENTERPRISE:
    urlpatterns += enterprise_urlpatterns

urlpatterns += [
    path("user", CurrentUserView.as_view(), name="current-user"),
    path("slack/", include("api.internal.slack.urls")),
    path("charts/", include("api.internal.chart.urls")),
    path("<str:service>/", include(owners_router.urls)),
    path("<str:service>/<str:owner_username>/", include(owner_artifacts_router.urls)),
    path("<str:service>/<str:owner_username>/", include(account_details_router.urls)),
    path("<str:service>/<str:owner_username>/", include(repository_router.urls)),
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/",
        include(repository_artifacts_router.urls),
    ),
    path(
        "<str:service>/<str:owner_username>/repos/<str:repo_name>/",
        include(repository_artifacts_router.urls),
    ),
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/",
        include(compare_router.urls),
    ),
    path(
        "<str:service>/<str:owner_username>/repos/<str:repo_name>/",
        include(compare_router.urls),
    ),
    path("features", FeaturesView.as_view(), name="features"),
]
