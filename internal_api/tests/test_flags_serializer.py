from pathlib import Path
import json

from internal_api.compare.serializers import FlagComparisonSerializer
from core.tests.factories import CommitFactory, RepositoryFactory
from services.archive import ArchiveService
from services.comparison import Comparison

current_file = Path(__file__)


class TestFlagSerializers(object):

    def test_flag_serializer(self, mocker, db, codecov_vcr):
        head_commit_sha = '68946ef98daec68c7798459150982fc799c87d85'
        base_commit_sha = '00c7b4b49778b3c79427f9c4c13a8612a376ff19'
        mocked = mocker.patch.object(ArchiveService, 'read_chunks')
        head_f = open(
            current_file.parent / f'samples/{head_commit_sha}_chunks.txt',
            'r'
        )
        base_f = open(
            current_file.parent / f'samples/{base_commit_sha}_chunks.txt',
            'r'
        )
        mocker.patch.object(ArchiveService, 'create_root_storage')
        mocked.side_effect = lambda x: head_f.read() if x == head_commit_sha else base_f.read()
        repo = RepositoryFactory.create(
            author__unencrypted_oauth_token='testaaft3ituvli790m1yajovjv5eg0r4j0264iw',
            author__username='ThiagoCodecov',
            author__service='github'
        )
        base_commit = CommitFactory.create(
            message='test_report_serializer',
            commitid=base_commit_sha,
            repository=repo,
            totals={"C": 0, "M": 0, "N": 0, "b": 0, "c": "79.16667", "d": 0, "f": 3, "h": 19, "m": 5, "n": 24, "p": 0, "s": 2, "diff": None},
            report=json.load(open(current_file.parent / f'samples/{base_commit_sha}_report.json'))
        )
        commit = CommitFactory.create(
            message='test_report_serializer',
            commitid=head_commit_sha,
            repository=repo,
            totals={"C": 0, "M": 0, "N": 0, "b": 0, "c": "79.16667", "d": 0, "f": 3, "h": 19, "m": 5, "n": 24, "p": 0, "s": 2, "diff": [1, 0, 0, 0, 0, None, 0, 0, 0, 0, None, None, 0]},
            report=json.load(open(current_file.parent / f'samples/{head_commit_sha}_report.json'))
        )
        comparison = Comparison(base_commit, commit, user=repo.author)
        flag_comparison = comparison.flag_comparison('flagtwo')
        res = FlagComparisonSerializer(instance=flag_comparison, context={'user': repo.author}).data
        expected_result = {
            'name': 'flagtwo',
            'base_report_totals': {
                'branches': 0,
                'complexity': 0,
                'complexity_total': 0,
                'coverage': 79.17,
                'diff': 0,
                'files': 3,
                'hits': 19,
                'lines': 24,
                'messages': 0,
                'methods': 0,
                'misses': 5,
                'partials': 0,
                'sessions': 2
            },
            'diff_totals': {
                'branches': 0,
                'complexity': 0,
                'complexity_total': 0,
                'coverage': 0,
                'diff': 0,
                'files': 1,
                'hits': 0,
                'lines': 1,
                'messages': 0,
                'methods': 0,
                'misses': 1,
                'partials': 0,
                'sessions': 0
            },
            'head_report_totals': {
                'branches': 0,
                'complexity': 0,
                'complexity_total': 0,
                'coverage': 56,
                'diff': 0,
                'files': 3,
                'hits': 14,
                'lines': 25,
                'messages': 0,
                'methods': 0,
                'misses': 11,
                'partials': 0,
                'sessions': 2
            }
        }
        mocked.assert_called_with(
            head_commit_sha
        )
        mocked.assert_any_call(
            base_commit_sha
        )
        assert expected_result == res
        second_flag_comparison = comparison.flag_comparison('flagone')
        second_res = FlagComparisonSerializer(instance=second_flag_comparison, context={'user': repo.author}).data
        second_expected_result = {
            'name': 'flagone',
            'base_report_totals': {
                'branches': 0,
                'complexity': 0,
                'complexity_total': 0,
                'coverage': 79.17,
                'diff': 0,
                'files': 3,
                'hits': 19,
                'lines': 24,
                'messages': 0,
                'methods': 0,
                'misses': 5,
                'partials': 0,
                'sessions': 2
            },
            'diff_totals': {
                'branches': 0,
                'complexity': 0,
                'complexity_total': 0,
                'coverage': 100,
                'diff': 0,
                'files': 1,
                'hits': 1,
                'lines': 1,
                'messages': 0,
                'methods': 0,
                'misses': 0,
                'partials': 0,
                'sessions': 0
            },
            'head_report_totals': {
                'branches': 0,
                'complexity': 0,
                'complexity_total': 0,
                'coverage': 80,
                'diff': 0,
                'files': 3,
                'hits': 20,
                'lines': 25,
                'messages': 0,
                'methods': 0,
                'misses': 5,
                'partials': 0,
                'sessions': 2
            }
        }
        assert second_res['base_report_totals'] == second_expected_result['base_report_totals']
        assert second_res['diff_totals'] == second_expected_result['diff_totals']
        assert second_res['head_report_totals'] == second_expected_result['head_report_totals']
        assert second_res == second_expected_result
