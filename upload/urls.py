from django.urls import path, re_path

from upload.views.commits import CommitViews
from upload.views.legacy import UploadDownloadHandler, UploadHandler
from upload.views.reports import ReportViews
from upload.views.uploads import UploadViews

urlpatterns = [
    # use regex to make trailing slash optional
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/download",
        UploadDownloadHandler.as_view(),
        name="upload-download",
    ),
    # Empty routes that will become the new upload endpoint eventually
    path(
        "<str:repo>/commits/<str:commit_sha>/reports/<str:report_code>/uploads",
        UploadViews.as_view(),
        name="new_upload.uploads",
    ),
    path(
        "<str:repo>/commits/<str:commit_sha>/reports",
        ReportViews.as_view(),
        name="new_upload.reports",
    ),
    path("<str:repo>/commits", CommitViews.as_view(), name="new_upload.commits"),
    # This was getting in the way of the new endpoints, so I moved to the end
    re_path("(?P<version>\w+)/?", UploadHandler.as_view(), name="upload-handler"),
]
