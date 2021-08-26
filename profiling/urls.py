from django.urls import path

from profiling.views import ProfilingUploadCreateView

urlpatterns = [
    path(
        "uploads", ProfilingUploadCreateView.as_view(), name="create_profiling_upload"
    ),
]
