from pathlib import Path

from internal_api.commit.serializers import ParentlessCommitSerializer
from core.tests.factories import CommitFactory, RepositoryFactory
from archive.services import ArchiveService

current_file = Path(__file__)


class TestSerializers(object):

    def test_commit_serializer(self, mocker, db, codecov_vcr):
        mocked = mocker.patch.object(ArchiveService, 'read_chunks')
        f = open(
            current_file.parent.parent.parent / 'archive/tests/samples' / 'chunks.txt',
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
        res = ParentlessCommitSerializer(instance=commit, context={'user': repo.author}).data
        expected_result = {
            'ci_passed': True,
            'author': {
                'username': commit.author.username,
                'email': commit.author.email,
                'name': commit.author.name,
            },
            'message': 'test_report_serializer',
            'commitid': 'abf6d4df662c47e32460020ab14abf9303581429',
            'repository': {
                'repoid': commit.repository.repoid,
                'name': 'example-python',
                'updatestamp': commit.repository.updatestamp.isoformat()[:-6] + 'Z'
            },
            'timestamp': commit.timestamp.isoformat()[:-6] + 'Z',
            'updatestamp': commit.updatestamp.isoformat()[:-6] + 'Z',
            'report': {
                'files': [
                    ({
                        'name': 'awesome/__init__.py',
                        'lines': [
                            (1, 1, None, [[0, 1, None, None, None]], None, None),
                            (2, 1, None, [[0, 1, None, None, None]], None, None),
                            (5, 1, None, [[0, 1, None, None, None]], None, None),
                            (6, 0, None, [[0, 0, None, None, None]], None, None),
                            (9, 1, None, [[0, 1, None, None, None]], None, None),
                            (10, 1, None, [[0, 1, None, None, None]], None, None),
                            (11, 1, None, [[0, 1, None, None, None]], None, None),
                            (12, 1, None, [[0, 1, None, None, None]], None, None),
                            (15, 1, None, [[0, 1, None, None, None]], None, None),
                            (16, 0, None, [[0, 0, None, None, None]], None, None)
                        ],
                        'totals': {
                            'files': 0,
                            'lines': 10,
                            'hits': 8,
                            'misses': 2,
                            'partials': 0,
                            'coverage': '80.00000',
                            'branches': 0,
                            'methods': 0,
                            'messages': 0,
                            'sessions': 0,
                            'complexity': 0,
                            'complexity_total': 0,
                            'diff': 0
                        }
                    }),
                    {
                        'name': 'tests/__init__.py',
                        'lines': [
                            (1, 1, None, [[0, 1, None, None, None]], None, None),
                            (4, 1, None, [[0, 1, None, None, None]], None, None),
                            (5, 0, None, [[0, 0, None, None, None]], None, None)
                        ],
                        'totals': {
                            'files': 0,
                            'lines': 3,
                            'hits': 2,
                            'misses': 1,
                            'partials': 0,
                            'coverage': '66.66667',
                            'branches': 0,
                            'methods': 0,
                            'messages': 0,
                            'sessions': 0,
                            'complexity': 0,
                            'complexity_total': 0,
                            'diff': 0
                        }
                    },
                    {
                        'name': 'tests/test_sample.py',
                        'lines': [
                            (1, 1, None, [[0, 1, None, None, None]], None, None),
                            (4, 1, None, [[0, 1, None, None, None]], None, None),
                            (5, 1, None, [[0, 1, None, None, None]], None, None),
                            (8, 1, None, [[0, 1, None, None, None]], None, None),
                            (9, 1, None, [[0, 1, None, None, None]], None, None),
                            (12, 1, None, [[0, 1, None, None, None]], None, None),
                            (13, 1, None, [[0, 1, None, None, None]], None, None)
                        ],
                        'totals': {
                            'files': 0,
                            'lines': 7,
                            'hits': 7,
                            'misses': 0,
                            'partials': 0,
                            'coverage': '100',
                            'branches': 0,
                            'methods': 0,
                            'messages': 0,
                            'sessions': 0,
                            'complexity': 0,
                            'complexity_total': 0,
                            'diff': 0
                        }
                    }
                ],
                'totals': {
                    'files': 3,
                    'lines': 20,
                    'hits': 17,
                    'misses': 3,
                    'partials': 0,
                    'coverage': '85.00000',
                    'branches': 0,
                    'methods': 0,
                    'messages': 0,
                    'sessions': 1,
                    'complexity': 0,
                    'complexity_total': 0,
                    'diff': [1, 2, 1, 1, 0, '50.00000', 0, 0, 0, 0, 0, 0, 0]
                }
            },
            'src': {
                'files': {
                    'awesome/__init__.py': {
                        'before': None,
                        'segments': [
                            {
                                'header': ['10', '3', '10', '7'],
                                'lines': [
                                    '     if n '
                                    '< 2:',
                                    '         '
                                    'return 1',
                                    '     '
                                    'return '
                                    'fib(n - 2) '
                                    '+ fib(n - '
                                    '1)',
                                    '+',
                                    '+',
                                    '+def '
                                    'coala(k):',
                                    '+    '
                                    'return k * '
                                    'k'
                                ]
                            }
                        ],
                        'stats': {'added': 4, 'removed': 0},
                        'type': 'modified'
                    },
                    'coverage.xml': {
                        'before': None,
                        'segments': [
                            {
                                'header': ['1', '5', '1', '5'],
                                'lines': [
                                    ' <?xml '
                                    'version="1.0" ?>',
                                    '-<coverage '
                                    'branch-rate="0" '
                                    'branches-covered="0" '
                                    'branches-valid="0" '
                                    'complexity="0" '
                                    'line-rate="0.8889" '
                                    'lines-covered="16" '
                                    'lines-valid="18" '
                                    'timestamp="1547083947227" '
                                    'version="4.5.1">',
                                    '+<coverage '
                                    'branch-rate="0" '
                                    'branches-covered="0" '
                                    'branches-valid="0" '
                                    'complexity="0" '
                                    'line-rate="0.8889" '
                                    'lines-covered="16" '
                                    'lines-valid="18" '
                                    'timestamp="1547084360935" '
                                    'version="4.5.1">',
                                    ' \t<!-- Generated '
                                    'by coverage.py: '
                                    'https://coverage.readthedocs.io '
                                    '-->',
                                    ' \t<!-- Based on '
                                    'https://raw.githubusercontent.com/cobertura/web/master/htdocs/xml/coverage-04.dtd '
                                    '-->',
                                    ' \t<sources>'
                                ]
                            }
                        ],
                        'stats': {'added': 1, 'removed': 1},
                        'type': 'modified'
                    }
                }
            },
        }
        assert expected_result['src'] == res['src']
        assert expected_result['report'] == res['report']
        assert expected_result == res
        mocked.assert_called_with(
            'abf6d4df662c47e32460020ab14abf9303581429'
        )
