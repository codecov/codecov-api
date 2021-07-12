from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.instrumentation.django import DjangoInstrumentor
from datetime import datetime
import os
import json
import requests
import logging


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
    """
    instrument is called in both development and production environments

    NOTE TO DEVELOPERS:

    * instrument() is currently being used with contract coverage work. This
      is experimental, but because we want to collect production data must be
      merged into master. The values hard-coded here are for demonstration
      purposes only, and are to be removed before using contract coverage in
      any serious capacity.
    * also note that, unless TRANSMIT_SPANS is set in your environment, this
      function will not be called
    """
    # api = os.environ['CODECOV_API']
    # token = os.environ['CODECOV_TOKEN']
    
    # THESE ARE NOT PRODUCTION VALUES
    env = os.environ.get('CODECOV_ENV')
    api = "https://contract.codecov.dev"
    token = "teststhnbb89l6t1om6zrst36d8ld5i3izrk"

    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer_provider().get_tracer(__name__)

    trace.get_tracer_provider().add_span_processor(
        SimpleSpanProcessor(CodecovExporter({
            'api': api,
            'env': env,
            'token': token,
            'release': '0.0.9'
        }))
    )
    print("instrumenting with OpenTelemetry")
    DjangoInstrumentor().instrument()
