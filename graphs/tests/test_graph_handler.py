from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    BranchFactory,
    CommitFactory,
    CommitWithReportFactory,
    PullFactory,
    RepositoryFactory,
)


@patch("services.archive.ArchiveService.read_chunks", lambda obj, _: "")
class TestGraphHandler(APITestCase):
    def _get(self, graph_type, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/graphs/{graph_type}.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def _get_branch(self, graph_type, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/branch/{kwargs.get('branch')}/graphs/{graph_type}.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def _get_commit(self, graph_type, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/commit/{kwargs.get('commit')}/graphs/{graph_type}.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def _get_pull(self, graph_type, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/pull/{kwargs.get('pull')}/graphs/{graph_type}.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def test_invalid_extension(self):
        response = self._get(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "json",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["detail"] == "File extension should be one of [ svg ]"

        response = self._get(
            "icicle",
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "json",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["detail"] == "File extension should be one of [ svg ]"

        response = self._get(
            "sunburst",
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "json",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["detail"] == "File extension should be one of [ svg ]"

        response = self._get(
            "commits",
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "txt",
            },
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["detail"] == "File extension should be one of [ svg ]"

    def test_tree_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitWithReportFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
        )

        expected_graph = """<svg baseProfile="full" width="300" height="300" viewBox="0 0 300 300" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <rect x="0" y="0" width="210.0" height="150.0" fill="#4c1" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/test_sample.py"><title>tests/test_sample.py</title></rect>
            <rect x="210.0" y="0" width="90.0" height="150.0" fill="#e05d44" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/__init__.py"><title>tests/__init__.py</title></rect>
            <rect x="0" y="150.0" width="300.0" height="150.0" fill="#efa41b" stroke="white" stroke-width="1" class=" tooltipped" data-content="awesome/__init__.py"><title>awesome/__init__.py</title></rect>
        </svg>"""

        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert expected_graph == graph
        assert response.status_code == status.HTTP_200_OK

    def test_icicle_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitWithReportFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            "icicle",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
        )

        expected_graph = """<svg baseProfile="full" width="750" height="150" viewBox="0 0 750 150" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <rect x="37.5" y="7.5" width="675.0" height="45.0" fill="#c0b01b" stroke="white" stroke-width="1" class=" tooltipped" data-content="/"><title>/</title></rect>
            <rect x="37.5" y="52.5" width="337.5" height="45.0" fill="#a3b114" stroke="white" stroke-width="1" class=" tooltipped" data-content="//tests"><title>//tests</title></rect>
            <rect x="37.5" y="97.5" width="101.25" height="45.0" fill="#e05d44" stroke="white" stroke-width="1" class=" tooltipped" data-content="//tests/__init__.py"><title>//tests/__init__.py</title></rect>
            <rect x="138.75" y="97.5" width="236.24999999999997" height="45.0" fill="#4c1" stroke="white" stroke-width="1" class=" tooltipped" data-content="//tests/test_sample.py"><title>//tests/test_sample.py</title></rect>
            <rect x="375.0" y="52.5" width="337.5" height="45.0" fill="#efa41b" stroke="white" stroke-width="1" class=" tooltipped" data-content="//awesome"><title>//awesome</title></rect>
            <rect x="375.0" y="97.5" width="337.5" height="45.0" fill="#efa41b" stroke="white" stroke-width="1" class=" tooltipped" data-content="//awesome/__init__.py"><title>//awesome/__init__.py</title></rect>
        </svg>"""

        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert expected_graph == graph
        assert response.status_code == status.HTTP_200_OK

    def test_sunburst_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitWithReportFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            "sunburst",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
        )

        expected_graph = """<svg baseProfile="full" width="300" height="300" viewBox="0 0 300 300" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <circle cx="150.0" cy="150.0" fill="#c0b01b" r="47.5" stroke="white" stroke-width="1" />
            <path d="M 150.0 197.5 L 150.0 245.0 A 95.0 95.0 0 0 0 150.0 55.0 L 150.0 102.5 A 47.5 47.5 0 0 1 150.0 197.5 z" fill="#a3b114" stroke="white" stroke-width="1" />
            <path d="M 150.0 245.0 L 150.0 292.5 A 142.5 142.5 0 0 0 265.28492169843 233.75939845167744 L 226.85661446562 205.83959896778495 A 95.0 95.0 0 0 1 150.0 245.0 z" fill="#e05d44" stroke="white" stroke-width="1" />
            <path d="M 226.85661446562 205.83959896778495 L 265.28492169843 233.75939845167744 A 142.5 142.5 0 0 0 150.00000000000003 7.5 L 150.0 55.0 A 95.0 95.0 0 0 1 226.85661446562 205.83959896778495 z" fill="#4c1" stroke="white" stroke-width="1" />
            <path d="M 150.0 102.5 L 150.0 55.0 A 95.0 95.0 0 0 0 149.99999999999997 245.0 L 150.0 197.5 A 47.5 47.5 0 0 1 150.0 102.5 z" fill="#efa41b" stroke="white" stroke-width="1" />
            <path d="M 150.0 55.0 L 150.00000000000003 7.5 A 142.5 142.5 0 0 0 149.99999999999997 292.5 L 149.99999999999997 245.0 A 95.0 95.0 0 0 1 150.0 55.0 z" fill="#efa41b" stroke="white" stroke-width="1" />
        </svg>"""

        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert expected_graph == graph
        assert response.status_code == status.HTTP_200_OK

    def test_unkown_owner(self):
        response = self._get(
            "sunburst",
            kwargs={
                "service": "gh",
                "owner_username": "gh_owner",
                "repo_name": "repo1",
                "ext": "svg",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Not found. Note: private repositories require ?token arguments"
        )

    def test_unkown_repo(self):
        gh_owner = OwnerFactory(service="github")
        response = self._get(
            "sunburst",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Not found. Note: private repositories require ?token arguments"
        )

    def test_private_repo_no_token(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
        )
        response = self._get(
            "sunburst",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"token": "123456"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Not found. Note: private repositories require ?token arguments"
        )

    def test_private_repo(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
        )
        commit = CommitWithReportFactory(repository=repo, author=gh_owner)

        response = self._get(
            "sunburst",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"token": "12345678"},
        )

        expected_graph = """<svg baseProfile="full" width="300" height="300" viewBox="0 0 300 300" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <circle cx="150.0" cy="150.0" fill="#c0b01b" r="47.5" stroke="white" stroke-width="1" />
            <path d="M 150.0 197.5 L 150.0 245.0 A 95.0 95.0 0 0 0 150.0 55.0 L 150.0 102.5 A 47.5 47.5 0 0 1 150.0 197.5 z" fill="#a3b114" stroke="white" stroke-width="1" />
            <path d="M 150.0 245.0 L 150.0 292.5 A 142.5 142.5 0 0 0 265.28492169843 233.75939845167744 L 226.85661446562 205.83959896778495 A 95.0 95.0 0 0 1 150.0 245.0 z" fill="#e05d44" stroke="white" stroke-width="1" />
            <path d="M 226.85661446562 205.83959896778495 L 265.28492169843 233.75939845167744 A 142.5 142.5 0 0 0 150.00000000000003 7.5 L 150.0 55.0 A 95.0 95.0 0 0 1 226.85661446562 205.83959896778495 z" fill="#4c1" stroke="white" stroke-width="1" />
            <path d="M 150.0 102.5 L 150.0 55.0 A 95.0 95.0 0 0 0 149.99999999999997 245.0 L 150.0 197.5 A 47.5 47.5 0 0 1 150.0 102.5 z" fill="#efa41b" stroke="white" stroke-width="1" />
            <path d="M 150.0 55.0 L 150.00000000000003 7.5 A 142.5 142.5 0 0 0 149.99999999999997 292.5 L 149.99999999999997 245.0 A 95.0 95.0 0 0 1 150.0 55.0 z" fill="#efa41b" stroke="white" stroke-width="1" />
        </svg>"""

        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert expected_graph == graph
        assert response.status_code == status.HTTP_200_OK

    def test_unkown_branch(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )

        response = self._get(
            "sunburst",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Not found. Note: private repositories require ?token arguments"
        )

    def test_branch_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
            branch="branch1",
        )
        commit = CommitWithReportFactory(repository=repo, author=gh_owner)
        commit_2_totals = {
            "C": 0,
            "M": 0,
            "N": 0,
            "b": 0,
            "c": "95.00000",
            "d": 0,
            "diff": [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
            "f": 3,
            "h": 17,
            "m": 3,
            "n": 20,
            "p": 0,
            "s": 1,
        }
        commit_2 = CommitWithReportFactory(
            repository=repo, author=gh_owner, totals=commit_2_totals
        )
        branch_2 = BranchFactory(
            repository=repo, name="branch1", head=commit_2.commitid
        )
        # test default precision
        response = self._get_branch(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "branch": "branch1",
            },
            data={"token": "12345678"},
        )
        expected_graph = """<svg baseProfile="full" width="300" height="300" viewBox="0 0 300 300" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <rect x="0" y="0" width="210.0" height="150.0" fill="#4c1" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/test_sample.py"><title>tests/test_sample.py</title></rect>
            <rect x="210.0" y="0" width="90.0" height="150.0" fill="#e05d44" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/__init__.py"><title>tests/__init__.py</title></rect>
            <rect x="0" y="150.0" width="300.0" height="150.0" fill="#efa41b" stroke="white" stroke-width="1" class=" tooltipped" data-content="awesome/__init__.py"><title>awesome/__init__.py</title></rect>
        </svg>"""
        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert expected_graph == graph
        assert response.status_code == status.HTTP_200_OK

    def test_commit_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
        )
        commit_1 = CommitWithReportFactory(repository=repo, author=gh_owner)

        # make sure commit 2 report is different than commit 1 and
        # assert that the expected graph below still pertains to commit_1
        commit_2 = CommitFactory(
            repository=repo,
            author=gh_owner,
            parent_commit_id=commit_1.commitid,
            _report={
                "files": {
                    "different/test_file.py": [
                        2,
                        [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
                        [[0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]],
                        [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
                    ],
                },
                "sessions": {
                    "0": {
                        "N": None,
                        "a": "v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
                        "c": None,
                        "d": 1547084427,
                        "e": None,
                        "f": ["unittests"],
                        "j": None,
                        "n": None,
                        "p": None,
                        "t": [3, 20, 17, 3, 0, "85.00000", 0, 0, 0, 0, 0, 0, 0],
                        "": None,
                    }
                },
            },
        )

        response = self._get_commit(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "commit": commit_1.commitid,
            },
            data={"token": "12345678"},
        )
        expected_graph = """<svg baseProfile="full" width="300" height="300" viewBox="0 0 300 300" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <rect x="0" y="0" width="210.0" height="150.0" fill="#4c1" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/test_sample.py"><title>tests/test_sample.py</title></rect>
            <rect x="210.0" y="0" width="90.0" height="150.0" fill="#e05d44" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/__init__.py"><title>tests/__init__.py</title></rect>
            <rect x="0" y="150.0" width="300.0" height="150.0" fill="#efa41b" stroke="white" stroke-width="1" class=" tooltipped" data-content="awesome/__init__.py"><title>awesome/__init__.py</title></rect>
        </svg>"""
        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert expected_graph == graph
        assert response.status_code == status.HTTP_200_OK

    def test_pull_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
            branch="branch1",
        )
        pull = PullFactory(
            pullid=10,
            repository_id=repo.repoid,
            _flare=[
                {
                    "name": "",
                    "color": "#e05d44",
                    "lines": 14,
                    "_class": None,
                    "children": [
                        {
                            "name": "tests.py",
                            "color": "#baaf1b",
                            "lines": 7,
                            "_class": None,
                            "coverage": "85.71429",
                        }
                    ],
                }
            ],
        )
        # test default precision
        response = self._get_pull(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "pull": 10,
            },
            data={"token": "12345678"},
        )
        expected_graph = """<svg baseProfile="full" width="300" height="300" viewBox="0 0 300 300" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <rect x="0" y="0" width="300.0" height="300.0" fill="#baaf1b" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests.py"><title>tests.py</title></rect>
        </svg>"""
        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert expected_graph == graph
        assert response.status_code == status.HTTP_200_OK

    def test_no_pull_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
            branch="branch1",
        )
        # test default precision
        response = self._get_pull(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "pull": 10,
            },
            data={"token": "12345678"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Not found. Note: private repositories require ?token arguments"
        )

    def test_pull_no_flare_graph(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
            branch="master",
        )
        commit = CommitWithReportFactory(repository=repo, author=gh_owner)
        pull = PullFactory(pullid=10, repository_id=repo.repoid, _flare=None)

        # test default precision
        response = self._get_pull(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "pull": 10,
            },
            data={"token": "12345678"},
        )
        expected_graph = """<svg baseProfile="full" width="300" height="300" viewBox="0 0 300 300" version="1.1"
            xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events"
            xmlns:xlink="http://www.w3.org/1999/xlink">

            <style>rect.s{mask:url(#mask);}</style>
            <defs>
            <pattern id="white" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="2" height="2" transform="translate(0,0)" fill="white"></rect>
            </pattern>
            <mask id="mask">
                <rect x="0" y="0" width="100%" height="100%" fill="url(#white)"></rect>
            </mask>
            </defs>

            <rect x="0" y="0" width="210.0" height="150.0" fill="#4c1" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/test_sample.py"><title>tests/test_sample.py</title></rect>
            <rect x="210.0" y="0" width="90.0" height="150.0" fill="#e05d44" stroke="white" stroke-width="1" class=" tooltipped" data-content="tests/__init__.py"><title>tests/__init__.py</title></rect>
            <rect x="0" y="150.0" width="300.0" height="150.0" fill="#efa41b" stroke="white" stroke-width="1" class=" tooltipped" data-content="awesome/__init__.py"><title>awesome/__init__.py</title></rect>
        </svg>"""
        graph = response.content.decode("utf-8")
        graph = [line.strip() for line in graph.split("\n")]
        expected_graph = [line.strip() for line in expected_graph.split("\n")]
        assert response.status_code == status.HTTP_200_OK
        assert expected_graph == graph

    def test_pull_no_repo_graph(self):
        gh_owner = OwnerFactory(service="github")

        # test default precision
        response = self._get_pull(
            "tree",
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "pull": 10,
            },
            data={"token": "12345678"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Not found. Note: private repositories require ?token arguments"
        )
