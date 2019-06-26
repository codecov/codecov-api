from pathlib import Path
import json

from django.test.utils import override_settings


from core.tests.factories import CommitFactory, RepositoryFactory
from archive.services import ArchiveService

current_file = Path(__file__)


class TestFlagsView(object):

    @override_settings(DEBUG=True)
    def test_commit_flag_view(self, mocker, db, client, codecov_vcr):
        mocked = mocker.patch.object(ArchiveService, 'read_chunks')
        f = open(
            current_file.parent.parent.parent.parent.parent / 'archive/tests/samples' / 'chunks.txt',
            'r'
        )
        mocker.patch.object(ArchiveService, 'create_root_storage')
        mocked.return_value = f.read()
        repo = RepositoryFactory.create(
            author__unencrypted_oauth_token='testqmit3okrgutcoyzscveipor3toi3nsmb927v',
            author__username='ThiagoCodecov'
        )
        parent_commit = CommitFactory.create(
            message='test_report_serializer',
            commitid='c5b6730',
            repository=repo,
        )
        commit = CommitFactory.create(
            message='test_report_serializer',
            commitid='abf6d4df662c47e32460020ab14abf9303581429',
            parent_commit_id=parent_commit.commitid,
            repository=repo,
        )
        client.force_login(user=repo.author)
        print(f'/internal/{repo.author.username}/{repo.name}/commits/{commit.commitid}/flags')
        response = client.get(f'/internal/{repo.author.username}/{repo.name}/commits/{commit.commitid}/flags')
        print(response.content)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        import pprint
        pprint.pprint(content)
        expected_result = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'name': 'unittests',
                    'report': {
                        'files': [
                            {
                                'lines': [
                                    [1, 1, None, [[0, 1, None, None, None]], None, None],
                                    [4, 1, None, [[0, 1, None, None, None]], None, None],
                                    [5, 0, None, [[0, 0, None, None, None]], None, None]],
                                'name': 'tests/__init__.py',
                                'totals': {
                                    'branches': 0, 'complexity': 0, 'complexity_total': 0,
                                    'coverage': '66.66667', 'diff': 0, 'files': 0, 'hits': 2,
                                    'lines': 3, 'messages': 0, 'methods': 0, 'misses': 1,
                                    'partials': 0, 'sessions': 0
                                }
                            },
                            {
                                'lines': [
                                    [1, 1, None, [[0, 1, None, None, None]], None, None],
                                    [2, 1, None, [[0, 1, None, None, None]], None, None],
                                    [5, 1, None, [[0, 1, None, None, None]], None, None],
                                    [6, 0, None, [[0, 0, None, None, None]], None, None],
                                    [9, 1, None, [[0, 1, None, None, None]], None, None],
                                    [10, 1, None, [[0, 1, None, None, None]], None, None],
                                    [11, 1, None, [[0, 1, None, None, None]], None, None],
                                    [12, 1, None, [[0, 1, None, None, None]], None, None],
                                    [15, 1, None, [[0, 1, None, None, None]], None, None],
                                    [16, 0, None, [[0, 0, None, None, None]], None, None]
                                ],
                                'name': 'awesome/__init__.py',
                                'totals': {'branches': 0, 'complexity': 0, 'complexity_total': 0, 'coverage': '80.00000', 'diff': 0, 'files': 0, 'hits': 8, 'lines': 10, 'messages': 0, 'methods': 0, 'misses': 2, 'partials': 0, 'sessions': 0
                                }
                            },
                            {
                                'lines': [
                                    [1, 1, None, [[0, 1, None, None, None]], None, None],
                                    [4, 1, None, [[0, 1, None, None, None]], None, None],
                                    [5, 1, None, [[0, 1, None, None, None]], None, None],
                                    [8, 1, None, [[0, 1, None, None, None]], None, None],
                                    [9, 1, None, [[0, 1, None, None, None]], None, None],
                                    [12, 1, None, [[0, 1, None, None, None]], None, None],
                                    [13, 1, None, [[0, 1, None, None, None]], None, None]],
                                'name': 'tests/test_sample.py',
                                'totals': {'branches': 0, 'complexity': 0, 'complexity_total': 0, 'coverage': '100', 'diff': 0, 'files': 0, 'hits': 7, 'lines': 7, 'messages': 0, 'methods': 0, 'misses': 0, 'partials': 0, 'sessions': 0
                                }
                            }
                        ],
                        'totals': {
                            'branches': 0,
                            'complexity': 0,
                            'complexity_total': 0,
                            'coverage': '85.00000',
                            'diff': 0,
                            'files': 3,
                            'hits': 17,
                            'lines': 20,
                            'messages': 0,
                            'methods': 0,
                            'misses': 3,
                            'partials': 0,
                            'sessions': 2
                        }
                    }
                },
                {
                    'name': 'integrations',
                    'report': {
                        'files': [
                            {
                                'lines': [
                                    [1, 0, None, [[1, 0, None, None, None]], None, None],
                                    [4, 0, None, [[1, 0, None, None, None]], None, None],
                                    [5, 0, None, [[1, 0, None, None, None]], None, None]
                                ],
                                'name': 'tests/__init__.py',
                                'totals': {
                                    'branches': 0, 'complexity': 0, 'complexity_total': 0, 'coverage': '0', 'diff': 0, 'files': 0, 'hits': 0, 'lines': 3, 'messages': 0, 'methods': 0, 'misses': 3, 'partials': 0, 'sessions': 0
                                }
                            },
                            {
                                'lines': [
                                    [1, 0, None, [[1, 0, None, None, None]], None, None],
                                    [2, 0, None, [[1, 0, None, None, None]], None, None],
                                    [5, 1, None, [[1, 1, None, None, None]], None, None],
                                    [6, 0, None, [[1, 0, None, None, None]], None, None],
                                    [9, 0, None, [[1, 0, None, None, None]], None, None],
                                    [10, 0, None, [[1, 0, None, None, None]], None, None],
                                    [11, 0, None, [[1, 0, None, None, None]], None, None],
                                    [12, 0, None, [[1, 0, None, None, None]], None, None],
                                    [15, 0, None, [[1, 0, None, None, None]], None, None],
                                    [16, 0, None, [[1, 0, None, None, None]], None, None]
                                ],
                                'name': 'awesome/__init__.py',
                                'totals': {'branches': 0, 'complexity': 0, 'complexity_total': 0, 'coverage': '10.00000', 'diff': 0, 'files': 0, 'hits': 1, 'lines': 10, 'messages': 0, 'methods': 0, 'misses': 9, 'partials': 0, 'sessions': 0}},
                            {
                                'lines': [
                                    [1, 0, None, [[1, 0, None, None, None]], None, None],
                                    [4, 0, None, [[1, 0, None, None, None]], None, None],
                                    [5, 0, None, [[1, 0, None, None, None]], None, None],
                                    [8, 0, None, [[1, 0, None, None, None]], None, None],
                                    [9, 0, None, [[1, 0, None, None, None]], None, None],
                                    [12, 1, None, [[1, 1, None, None, None]], None, None],
                                    [13, 1, None, [[1, 1, None, None, None]], None, None]
                                ],
                                'name': 'tests/test_sample.py',
                                'totals': {
                                    'branches': 0, 'complexity': 0, 'complexity_total': 0, 'coverage': '28.57143', 'diff': 0, 'files': 0, 'hits': 2, 'lines': 7, 'messages': 0, 'methods': 0, 'misses': 5, 'partials': 0, 'sessions': 0
                                }
                            }
                        ],
                        'totals': {
                            'branches': 0,
                            'complexity': 0,
                            'complexity_total': 0,
                            'coverage': '15.00000',
                            'diff': 0,
                            'files': 3,
                            'hits': 3,
                            'lines': 20,
                            'messages': 0,
                            'methods': 0,
                            'misses': 17,
                            'partials': 0,
                            'sessions': 2
                        }
                    }
                }
            ]
        }
        assert content == expected_result
        mocked.assert_called_with(
            'abf6d4df662c47e32460020ab14abf9303581429'
        )
