from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from api.internal.constants import INTERNAL_API_PREFIX
from codecov import views

urlpatterns = [
    path("billing/", include("billing.urls")),
    path("api/v2/", include("api.public.v2.urls")),
    path("api/v1/", include("api.public.v1.urls")),
    path("api/", include("api.public.v1.urls")),  # for backwards compat
    path(INTERNAL_API_PREFIX, include("api.internal.urls")),
    re_path("^validate/?", include("validate.urls")),
    path("health/", views.health),
    path("", views.health),
    path("<str:service>/<str:owner_username>/<str:repo_name>/", include("graphs.urls")),
    path("upload/", include("upload.urls")),
    path("webhooks/", include("webhook_handlers.urls")),
    path("graphql/", include("graphql_api.urls")),
    path("", include("codecov_auth.urls")),
    path("profiling/", include("profiling.urls")),
]

if not settings.IS_ENTERPRISE:
    urlpatterns += [
        path(f"{settings.DJANGO_ADMIN_URL}/", admin.site.urls),
        re_path(r"^redirect_app", views.redirect_app),
        path("staticanalysis/", include("staticanalysis.urls")),
        path("labels/", include("labelanalysis.urls")),
    ]
