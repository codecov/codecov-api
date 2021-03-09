import pytest
import vcr
from pathlib import Path


@pytest.fixture
def codecov_vcr(request):
    current_path = Path(request.node.fspath)
    current_path_name = current_path.name.replace('.py', '')
    cls_name = request.node.cls.__name__
    cassete_path = current_path.parent / 'cassetes' / current_path_name / cls_name
    current_name = request.node.name
    casset_file_path = str(cassete_path / f"{current_name}.yaml")
    with vcr.use_cassette(
            casset_file_path,
            filter_headers=['authorization'],
            match_on=['method', 'scheme', 'host', 'port', 'path']) as cassete_maker:
        yield cassete_maker

@pytest.fixture
def mock_redis(mocker):
    m = mocker.patch('services.redis_configuration._get_redis_instance_from_url')
    redis_server = mocker.MagicMock()
    m.return_value = redis_server
    yield redis_server
