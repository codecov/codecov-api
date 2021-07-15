from django.urls import path
from .views import UploadHandler, UploadDownloadHandler


urlpatterns = [
    # use regex to make trailing slash optional
    path("upload/<str:version>/", UploadHandler.as_view(), name="upload-handler"),
    path(
        "upload/<str:service>/<str:owner_username>/<str:repo_name>/download",
        UploadDownloadHandler.as_view(),
        name="upload-download",
    ),
]
