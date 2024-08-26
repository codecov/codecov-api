from prometheus_client import REGISTRY


# TODO: consolidate with worker/helpers/tests/unit/test_checkpoint_logger.py into shared repo
class CounterAssertion:
    def __init__(self, metric, labels, expected_value):
        self.metric = metric
        self.labels = labels
        self.expected_value = expected_value

        self.before_value = None
        self.after_value = None

    def __repr__(self):
        return f"<CounterAssertion: {self.metric} {self.labels}>"


# TODO: consolidate with worker/helpers/tests/unit/test_checkpoint_logger.py into shared repo
class CounterAssertionSet:
    def __init__(self, counter_assertions):
        self.counter_assertions = counter_assertions

    def __enter__(self):
        for assertion in self.counter_assertions:
            assertion.before_value = (
                REGISTRY.get_sample_value(assertion.metric, labels=assertion.labels)
                or 0
            )

    def __exit__(self, exc_type, exc_value, exc_tb):
        for assertion in self.counter_assertions:
            assertion.after_value = (
                REGISTRY.get_sample_value(assertion.metric, labels=assertion.labels)
                or 0
            )
            assert (
                assertion.after_value - assertion.before_value
                == assertion.expected_value
            )


# TODO: Re-enable some cheaper form of user-agent logging
# https://github.com/codecov/engineering-team/issues/1654
"""
class PrometheusUserAgentLabelTest(TestCase):
    def test_user_agent_label_added(self):
        user_agent = "iphone"

        counter_assertions = [
            CounterAssertion(
                "django_http_requests_latency_seconds_by_view_method_count",
                {
                    "view": "codecov.views.health",
                    "method": "GET",
                    "user_agent": user_agent,
                },
                1,
            ),
            CounterAssertion(
                "django_http_requests_total_by_method_total",
                {"user_agent": user_agent, "method": "GET"},
                1,
            ),
            CounterAssertion(
                "django_http_requests_total_by_transport_total",
                {"transport": "http", "user_agent": user_agent},
                1,
            ),
            CounterAssertion(
                "django_http_requests_total_by_view_transport_method_total",
                {
                    "view": "codecov.views.health",
                    "transport": "http",
                    "method": "GET",
                    "user_agent": user_agent,
                },
                1,
            ),
            CounterAssertion(
                "django_http_requests_body_total_bytes_count",
                {"user_agent": user_agent},
                1,
            ),
            CounterAssertion(
                "django_http_requests_total_by_transport_total",
                {"transport": "http", "user_agent": user_agent},
                1,
            ),
            CounterAssertion(
                "django_http_responses_total_by_status_total",
                {"status": "200", "user_agent": user_agent},
                1,
            ),
            CounterAssertion(
                "django_http_responses_total_by_status_view_method_total",
                {
                    "status": "200",
                    "view": "codecov.views.health",
                    "method": "GET",
                    "user_agent": user_agent,
                },
                1,
            ),
            CounterAssertion(
                "django_http_responses_body_total_bytes_count",
                {"user_agent": user_agent},
                1,
            ),
            CounterAssertion(
                "django_http_responses_total_by_charset_total",
                {"charset": "utf-8", "user_agent": user_agent},
                1,
            ),
        ]

        with CounterAssertionSet(counter_assertions):
            self.client.get(
                "/",
                headers={
                    "User-Agent": user_agent,
                },
            )

            for metric in REGISTRY.collect():
                if metric.name in USER_AGENT_METRICS:
                    for sample in metric.samples:
                        assert (
                            sample.labels["user_agent"]
                            == "none"  # not all requests have User-Agent header defined
                            or sample.labels["user_agent"] == user_agent
                        )
"""
