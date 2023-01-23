import os
from pathlib import Path

import fakeredis
import pytest
import vcr
from django.conf import settings

# we need to enable this in the test environment since we're often creating
# timeseries data and then asserting something about the aggregates all in
# a single transaction.  calling `refresh_continuous_aggregate` doesn't work
# either since it cannot be called in a transaction.
settings.TIMESERIES_REAL_TIME_AGGREGATES = True


def pytest_configure(config):
    """
    pytest_configure is the canonical way to configure test server for entire testing suite
    """
    print("called pytest_configure hook")


@pytest.fixture
def codecov_vcr(request):
    current_path = Path(request.node.fspath)
    current_path_name = current_path.name.replace(".py", "")
    cls_name = request.node.cls.__name__
    cassete_path = current_path.parent / "cassetes" / current_path_name / cls_name
    current_name = request.node.name
    casset_file_path = str(cassete_path / f"{current_name}.yaml")
    with vcr.use_cassette(
        casset_file_path,
        filter_headers=["authorization"],
        match_on=["method", "scheme", "host", "port", "path"],
    ) as cassete_maker:
        yield cassete_maker


@pytest.fixture
def mock_redis(mocker):
    m = mocker.patch("services.redis_configuration._get_redis_instance_from_url")
    redis_server = fakeredis.FakeStrictRedis()
    m.return_value = redis_server
    yield redis_server
