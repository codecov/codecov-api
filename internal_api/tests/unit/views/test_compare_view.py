import json
import pytest
from unittest.mock import patch

from django.test import override_settings

from rest_framework import status
from rest_framework.reverse import reverse

from services.archive import SerializableReport
from internal_api.commit.serializers import ReportSerializer
from covreports.reports.resources import ReportFile
from services.archive import ArchiveService
from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from services.comparison import Comparison
from core.tests.factories import (
    RepositoryFactory,
    CommitFactory,
    BranchFactory,
    PullFactory,
)

def build_commits(client):
    """
        build commits in mock_db that are based on a real git commit for using VCR
    :param user:
    :param client:
    :return: repo, commit_base, commit_head
    """
    repo = RepositoryFactory.create(
        author__unencrypted_oauth_token='testqmit3okrgutcoyzscveipor3toi3nsmb927v',
        author__username='ThiagoCodecov'
    )
    parent_commit = CommitFactory.create(
        message='test_compare_parent',
        commitid='c5b6730',
        repository=repo,
    )
    commit_base = CommitFactory.create(
        message='test_compare_commits_base',
        commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
    )
    commit_head = CommitFactory.create(
        message='test_compare_commits_head',
        commitid='abf6d4df662c47e32460020ab14abf9303581429',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
    )
    client.force_login(user=repo.author)
    return repo, commit_base, commit_head


class TestCompareCommitsView(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='Codecov')
        self.user = OwnerFactory(
            username='codecov-user',
            email='codecov-user@codecov.io',
            organizations=[org.ownerid]
        )
        self.repo, self.commit_base, self.commit_head = build_commits(self.client)
        self.commit_base_totals_serialized = {
            'files': self.commit_base.totals['f'],
            'lines': self.commit_base.totals['n'],
            'hits': self.commit_base.totals['h'],
            'misses': self.commit_base.totals['m'],
            'partials': self.commit_base.totals['p'],
            'coverage': round(float(self.commit_base.totals['c']), 2),
            'branches': self.commit_base.totals['b'],
            'methods': self.commit_base.totals['d'],
            'sessions': self.commit_base.totals['s'],
            'diffCoverage': round(float(self.commit_base.totals['diff'][5]), 2) ,
            'complexity': self.commit_base.totals['C'],
            'complexity_total': self.commit_base.totals['N'],
        }
        self.commit_head_totals_serialized = {
            'files': self.commit_head.totals['f'],
            'lines': self.commit_head.totals['n'],
            'hits': self.commit_head.totals['h'],
            'misses': self.commit_head.totals['m'],
            'partials': self.commit_head.totals['p'],
            'coverage': round(float(self.commit_head.totals['c']), 2),
            'branches': self.commit_head.totals['b'],
            'methods': self.commit_head.totals['d'],
            'sessions': self.commit_head.totals['s'],
            'diffCoverage': round(float(self.commit_head.totals['diff'][5]), 2),
            'complexity': self.commit_head.totals['C'],
            'complexity_total': self.commit_head.totals['N'],    
        }

    def _get_commits_comparison(self, kwargs, query_params):
        return self.client.get(reverse('compare-commits', kwargs=kwargs), data=query_params)

    def _configure_mocked_comparison_with_commits(self, mock):
         mock.return_value = {
            "commits": [ 
                {
                    'commitid': self.commit_base.commitid,
                    'message': self.commit_base.message,
                    'timestamp': '2019-03-31T02:28:02Z',
                    'author': {
                        'id': self.repo.author.ownerid,
                        'username': self.repo.author.username,
                        'name': self.repo.author.name,
                        'email': self.repo.author.email
                    }
                },
                {
                    'commitid': self.commit_head.commitid,
                    'message': self.commit_head.message,
                    'timestamp': '2019-03-31T07:23:19Z',
                    'author': {
                        'id': self.repo.author.ownerid,
                        'username': self.repo.author.username,
                        'name': self.repo.author.name,
                        'email': self.repo.author.email
                    }
                }
            ]
        }

    def test_compare_commits_bad_commit(self):
        bad_commitid = "9193232a8fe3429496123ba82b5fed2583d1b5eb"
        response = self._get_commits_comparison(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "base": self.commit_base.commitid,
                "head": bad_commitid
            }
        )
        assert response.status_code == 404

    def test_compare_commits_bad_branch(self):
        bad_branch = "bad-branch"
        branch_base = BranchFactory.create(
            head=self.commit_base,
            repository=self.repo
        )
        response = self._get_commits_comparison(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "base": branch_base.name,
                "head": bad_branch
            }
        )
        assert response.status_code == 404

    @patch('services.comparison.Comparison._calculate_git_comparison')
    def test_compare_commits_view_with_branchname(self, mocked_comparison):
        self._configure_mocked_comparison_with_commits(mocked_comparison)
        branch_base = BranchFactory.create(head=self.commit_base.commitid, repository=self.commit_base.repository)
        branch_head = BranchFactory.create(head=self.commit_head.commitid, repository=self.commit_head.repository)

        response = self._get_commits_comparison(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "base": branch_base.name,
                "head": branch_head.name
            }
        )

        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['git_commits'] == mocked_comparison.return_value["commits"]
        assert content['commit_uploads'][0]['commitid'] == self.commit_head.commitid
        assert content['commit_uploads'][0]['totals'] == self.commit_head_totals_serialized
        assert content['commit_uploads'][1]['commitid'] == self.commit_base.commitid
        assert content['commit_uploads'][1]['totals'] == self.commit_base_totals_serialized

    @patch('services.comparison.Comparison._calculate_git_comparison')
    def test_compare_commits_view_with_commitid(self, mocked_comparison):
        self._configure_mocked_comparison_with_commits(mocked_comparison)
        response = self._get_commits_comparison(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "base": self.commit_base.commitid,
                "head": self.commit_head.commitid
            }
        )

        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['git_commits'] == mocked_comparison.return_value["commits"]
        assert content['commit_uploads'][0]['commitid'] == self.commit_head.commitid
        assert content['commit_uploads'][0]['totals'] == self.commit_head_totals_serialized
        assert content['commit_uploads'][1]['commitid'] == self.commit_base.commitid
        assert content['commit_uploads'][1]['totals'] == self.commit_base_totals_serialized

    @patch('services.comparison.Comparison._calculate_git_comparison')
    def test_compare_commits_view_with_pullid(self, mocked_comparison):
        self._configure_mocked_comparison_with_commits(mocked_comparison)
        pull = PullFactory(
            pullid=2,
            repository=self.repo,
            author=self.repo.author,
            base=self.commit_base.commitid,
            head=self.commit_head.commitid
        )

        response = self._get_commits_comparison(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "pullid": pull.pullid
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        assert response.data['git_commits'] == mocked_comparison.return_value["commits"]
        assert response.data['commit_uploads'][0]['commitid'] == self.commit_head.commitid
        assert response.data['commit_uploads'][0]['totals'] == self.commit_head_totals_serialized
        assert response.data['commit_uploads'][1]['commitid'] == self.commit_base.commitid
        assert response.data['commit_uploads'][1]['totals'] == self.commit_base_totals_serialized


@patch('services.archive.ArchiveService.create_root_storage')
@patch('services.archive.ArchiveService.read_chunks')
@patch('services.comparison.Comparison._calculate_git_comparison')
class TestCompareDetailsView(InternalAPITest):
    def _get_compare_details(self, kwargs={}, query_params={}):
        if not kwargs:
            kwargs = {"orgName": self.repo.author.username, "repoName": self.repo.name}
        if not query_params:
            query_params = {"base": self.commit_base.commitid, "head": self.commit_head.commitid}
        return self.client.get(reverse('compare-details', kwargs=kwargs), data=query_params)

    def setUp(self):
        self.repo, self.commit_base, self.commit_head = build_commits(client=self.client)

    def test_details_returns_200_on_success(self, mocked_comparison, mocked_read_chunks, *_):
        mocked_comparison.return_value = {"commits": []}
        mocked_read_chunks.return_value = ''
        response = self._get_compare_details()
        assert response.status_code == status.HTTP_200_OK

    def test_details_returns_relevant_fields_on_success(self, mocked_comparison, mocked_read_chunks, *_):
        mocked_comparison.return_value = {"commits": []}
        mocked_read_chunks.return_value = ''
        response = self._get_compare_details()
        assert response.status_code == status.HTTP_200_OK
        for field in ('head_commit', 'base_commit', 'head_report', 'base_report', 'git_commits'):
            assert field in response.data

    def test_details_accepts_pullid_query_param(self, mocked_comparison, mocked_read_chunks, *_):
        mocked_comparison.return_value = {"commits": []}
        mocked_read_chunks.return_value = ''
        response = self._get_compare_details(
            query_params={
                "pullid": PullFactory(
                    base=self.commit_base.commitid,
                    head=self.commit_head.commitid,
                    pullid=2,
                    author=self.commit_head.author,
                    repository=self.repo
                ).pullid
            }
        )
        assert response.status_code == status.HTTP_200_OK

    def test_details_return_with_mock_data(self, mocked_comparison, mocked_read_chunks, *args):
        mocked_comparison.return_value = {
            "commits": [
                {
                    'commitid': self.commit_base.commitid,
                    'message': self.commit_base.message,
                    'timestamp': '2019-03-31T02:28:02Z',
                    'author': {
                        'id': self.repo.author.ownerid,
                        'username': self.repo.author.username,
                        'name': self.repo.author.name,
                        'email': self.repo.author.email
                    }
                },
                {
                    'commitid': 'e8d9ce1a4c54a443607a2dd14cdeefc4dca4fde8',
                    'message': 'Some commit that doesnt have an upload',
                    'timestamp': '2019-03-31T04:28:02Z',
                    'author': {
                        'id': self.repo.author.ownerid,
                        'username': self.repo.author.username,
                        'name': self.repo.author.name,
                        'email': self.repo.author.email
                    }
                },
                {
                    'commitid': self.commit_head.commitid,
                    'message': self.commit_head.message,
                    'timestamp': '2019-03-31T07:23:19Z',
                    'author': {
                        'id': self.repo.author.ownerid,
                        'username': self.repo.author.username,
                        'name': self.repo.author.name,
                        'email': self.repo.author.email
                    }
                }
            ]
        }

        mocked_read_chunks.return_value = """{}
[1, null, [[0, 1], [1, 0]]]


[1, null, [[0, 1], [1, 0]]]
[0, null, [[0, 0], [1, 0]]]
<<<<< end_of_chunk >>>>>
{}
[1, null, [[0, 1], [1, 0]]]


[1, null, [[0, 1], [1, 0]]]
[1, null, [[0, 1], [1, 0]]]


[1, null, [[0, 1], [1, 0]]]
[1, null, [[0, 1], [1, 0]]]


[1, null, [[0, 1], [1, 1]]]
[1, null, [[0, 1], [1, 1]]]
<<<<< end_of_chunk >>>>>
{}
[1, null, [[0, 1], [1, 0]]]
[1, null, [[0, 1], [1, 0]]]


[1, null, [[0, 1], [1, 1]]]
[1, null, [[0, 0], [1, 0]]]


[1, null, [[0, 1], [1, 0]]]
[1, null, [[0, 1], [1, 0]]]
[1, null, [[0, 1], [1, 0]]]
[1, null, [[0, 1], [1, 0]]]


[1, null, [[0, 1], [1, 0]]]
[0, null, [[0, 0], [1, 0]]]"""

        ## dump to string, then read back as JSON to get rid of nested ordered dicts
        expected_serialized_report = json.loads(json.dumps(ReportSerializer(
            SerializableReport(
                chunks=mocked_read_chunks.return_value,
                files=CommitFactory.report["files"],
                sessions=CommitFactory.report['sessions'],
                totals=CommitFactory.totals
            )
        ).data))

        response = self._get_compare_details()
        content = json.loads(response.content.decode())
        assert response.status_code == status.HTTP_200_OK
        assert content["head_commit"] == self.commit_head.commitid
        assert content["base_commit"] == self.commit_base.commitid
        assert content["head_report"]["totals"] == expected_serialized_report["totals"]
        assert content["base_report"]["totals"] == expected_serialized_report["totals"]

        # loop through the files in the expected serialized report --
        # can't do equality test because files appear in a list of nondeterministic order,
        # because they are stored as a dict.
        for file_data in expected_serialized_report["files"]:
            # If an equivilant object exists in the head report (or base for second assert)
            # this condition qill evaluate to True. If not, the list will be empty, which
            # evaluates to False.
            assert [f for f in content["head_report"]["files"] if f == file_data]
            assert [f for f in content["base_report"]["files"] if f == file_data]

        assert content["git_commits"] == mocked_comparison.return_value["commits"]


@patch('services.archive.ArchiveService.create_root_storage')
@patch('services.archive.ArchiveService.read_chunks', lambda obj, sha: '')
@patch('services.comparison.Comparison._calculate_git_comparison')
class TestCompareSingleFileDiffView(InternalAPITest):
    def _get_single_file_diff(self, kwargs, query_params):
        return self.client.get(reverse('compare-diff-file', kwargs=kwargs), data=query_params)

    def setUp(self):
        self.repo = RepositoryFactory()
        self.commit_base = CommitFactory(repository=self.repo)
        self.commit_head = CommitFactory(repository=self.repo)

        self.client.force_login(user=self.repo.author)

    def test_returns_diff_for_file_name_on_success(self, mocked_comparison, *args):
        tracked_file = "awesome/__init__.py"
        mocked_comparison.return_value = {"diff": {"files": {tracked_file: tracked_file + "_data"}}}

        response = self._get_single_file_diff(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name,
                "file_path": tracked_file
            },
            query_params={
                "head": self.commit_head.commitid,
                "base": self.commit_base.commitid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['src_diff'] == mocked_comparison.return_value["diff"]["files"][tracked_file]
        assert 'base_coverage' in response.data
        assert 'head_coverage' in response.data

    def test_returns_404_if_file_name_not_in_diff(self, mocked_comparison, *args):
        file_not_in_diff = "not_found.py"
        mocked_comparison.return_value = {"diff": {"files": {"hello.py": True}}}

        response = self._get_single_file_diff(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name,
                "file_path": file_not_in_diff
            },
            query_params={
                "head": self.commit_head.commitid,
                "base": self.commit_base.commitid
            }
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@patch('services.archive.ArchiveService.create_root_storage')
@patch('services.archive.ArchiveService.read_chunks', lambda obj, sha: '')
@patch('services.comparison.Comparison._calculate_git_comparison')
class TestCompareFullSrcView(InternalAPITest):
    def _get_compare_src(self, kwargs, query_params):
        return self.client.get(reverse('compare-src-full', kwargs=kwargs), data=query_params)

    def _configure_comparison_mock_with_commit_factory_report(self, mock):
        mock.return_value = {
            "diff": {"files": {
                file_name: {"segments": True} for file_name, _ in CommitFactory.report["files"].items()
            }},
            "commits": []
        }

    def _configure_file_reports_with_commit_factory_report(self, mock):
        mock.return_value = [
            ReportFile(file_name) for file_name, _ in CommitFactory.report["files"].items()
        ]

    def setUp(self):
        self.repo = RepositoryFactory()
        self.commit_base = CommitFactory(repository=self.repo)
        self.commit_head = CommitFactory(repository=self.repo)
        self.commit_base_no_report = CommitFactory(repository=self.repo, report=None)
        self.client.force_login(user=self.repo.author)

    def test_returns_calculated_diff_data_with_commit_refs(self, mocked_comparison, *_):
        self._configure_comparison_mock_with_commit_factory_report(mocked_comparison)
        response = self._get_compare_src(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "base": self.commit_base.commitid,
                "head": self.commit_head.commitid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["tracked_files"] == mocked_comparison.return_value["diff"]["files"]
        assert response.data["untracked_files"] == []

    def test_accepts_pullid_query_param(self, mocked_comparison, *_):
        self._configure_comparison_mock_with_commit_factory_report(mocked_comparison)
        response = self._get_compare_src(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "pullid": PullFactory(
                    base=self.commit_base.commitid,
                    head=self.commit_head.commitid,
                    pullid=2,
                    author=self.commit_head.author,
                    repository=self.commit_head.repository
                ).pullid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["tracked_files"] == mocked_comparison.return_value["diff"]["files"]
        assert response.data["untracked_files"] == []

    @patch('services.archive.SerializableReport.file_reports')
    def test_tracked_files_omits_line_data_after_first_five(self, mocked_head_file_reports, mocked_comparison, *args):
        self._configure_comparison_mock_with_commit_factory_report(mocked_comparison)
        self._configure_file_reports_with_commit_factory_report(mocked_head_file_reports)

        # Add a 3 more tracked files to the report and diff (so total > 5)
        for i in range(3):
            new_file_name = f"newfile{i}.py"
            mocked_head_file_reports.return_value.append(ReportFile(new_file_name))
            mocked_comparison.return_value["diff"]["files"][new_file_name] = {"segments": True}

        assert len(mocked_head_file_reports.return_value) > 5
        assert len(mocked_comparison.return_value["diff"]["files"]) > 5

        response = self._get_compare_src(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "head": self.commit_head.commitid,
                "base": self.commit_base.commitid
            }
        )

        # there should be exactly five files with a non-empty list for "lines"
        files_with_lines = 0
        for _, diff_data in response.data["tracked_files"].items():
            if diff_data["segments"] is not None:
                files_with_lines += 1

        assert files_with_lines == 5

    @patch('services.archive.SerializableReport.file_reports')
    def test_diff_without_segments_doesnt_crash(self, mocked_head_file_reports, mocked_comparison, *args):
        self._configure_comparison_mock_with_commit_factory_report(mocked_comparison)
        self._configure_file_reports_with_commit_factory_report(mocked_head_file_reports)

        # Some extra configuration for head file reports mock
        mocked_head_file_reports.return_value = [
            ReportFile(file_name) for file_name, _ in CommitFactory.report["files"].items()
        ]

        # Delete segments from this file's data -- case of no src data
        del mocked_comparison.return_value["diff"]["files"]["awesome/__init__.py"]["segments"]

        response = self._get_compare_src(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "head": self.commit_head.commitid,
                "base": self.commit_base.commitid
            }
        )

    @patch('services.archive.SerializableReport.file_reports')
    def test_correctly_sorts_tracked_and_untracked_files(self, mocked_head_file_reports, mocked_comparison, *args):
        self._configure_comparison_mock_with_commit_factory_report(mocked_comparison)
        self._configure_file_reports_with_commit_factory_report(mocked_head_file_reports)

        # Put in a file that is untracked -- not in report files
        made_up_file = "madeup.py"
        mocked_comparison.return_value["diff"]["files"].update({made_up_file: {'segments': None}})

        response = self._get_compare_src(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "head": self.commit_head.commitid,
                "base": self.commit_base.commitid
            }
        )

        assert "tracked_files" in response.data
        for file_name, _ in mocked_comparison.return_value["diff"]["files"].items():
            if file_name == made_up_file:
                continue
            assert file_name in response.data["tracked_files"]

        assert "untracked_files" in response.data
        for file_name, _ in mocked_comparison.return_value["diff"]["files"].items():
            if file_name != made_up_file:
                continue
            assert file_name in response.data["untracked_files"]

    def test_missing_base_report(self, mocked_comparison, *_):
        self._configure_comparison_mock_with_commit_factory_report(mocked_comparison)
        expected_data = {
            'tracked_files': {
                'awesome/__init__.py': {
                    'segments': True},
                    'tests/__init__.py': {
                        'segments': True
                    },
                    'tests/test_sample.py': {
                        'segments': True
                    }
                },
            'untracked_files': []
        }
        response = self._get_compare_src(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "head": self.commit_head.commitid,
                "base": self.commit_base_no_report.commitid
            }
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected_data
