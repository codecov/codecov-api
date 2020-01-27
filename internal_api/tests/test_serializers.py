import asyncio
from pathlib import Path
from json import loads, dumps
import json
from mock import patch

from internal_api.commit.serializers import CommitSerializer, CommitWithSrcSerializer
from internal_api.owner.serializers import OwnerSerializer, OwnerDetailsSerializer
from core.tests.factories import RepositoryFactory, CommitFactory
from codecov_auth.tests.factories import OwnerFactory
from core.models import Commit
from archive.services import ArchiveService

from internal_api.tests.utils import TestUtils

current_file = Path(__file__)


class TestCommitSerializers(object):
    def test_serializer(self, mocker, db, codecov_vcr):
        repo = RepositoryFactory()
        parent_commit = CommitFactory(repository=repo)
        commit = CommitFactory(
            repository=repo,
            commitid='abf6d4df662c47e32460020ab14abf9303581429',
            parent_commit_id=parent_commit.commitid,
        )

        response = CommitSerializer(instance=commit).data

        expected_result = {
            'ci_passed': True,
            'author': {
                'service': commit.author.service,
                'active_repos': commit.author.active_repos,
                'username': commit.author.username,
                'email': commit.author.email,
                'name': commit.author.name,
                'stats': {'members': 2, 'repos': 1},
            },
            'message': commit.message,
            'commitid': 'abf6d4df662c47e32460020ab14abf9303581429',
            'repository': {
                'repoid': commit.repository.repoid,
                'name': 'example-python',
                'updatestamp': commit.repository.updatestamp.isoformat()[:-6] + 'Z'
            },
            'branch': 'master',
            'timestamp': commit.timestamp.isoformat()[:-6] + 'Z',
            'totals': commit.totals,
            'state': Commit.CommitStates.COMPLETE
        }

        response = loads(dumps(response))
        expected_result = loads(dumps(expected_result))
        assert expected_result == response


class TestCommitWithSrcSerializers(object):
    @patch('torngit.github.Github.get_commit_diff', TestUtils.get_mock_coro(json.load(open(current_file.parent / f'samples/get_commit_diff-response.json'))))
    def test_serializer(self, mocker, db, codecov_vcr):
        mocked = mocker.patch.object(ArchiveService, 'read_chunks')
        f = open(
            current_file.parent.parent.parent / 'archive/tests/samples' / 'chunks.txt',
            'r'
        )
        mocker.patch.object(ArchiveService, 'create_root_storage')
        mocked.return_value = f.read()

        repo = RepositoryFactory()
        parent_commit = CommitFactory(repository=repo)
        commit = CommitFactory(
            repository=repo,
            commitid='abf6d4df662c47e32460020ab14abf9303581429',
            parent_commit_id=parent_commit.commitid,
        )

        response = CommitWithSrcSerializer(instance=commit, context={'user': repo.author}).data

        expected_result = {
            'ci_passed': True,
            'author': {
                'service': commit.author.service,
                'active_repos': commit.author.active_repos,
                'username': commit.author.username,
                'email': commit.author.email,
                'name': commit.author.name,
                'stats': {'members': 2, 'repos': 1},
            },
            'message': commit.message,
            'commitid': 'abf6d4df662c47e32460020ab14abf9303581429',
            'repository': {
                'repoid': commit.repository.repoid,
                'name': 'example-python',
                'updatestamp': commit.repository.updatestamp.isoformat()[:-6] + 'Z'
            },
            'branch': 'master',
            'timestamp': commit.timestamp.isoformat()[:-6] + 'Z',
            'totals': commit.totals,
            'report': {
                'files': [
                    ({
                        'name': 'awesome/__init__.py',
                        'lines': [
                            (1, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (2, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (5, 1, None, [[0, 1, None, None, None], [1, 1, None, None, None]], None, None),
                            (6, 1, None, [[0, 0, None, None, None], [1, 0, None, None, None]], None, None),
                            (9, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (10, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (11, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (12, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (15, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (16, 0, None, [[0, 0, None, None, None], [1, 0, None, None, None]], None, None)
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
                            (1, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (4, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (5, 0, None, [[0, 0, None, None, None], [1, 0, None, None, None]], None, None)
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
                            (1, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (4, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (5, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (8, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (9, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                            (12, 1, None, [[0, 1, None, None, None], [1, 1, None, None, None]], None, None),
                            (13, 1, None, [[0, 1, None, None, None], [1, 1, None, None, None]], None, None)
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
                        'before': 'None',
                        'segments': [
                            {
                                'header': ['10', '3', '10', '7'],
                                'lines': [
                                    '     if n ',
                                    '< 2:',
                                    '         ',
                                    'return 1',
                                    '     ',
                                    'return ',
                                    'fib(n - 2) ',
                                    '+ fib(n - ',
                                    '1)',
                                    '+',
                                    '+',
                                    '+def ',
                                    'coala(k):',
                                    '+    ',
                                    'return k * ',
                                    'k',
                                ]
                            }
                        ],
                        'stats': {'added': 4, 'removed': 0},
                        'type': 'modified'
                    },
                    'coverage.xml': {
                        'before': 'None',
                        'segments': [
                            {
                                'header': ['1', '5', '1', '5'],
                                'lines': [
                                    ' <?xml ',
                                    'version="1.0" ?>',
                                    '-<coverage ',
                                    'branch-rate="0" ',
                                    'branches-covered="0" ',
                                    'branches-valid="0" ',
                                    'complexity="0" ',
                                    'line-rate="0.8889" ',
                                    'lines-covered="16" ',
                                    'lines-valid="18" ',
                                    'timestamp="1547083947227" ',
                                    'version="4.5.1">',
                                    '+<coverage ',
                                    'branch-rate="0" ',
                                    'branches-covered="0" ',
                                    'branches-valid="0" ',
                                    'complexity="0" ',
                                    'line-rate="0.8889" ',
                                    'lines-covered="16" ',
                                    'lines-valid="18" ',
                                    'timestamp="1547084360935" ',
                                    'version="4.5.1">',
                                    ' \t<!-- Generated ',
                                    'by coverage.py: ',
                                    'https://coverage.readthedocs.io ',
                                    '-->',
                                    ' \t<!-- Based on ',
                                    'https://raw.githubusercontent.com/cobertura/web/master/htdocs/xml/coverage-04.dtd ',
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

        response = loads(dumps(response))
        expected_result = loads(dumps(expected_result))

        assert expected_result == response
        mocked.assert_called_with('abf6d4df662c47e32460020ab14abf9303581429')


class TestOwnerSerializers(object):
    def test_serializer(self, mocker, db, codecov_vcr):
        owner = OwnerFactory()
        expected_result = {
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
            "email": owner.email,
            "stats": {
                "repos": 1,
                "members": 2,
            },
            "active_repos": None
        }

        response = OwnerSerializer(instance=owner).data
        assert expected_result == loads(dumps(response))

    def test_serializer_with_repo(self, mocker, db, codecov_vcr):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner, active=True)
        expected_result = {
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
            "email": owner.email,
            "stats": {
                "repos": 1,
                "members": 2,
            },
            "active_repos": [
                {
                    "repoid": repo.repoid,
                    "name": repo.name
                }
            ]
        }

        response = OwnerSerializer(instance=owner).data
        assert expected_result == loads(dumps(response))


class TestOwnerDetailsSerializers(object):
    def test_serializer_with_orgs(self, mocker, db, codecov_vcr):
        org1 = OwnerFactory(username='org1', email='org1@codecov.io')
        org2 = OwnerFactory(username='org2', email='org2@codecov.io')
        owner = OwnerFactory(organizations=[org1.ownerid, org2.ownerid])
        expected_result = {
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
            "email": owner.email,
            "stats": {
                "repos": 1,
                "members": 2
            },
            "active_repos": None,
            "orgs": [
                {
                    'active_repos': None,
                    'email': org1.email,
                    'name': org1.name,
                    'service': org1.service,
                    'stats': {'members': 2, 'repos': 1},
                    'username': org1.username
                },
                {
                    'active_repos': None,
                    'email': org2.email,
                    'name': org2.name,
                    'service': org2.service,
                    'stats': {'members': 2, 'repos': 1},
                    'username': org2.username
                }
            ],
            "avatar_url": "https://avatars0.githubusercontent.com/u/1234?v=3&s=50",
        }

        response = OwnerDetailsSerializer(instance=owner).data
        assert expected_result == loads(dumps(response))

    def test_serializer_without_orgs_and_stats(self, mocker, db, codecov_vcr):
        owner = OwnerFactory(cache=None)
        expected_result = {
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
            "email": owner.email,
            "stats": None,
            "active_repos": None,
            "orgs": [],
            "avatar_url": "https://avatars0.githubusercontent.com/u/1234?v=3&s=50",
        }

        response = OwnerDetailsSerializer(instance=owner).data
        assert expected_result == loads(dumps(response))
