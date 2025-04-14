from django.urls import path, re_path

from upload.views.bundle_analysis import BundleAnalysisView
from upload.views.commits import CommitViews
from upload.views.empty_upload import EmptyUploadView
from upload.views.legacy import UploadDownloadHandler, UploadHandler
from upload.views.reports import ReportResultsView, ReportViews
from upload.views.test_results import TestResultsView
from upload.views.upload_completion import UploadCompletionView
from upload.views.upload_coverage import UploadCoverageView
from upload.views.uploads import UploadViews

urlpatterns = [
    path(
        "test_results/v1",
        TestResultsView.as_view(),
        name="upload-test-results",
    ),
    path(
        "bundle_analysis/v1",
        BundleAnalysisView.as_view(),
        name="upload-bundle-analysis",
    ),
    # use regex to make trailing slash optional
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/download",
        UploadDownloadHandler.as_view(),
        name="upload-download",
    ),
    # Empty routes that will become the new upload endpoint eventually
    path(
        "<str:service>/<str:repo>/commits/<str:commit_sha>/reports/<str:report_code>/uploads",
        UploadViews.as_view(),
        name="new_upload.uploads",
    ),
    path(
        "<str:service>/<str:repo>/commits/<str:commit_sha>/reports/<report_code>/results",
        ReportResultsView.as_view(),
        name="new_upload.reports_results",
    ),
    path(
        "<str:service>/<str:repo>/commits/<str:commit_sha>/reports",
        ReportViews.as_view(),
        name="new_upload.reports",
    ),
    path(
        "<str:service>/<str:repo>/commits/<str:commit_sha>/empty-upload",
        EmptyUploadView.as_view(),
        name="new_upload.empty_upload",
    ),
    path(
        "<str:service>/<str:repo>/commits/<str:commit_sha>/upload-complete",
        UploadCompletionView.as_view(),
        name="new_upload.upload-complete",
    ),
    path(
        "<str:service>/<str:repo>/commits",
        CommitViews.as_view(),
        name="new_upload.commits",
    ),
    path(
        "<str:service>/<str:repo>/upload-coverage",
        UploadCoverageView.as_view(),
        name="new_upload.upload_coverage",
    ),
    # This was getting in the way of the new endpoints, so I moved to the end
    re_path(r"(?P<version>\w+)/?", UploadHandler.as_view(), name="upload-handler"),
]
