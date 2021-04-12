from django.urls import path
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .schema import schema
from .views import AriadneView

urlpatterns = [
    path(
        "<str:service>", csrf_exempt(AriadneView.as_view(schema=schema)), name="graphql"
    ),
]
