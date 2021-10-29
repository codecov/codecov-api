from django.urls import path, re_path

from .views import UploadDownloadHandler, UploadHandler

urlpatterns = [
    # use regex to make trailing slash optional
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/download",
        UploadDownloadHandler.as_view(),
        name="upload-download",
    ),
    re_path("(?P<version>\w+)/?", UploadHandler.as_view(), name="upload-handler"),
]
