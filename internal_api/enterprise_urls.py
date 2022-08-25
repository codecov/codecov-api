from django.urls import include, path

urlpatterns = [
    path("license/", include("internal_api.license.urls")),
]
