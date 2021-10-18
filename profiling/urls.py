from django.urls import path

from profiling.views import ProfilingCommitCreateView, ProfilingUploadCreateView

urlpatterns = [
    path(
        "uploads", ProfilingUploadCreateView.as_view(), name="create_profiling_upload"
    ),
    path(
        "versions", ProfilingCommitCreateView.as_view(), name="create_profiling_version"
    ),
]
