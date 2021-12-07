import ddtrace
import opentracing
from ariadne.contrib.tracing.apollotracing import ApolloTracingExtension
from ariadne.contrib.tracing.opentracing import OpenTracingExtension
from ddtrace.opentracer import Tracer
from django.conf import settings
from opentracing.scope_managers import ThreadLocalScopeManager


class MyTracer(Tracer):
    def __init__(self):
        # Pull out commonly used properties for performance
        self._service_name = "codecov-api"
        self._scope_manager = ThreadLocalScopeManager()
        self._dd_tracer = ddtrace.tracer


def get_tracer_extension():
    if settings.DEBUG:
        return ApolloTracingExtension
    # patch the datadog opentracing adapter so it uses the right _dd_tracer
    # under the hood (ddtrace.tracer) instead of creating a new one
    tracer = MyTracer()
    # setting it be as a singleton so the OpenTracingExtension can use it
    opentracing.tracer = tracer
    return OpenTracingExtension
