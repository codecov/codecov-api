from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase
from shared.bundle_analysis import BundleAnalysisReport, BundleReport
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)


class MockBundleReport(BundleReport):
    def __init__(self):
        return

    def total_size(self):
        return 1234567


class MockBundleAnalysisReport(BundleAnalysisReport):
    def bundle_report(self, bundle_name: str):
        if bundle_name == "idk":
            return None
        return MockBundleReport()


class TestBundleBadgeHandler(APITestCase):
    def _get(self, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/graphs/bundle/{kwargs.get('bundle')}/badge.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def _get_branch(self, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/branch/{kwargs.get('branch')}/graphs/{kwargs.get('bundle')}/badge.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def test_invalid_extension(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "png",
                "bundle": "asdf",
            }
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"] == "File extension should be one of [ svg || txt ]"
        )

    def test_unknown_badge_incorrect_service(self):
        response = self._get(
            kwargs={
                "service": "gih",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_badge_incorrect_owner(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user1233",
                "repo_name": "repo",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_badge_incorrect_repo(self):
        gh_owner = OwnerFactory(service="github")
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_badge_private_repo_wrong_token(self):
        gh_owner = OwnerFactory(service="github")
        RepositoryFactory(
            author=gh_owner, active=True, private=True, name="repo1", image_token="asdf"
        )
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_badge_no_branch(self):
        gh_owner = OwnerFactory(service="github")
        RepositoryFactory(author=gh_owner, active=True, private=False, name="repo1")
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_badge_no_commit(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        branch = BranchFactory(name="main", repository=repo)
        repo.branch = branch
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    @patch("graphs.views.load_report")
    def test_unknown_badge_no_report(self, mock_load_report):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        branch = BranchFactory(name="main", repository=repo)
        repo.branch = branch
        commit = CommitFactory(
            repository=repo, commitid=repo.branch.head, branch="main"
        )
        branch.head = commit.commitid

        mock_load_report.return_value = None

        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    @patch("graphs.views.load_report")
    def test_unknown_badge_no_bundle(self, mock_load_report):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        branch = BranchFactory(name="main", repository=repo)
        repo.branch = branch
        commit = CommitFactory(
            repository=repo, commitid=repo.branch.head, branch="main"
        )
        branch.head = commit.commitid

        mock_load_report.return_value = MockBundleAnalysisReport()

        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "bundle": "idk",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="106" height="20">
    <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
        <stop offset="1" stop-opacity=".1" />
    </linearGradient>
    <mask id="CodecovBadgeMask106px">
        <rect width="106" height="20" rx="3" fill="#fff" />
    </mask>
    <g mask="url(#CodecovBadgeMask106px)">
        <path fill="#555" d="M0 0h47v20H0z" />
        <path fill="#2C2433" d="M47 0h59v20H47z" />
        <path fill="url(#CodecovBadgeGradient)" d="M0 0h106v20H0z" />
    </g>
    <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
        <text x="5" y="14">bundle</text>
        <text x="52" y="15" fill="#010101" fill-opacity=".3">unknown</text>
        <text x="52" y="14">unknown</text>
    </g>
</svg>
"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    @patch("graphs.views.load_report")
    def test_bundle_badge(self, mock_load_report):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        branch = BranchFactory(name="main", repository=repo)
        repo.branch = branch
        commit = CommitFactory(
            repository=repo, commitid=repo.branch.head, branch="main"
        )
        branch.head = commit.commitid

        mock_load_report.return_value = MockBundleAnalysisReport()

        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "bundle": "asdf",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="99" height="20">
            <linearGradient id="CodecovBadgeGradient" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                <stop offset="1" stop-opacity=".1" />
            </linearGradient>
            <mask id="CodecovBadgeMask99px">
                <rect width="99" height="20" rx="3" fill="#fff" />
            </mask>
            <g mask="url(#CodecovBadgeMask99px)">
                <path fill="#555" d="M0 0h47v20H0z" />
                <path fill="#2C2433" d="M47 0h52v20H47z" />
                <path fill="url(#CodecovBadgeGradient)" d="M0 0h99v20H0z" />
            </g>
            <g fill="#fff" text-anchor="left" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="5" y="15" fill="#010101" fill-opacity=".3">bundle</text>
                <text x="5" y="14">bundle</text>
                <text x="52" y="15" fill="#010101" fill-opacity=".3">1.23MB</text>
                <text x="52" y="14">1.23MB</text>
            </g>
        </svg>
"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    @patch("graphs.views.load_report")
    def test_bundle_badge_text(self, mock_load_report):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        branch = BranchFactory(name="main", repository=repo)
        repo.branch = branch
        commit = CommitFactory(
            repository=repo, commitid=repo.branch.head, branch="main"
        )
        branch.head = commit.commitid

        mock_load_report.return_value = MockBundleAnalysisReport()

        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "txt",
                "bundle": "asdf",
            }
        )
        expected_badge = "1.23MB"

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    @patch("graphs.views.load_report")
    def test_bundle_badge_unsupported_precision_defaults_to_2(self, mock_load_report):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        branch = BranchFactory(name="main", repository=repo)
        repo.branch = branch
        commit = CommitFactory(
            repository=repo, commitid=repo.branch.head, branch="main"
        )
        branch.head = commit.commitid

        mock_load_report.return_value = MockBundleAnalysisReport()

        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "txt",
                "bundle": "asdf",
            },
            data={"precision": "asdf"},
        )
        expected_badge = "1.23MB"

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge

    @patch("graphs.views.load_report")
    def test_bundle_badge_private_repo_correct_token(self, mock_load_report):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=True, name="repo1", image_token="asdf"
        )
        branch = BranchFactory(name="main", repository=repo)
        repo.branch = branch
        commit = CommitFactory(
            repository=repo, commitid=repo.branch.head, branch="main"
        )
        branch.head = commit.commitid

        mock_load_report.return_value = MockBundleAnalysisReport()

        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "txt",
                "bundle": "asdf",
            },
            data={"token": "asdf"},
        )
        expected_badge = "1.23MB"

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK
