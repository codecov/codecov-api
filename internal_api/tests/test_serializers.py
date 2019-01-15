from unittest.mock import patch
from pathlib import Path

from internal_api.serializers import CommitSerializer
from core.tests.factories import CommitFactory

current_file = Path(__file__)


class TestSerializers(object):

    def test_report_serializer(self, db):
        with patch('archive.services.download_content') as mocked:
            f = open(current_file.parent.parent.parent / 'archive/tests/samples' / 'chunks.txt', 'r')
            mocked.return_value = f.read()
            commit = CommitFactory.create(message='test_report_serializer')
            res = CommitSerializer(instance=commit).data
            expected_result = {}
            assert res == expected_result
            mocked.assert_called_with(f'codecov.s3.amazonaws.com/v4/repos/4434BC2A2EC4FCA57F77B473D83F928C/commits/{commit.commitid}/chunks.txt')
