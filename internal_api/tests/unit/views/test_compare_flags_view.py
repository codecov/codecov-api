import json

from django.test import override_settings

from internal_api.tests.unit.views.test_compare_file_view import build_commits_with_changes
from core.tests.factories import PullFactory

from unittest.mock import patch

from rest_framework.reverse import reverse


class TestCompareFlagsView(object):
    def _get_compare_flags(self, client, kwargs, query_params):
        return client.get(reverse('compare-flags', kwargs=kwargs), data=query_params)

    @override_settings(DEBUG=True)
    def test_compare_flags___success(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head, change_commit = build_commits_with_changes(client=client)

        response = self._get_compare_flags(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "base": commit_base.commitid,
                "head": commit_head.commitid
            }
        )

        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['results'] == [
            {
                "name": "adder",
                "base_report_totals": {
                    "files": 4,
                    "lines": 6,
                    "hits": 5,
                    "misses": 1,
                    "partials": 0,
                    "coverage": "83.33333",
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 3,
                    "complexity": 0,
                    "complexity_total": 0,
                    "diff": 0
                },
                "head_report_totals": {
                    "files": 5,
                    "lines": 8,
                    "hits": 7,
                    "misses": 1,
                    "partials": 0,
                    "coverage": "87.50000",
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 2,
                    "complexity": 0,
                    "complexity_total": 0,
                    "diff": 0
                },
                "diff_totals": {
                    "files": 1,
                    "lines": 2,
                    "hits": 1,
                    "misses": 1,
                    "partials": 0,
                    "coverage": "50.00000",
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "diff": 0
                }
            },
            {
                "name": "assumeflag",
                "base_report_totals": {
                    "files": 4,
                    "lines": 6,
                    "hits": 5,
                    "misses": 1,
                    "partials": 0,
                    "coverage": "83.33333",
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 3,
                    "complexity": 0,
                    "complexity_total": 0,
                    "diff": 0
                },
                "head_report_totals": {
                    "files": 5,
                    "lines": 8,
                    "hits": 7,
                    "misses": 1,
                    "partials": 0,
                    "coverage": "87.50000",
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 2,
                    "complexity": 0,
                    "complexity_total": 0,
                    "diff": 0
                },
                "diff_totals": {
                    "files": 1,
                    "lines": 2,
                    "hits": 1,
                    "misses": 1,
                    "partials": 0,
                    "coverage": "50.00000",
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "diff": 0
                }
            }
        ]

    @override_settings(DEBUG=True)
    def test_compare_flags_view_accepts_pullid_query_param(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head, change_commit = build_commits_with_changes(client=client)

        from archive.services import ArchiveService
        mocked_read_chunks = mocker.patch.object(ArchiveService, 'read_chunks')
        mocked_create_root_storage = mocker.patch.object(ArchiveService, 'create_root_storage')

        mocked_read_chunks.return_value = ""

        response = self._get_compare_flags(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "pullid": PullFactory(
                    base=commit_base,
                    head=commit_head,
                    pullid=2,
                    author=commit_head.author,
                    repository=commit_head.repository
                ).pullid
            }
        )

        assert response.status_code == 200
