from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from codecov import views
from internal_api.constants import INTERNAL_API_PREFIX

urlpatterns = [
    path("billing/", include("billing.urls")),
    path("api/", include("public_api.urls")),
    path(INTERNAL_API_PREFIX, include("internal_api.urls")),
    re_path("^validate/?", include("validate.urls")),
    path("health/", views.health),
    path("", views.health),
    path(
        "<str:service>/<str:owner_username>/<str:repo_name>/", include("graphs.urls"),
    ),
    path("upload/", include("upload.urls")),
    path("webhooks/", include("webhook_handlers.urls")),
    path("graphql/", include("graphql_api.urls")),
]

if not settings.IS_ENTERPRISE:
    urlpatterns += [
        path(f"{settings.DJANGO_ADMIN_URL}/", admin.site.urls),
        re_path(r"^redirect_app", views.redirect_app),
        path("profiling/", include("profiling.urls")),
        path("", include("codecov_auth.urls")),
    ]
