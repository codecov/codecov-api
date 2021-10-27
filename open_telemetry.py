import re
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from codecovopentelem import (
    get_codecov_opentelemetry_instances,
    CoverageSpanFilter,
    UnableToStartProcessorException
)
from opentelemetry.instrumentation.django import DjangoInstrumentor
from datetime import datetime
from utils.version import get_current_version
import os
import json
import requests

log = logging.getLogger(__name__)


class CodecovExporter(SpanExporter):
    """
    CodecovExporter is used to pass span data to codecov in a way that is actionable
    """

    def __init__(self, options={}):
        """
        store values provided by user. we skip default values here to maintain
        code simplicity and ensure that it's always clear what values are passed.
        """
        self.attributes = {
            # 'api' is the backend that this exporter talks to
            'api': options['api'],

            # 'env' is either 'test' or 'prod'
            'env': options['env'],

            # 'token' is a codecov-provided token bound to a repo
            'token': options['token'],

            # 'release' is the current release number, provided by user
            'release': options['release'],
        }

    def _date_to_millis(self, dt):
        d = datetime.fromisoformat(dt.split(".")[0])
        return d.timestamp() * 1000

    def _format_span(self, span):
        """
        returns a span with codecov attributes prefixed with "codecov.request.*"
        """
        # set global attributes
        s = json.loads(span.to_json())
        span_attributes = s["attributes"]

        # start_time and end_time should be in millis
        s["start_time"] = self._date_to_millis(s["start_time"])
        s["end_time"] = self._date_to_millis(s["end_time"])

        # don't love that this exists as it can be derived
        s["duration"] = s["end_time"] - s["start_time"]

        # ::calculate path::
        # NOTE: flask uses http.route & django uses http.target?
        # TODO: figure out exactly what's going on here..
        path = span_attributes["http.route"] \
            if "http.route" in span_attributes \
            else span_attributes["http.target"]

        # path should be in format $path\/segments\/
        if path[0] == "/":
            path = path[1:]
        if path[-1] != "/":
            path = path + "/"

        # required but not used at the moment
        # for 404s it appears that django doesn't know how to set paths,
        # and so it ends up setting stuff like "HTTP GET", which totally
        # screws up results..
        s["name"] = path #s["name"] if "name" in s else path

        url = span_attributes["http.scheme"] + "://" \
            + span_attributes["http.server_name"] \
            + path

        # codecov-specific attributes
        s["attributes"] = {
            "codecov.environment": self.attributes["env"],
            "codecov.release_id": self.attributes["release"],
            "codecov.request.status_code": span_attributes["http.status_code"],
            "codecov.request.path": path,
            "codecov.request.url": url,
            "codecov.request.method": span_attributes["http.method"],
            "codecov.request.secure": span_attributes["http.scheme"] == "https",
            "codecov.request.ip": span_attributes["net.peer.ip"],
            "codecov.request.ua": "unknown",
            "codecov.request.user": "unknown",
            "codecov.request.action": "unknown",
            "codecov.request.server": span_attributes["http.server_name"]
        }

        s["events"] = []

        return s

    def export(self, spans):
        """
        export span to Codecov backend.

        oddly, on failure we don't return any debugging data, so that's just
        logged here.

        TODO (engineering notes):
            * that we should also be handling TooManyRedirects here, which I
              have skipped here for POC work
            * it's likely that we want to be accepting spans in batches. increase
              throughput but also I think for reliability's sake we'd want a single
              trace to be treated transactionally.

        returns #opentelemetry.sdk.trace.export.SpanExportResult
        see opentelemetry-python.readthedocs.io
        """
        api = self.attributes['api']

        try:
            to_send = []
            headers = {
                'content-type': 'application/json',
                'Authorization': self.attributes['token']
            }
            for span in spans:
                to_send.append(self._format_span(span))
            requests.post(api + "/api/ingest", headers=headers, json=to_send)
        except ConnectionError:
            logging.exception("failed to export all spans")
            return SpanExportResult.FAILURE
        except requests.HTTPError as e:
            print(e)
            logging.exception("HTTP server returned erroneous response")
            return SpanExportResult.FAILURE
        except requests.Timeout:
            logging.exception("request timed out")
            return SpanExportResult.FAILURE
        except Exception as e:
            print(e)
            logging.exception("request failed")
            return SpanExportResult.FAILURE

        return SpanExportResult.SUCCESS

    def shutdown(self):
        """
        this is where we end tracing session. nothing here..yet
        """
        return


def instrument():
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    log.info("Configuring opentelemetry exporter")
    current_version = get_current_version()
    current_env = "production"
    try:
        generator, exporter = get_codecov_opentelemetry_instances(
            repository_token=os.getenv("OPENTELEMETRY_TOKEN"),
            version_identifier=current_version,
            sample_rate=float(os.getenv("OPENTELEMETRY_CODECOV_RATE")),
            untracked_export_rate=0,
            filters={
                CoverageSpanFilter.regex_name_filter: None,
                CoverageSpanFilter.span_kind_filter: [trace.SpanKind.SERVER, trace.SpanKind.CONSUMER],
            },
            code=f"{current_version}:{current_env}",
            codecov_endpoint=os.getenv("OPENTELEMETRY_ENDPOINT"),
            environment=current_env,
        )
        provider.add_span_processor(generator)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except UnableToStartProcessorException:
        log.warning("Unable to start codecov open telemetry")
    DjangoInstrumentor().instrument()
