from django.conf import settings, urls
from django.urls import include, path
from rest_framework.exceptions import server_error
from rest_framework.routers import DefaultRouter

from internal_api.branch.views import BranchViewSet
from internal_api.commit.views import CommitsViewSet
from internal_api.compare.views import CompareViewSet
from internal_api.owner.views import (
    AccountDetailsViewSet,
    InvoiceViewSet,
    OwnerViewSet,
    PlanViewSet,
    UserViewSet,
)
from internal_api.pull.views import PullViewSet
from internal_api.repo.views import RepositoryViewSet
from utils.routers import OptionalTrailingSlashRouter, RetrieveUpdateDestroyRouter

from .error_views import not_found

urls.handler404 = not_found
urls.handler500 = server_error

plans_router = OptionalTrailingSlashRouter()
plans_router.register(r"plans", PlanViewSet, basename="plans")

owners_router = OptionalTrailingSlashRouter()
owners_router.register(r"owners", OwnerViewSet, basename="owners")

owner_artifacts_router = OptionalTrailingSlashRouter()
owner_artifacts_router.register(r"users", UserViewSet, basename="users")
owner_artifacts_router.register(r"invoices", InvoiceViewSet, basename="invoices")

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

compare_router = RetrieveUpdateDestroyRouter()
compare_router.register(r"compare", CompareViewSet, basename="compare")

urlpatterns = []

if not settings.IS_ENTERPRISE:
    urlpatterns += [
        path("charts/", include("internal_api.chart.urls")),
        path("", include(plans_router.urls)),
        path("<str:service>/", include(owners_router.urls)),
        path(
            "<str:service>/<str:owner_username>/", include(owner_artifacts_router.urls)
        ),
        path(
            "<str:service>/<str:owner_username>/", include(account_details_router.urls)
        ),
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
    ]
else:
    urlpatterns += [
        path("charts/", include("internal_api.chart.urls")),
        path("<str:service>/<str:owner_username>/", include(repository_router.urls)),
    ]
