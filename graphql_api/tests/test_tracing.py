import ddtrace
import opentracing
from ariadne.contrib.tracing.apollotracing import ApolloTracingExtension
from ariadne.contrib.tracing.opentracing import OpenTracingExtension
from django.test import TestCase, override_settings

from ..tracing import MyTracer, get_tracer_extension


class MyTracerTestCase(TestCase):
    @override_settings(DEBUG=True)
    def test_init_tracer(self):
        tracer = MyTracer()
        # use the tracer from dd_tracer
        assert tracer._dd_tracer == ddtrace.tracer

    @override_settings(DEBUG=True)
    def test_get_tracer_extension_when_debug_is_true(self):
        extension = get_tracer_extension()
        assert extension is ApolloTracingExtension

    @override_settings(DEBUG=False)
    def test_get_tracer_extension_when_debug_is_false(self):
        extension = get_tracer_extension()
        assert extension is OpenTracingExtension
        assert isinstance(opentracing.tracer, MyTracer)
