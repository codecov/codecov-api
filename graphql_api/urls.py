from django.urls import path
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .schema import schema
from .views import AriadneView

from ariadne.contrib.tracing.opentracing import OpenTracingExtensionSync

from ddtrace.opentracer import Tracer


def init_tracer(service_name):
    from os import environ

    config = {
        "agent_hostname": environ.get("STATSD_HOST"),
        "agent_port": environ.get("STATSD_PORT"),
    }
    tracer = Tracer("Codecov-GraphQL", config=config)
    import opentracing

    opentracing.tracer = tracer


urlpatterns = [
    path(
        "<str:service>",
        csrf_exempt(
            AriadneView.as_view(schema=schema, extensions=[OpenTracingExtensionSync])
        ),
        name="graphql",
    ),
]

# config = {
#     "agent_hostname": None,
#     "agent_https": None,
#     "agent_port": None,
#     "debug": None,
#     "enabled": None,
#     "global_tags": [],
#     "sampler": None,
#     "priority_sampling": None,
#     "uds_path": None,
#     "settings": None,
# }
#
#
# tracer = MyTracer("Codecov-Graphql", config=config)
# scope = tracer.start_active_span("GraphQL Query")
# scope.span.set_tag("component", "graphql")
# scope.close()
