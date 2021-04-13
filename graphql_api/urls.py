from django.urls import path
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .schema import schema
from .views import AriadneView

from ariadne.contrib.tracing.opentracing import OpenTracingExtensionSync

from ddtrace.opentracer import Tracer, set_global_tracer

tracer = Tracer("GraphQL")
set_global_tracer(tracer)


urlpatterns = [
    path(
        "<str:service>",
        csrf_exempt(
            AriadneView.as_view(schema=schema, extensions=[OpenTracingExtensionSync])
        ),
        name="graphql",
    ),
]
