from django.conf import settings, urls
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView
from rest_framework.exceptions import server_error

from api.shared.error_views import not_found
from utils.routers import OptionalTrailingSlashRouter, RetrieveUpdateDestroyRouter

from .branch.views import BranchViewSet
from .commit.views import CommitsUploadsViewSet, CommitsViewSet
from .compare.views import CompareViewSet
from .component.views import ComponentViewSet
from .coverage.views import CoverageViewSet, FlagCoverageViewSet
from .flag.views import FlagViewSet
from .owner.views import OwnersViewSet, OwnerViewSet, UserViewSet
from .pull.views import PullViewSet
from .repo.views import RepositoryConfigView, RepositoryViewSet
from .report.views import FileReportViewSet, ReportViewSet, TotalsViewSet
from .test_results.views import TestResultsView

urls.handler404 = not_found
urls.handler500 = server_error

owners_router = OptionalTrailingSlashRouter()
owners_router.register(r"", OwnerViewSet, basename="api-v2-owners")

owner_artifacts_router = OptionalTrailingSlashRouter()
owner_artifacts_router.register(r"users", UserViewSet, basename="api-v2-users")

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"repos", RepositoryViewSet, basename="api-v2-repos")

repository_artifacts_router = OptionalTrailingSlashRouter()
repository_artifacts_router.register(r"pulls", PullViewSet, basename="api-v2-pulls")
repository_artifacts_router.register(
    r"commits", CommitsViewSet, basename="api-v2-commits"
)
repository_artifacts_router.register(
    r"branches", BranchViewSet, basename="api-v2-branches"
)
repository_artifacts_router.register(r"flags", FlagViewSet, basename="api-v2-flags")
repository_artifacts_router.register(
    r"components", ComponentViewSet, basename="api-v2-components"
)
repository_artifacts_router.register(
    r"test-results", TestResultsView, basename="api-v2-tests-results"
)

compare_router = RetrieveUpdateDestroyRouter()
compare_router.register(r"compare", CompareViewSet, basename="api-v2-compare")

coverage_router = OptionalTrailingSlashRouter()
coverage_router.register(r"coverage", CoverageViewSet, basename="api-v2-coverage")

flag_coverage_router = OptionalTrailingSlashRouter()
flag_coverage_router.register(
    r"coverage", FlagCoverageViewSet, basename="api-v2-flag-coverage"
)

totals_router = RetrieveUpdateDestroyRouter()
totals_router.register(r"totals", TotalsViewSet, basename="api-v2-totals")

report_router = RetrieveUpdateDestroyRouter()
report_router.register(r"report", ReportViewSet, basename="api-v2-report")

file_report_router = RetrieveUpdateDestroyRouter()
file_report_router.register(
    r"file_report/(?P<path>.+)", FileReportViewSet, basename="api-v2-file-report"
)

service_prefix = "<str:service>/"
owner_prefix = "<str:service>/<str:owner_username>/"
repo_prefix = "<str:service>/<str:owner_username>/repos/<str:repo_name>/"
flag_prefix = repo_prefix + "flags/<path:flag_name>/"
commit_prefix = repo_prefix + "commits/<str:commitid>/"

urlpatterns = [
    path(r"schema/", SpectacularAPIView.as_view(), name="api-v2-schema"),
    path(
        r"docs/",
        SpectacularRedocView.as_view(url_name="api-v2-schema"),
        name="api-v2-docs",
    ),
    path(
        "<str:service>/",
        OwnersViewSet.as_view({"get": "list"}),
        name="api-v2-service-owners",
    ),
    path(service_prefix, include(owners_router.urls)),
    path(owner_prefix, include(owner_artifacts_router.urls)),
    path(owner_prefix, include(repository_router.urls)),
    path(repo_prefix, include(repository_artifacts_router.urls)),
    path(
        f"{repo_prefix}config/",
        RepositoryConfigView.as_view(),
        name="api-v2-repo-config",
    ),
    path(repo_prefix, include(compare_router.urls)),
    path(repo_prefix, include(totals_router.urls)),
    path(repo_prefix, include(report_router.urls)),
    path(repo_prefix, include(file_report_router.urls)),
    path(repo_prefix, include(coverage_router.urls)),
    path(
        f"{commit_prefix}uploads/",
        CommitsUploadsViewSet.as_view({"get": "list"}),
        name="api-v2-commits-uploads",
    ),
]

if settings.TIMESERIES_ENABLED:
    urlpatterns += [
        path(repo_prefix, include(coverage_router.urls)),
        path(flag_prefix, include(flag_coverage_router.urls)),
    ]
