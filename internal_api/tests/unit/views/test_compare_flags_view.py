import json

from django.test import override_settings

from internal_api.tests.unit.views.test_compare_file_view import build_commits_with_changes


class TestCompareFlagsView(object):

    @override_settings(DEBUG=True)
    def test_compare_flags___success(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head, change_commit = build_commits_with_changes(client=client)
        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{commit_head.commitid}/flags'
        print("request url: ", url)
        response = client.get(url)
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
