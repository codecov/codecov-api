from django.urls import re_path
from .views import UploadHandler


urlpatterns = [
    # use regex to make trailing slash optional
    re_path("^/?", UploadHandler.as_view(), name="upload-handler"),
]
