from email.mime import base

from django.urls import include, path

# from .routers.repos import ReposRouter
import public_api.views.repos as RepoViews
from public_api.views.pulls import PullViewSet
from utils.routers import OptionalTrailingSlashRouter

repository_router = OptionalTrailingSlashRouter()
repository_router.register(r"pulls", PullViewSet, basename="pulls")
# repository_router.register(r"repos", ReposRouter, basename="repos")

urlpatterns = [
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/",
        include(repository_router.urls),
    ),
    path("<str:repo>/commits", RepoViews.repo_commits, name="public_api.commits"),
    path(
        "<str:repo>/commits/<str:commit_id>/reports",
        RepoViews.repo_commits_reports,
        name="public_api.reports",
    ),
    path(
        "<str:repo>/commits/<str:commit_id>/reports/<str:report_id>/uploads",
        RepoViews.repo_commits_reports_uploads,
        name="public_api.uploads",
    ),
]
