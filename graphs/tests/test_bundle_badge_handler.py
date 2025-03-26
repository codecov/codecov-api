from unittest.mock import patch, PropertyMock

from rest_framework import status
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from services.bundle_analysis import load_report


class TestBundleBadgeHandler(APITestCase):
    def _get(self, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/graphs/bundle/{kwargs.get('bundle')}/badge.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def _get_branch(self, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/branch/{kwargs.get('branch')}/graphs/bundle/{kwargs.get('bundle')}/badge.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def test_invalid_precision(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "bundle": "main",
                "ext": "svg",
            },
            data={"precision": "3"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Bundle size precision should be one of [ 0 || 1 || 2 ]"
        )

    def test_invalid_extension(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "bundle": "main",
                "ext": "png",
            }
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"] == "File extension should be one of [ svg || txt ]"
        )

    def test_unknown_bundle_badge_incorrect_service(self):
        response = self._get(
            kwargs={
                "service": "gih",
                "owner_username": "user",
                "repo_name": "repo",
                "bundle": "main",
                "ext": "svg",
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

    def test_unknown_bundle_badge_incorrect_owner(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user1233",
                "repo_name": "repo",
                "bundle": "main",
                "ext": "svg",
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

    def test_unknown_bundle_badge_incorrect_repo(self):
        gh_owner = OwnerFactory(service="github")
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo",
                "bundle": "main",
                "ext": "svg",
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

    def test_unknown_bundle_badge_no_branch(self):
        gh_owner = OwnerFactory(service="github")
        RepositoryFactory(author=gh_owner, active=True, private=False, name="repo1")
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "bundle": "main",
                "ext": "svg",
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

    def test_unknown_bundle_badge_no_commit(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        BranchFactory(repository=repo, name="master")
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "bundle": "main",
                "ext": "svg",
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

    @patch("services.bundle_analysis.load_report")
    def test_text_badge(self, mock_load_report):
        class MockBundle:
            def total_size(self):
                return 1500000

        class MockBundleReport:
            def bundle_report(self, name):
                if name == "main":
                    return MockBundle()
                return None

        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitFactory(repository=repo, author=gh_owner)
        mock_load_report.return_value = MockBundleReport()

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "bundle": "main",
                "ext": "txt",
            }
        )

        badge = response.content.decode("utf-8")
        assert badge == "1.5MB"
        assert response.status_code == status.HTTP_200_OK

        # test precision = 1
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "bundle": "main",
                "ext": "txt",
            },
            data={"precision": "1"},
        )

        badge = response.content.decode("utf-8")
        assert badge == "1.5MB"
        assert response.status_code == status.HTTP_200_OK

        # test precision = 0
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "bundle": "main",
                "ext": "txt",
            },
            data={"precision": "0"},
        )

        badge = response.content.decode("utf-8")
        assert badge == "2MB"
        assert response.status_code == status.HTTP_200_OK

    @patch("services.bundle_analysis.load_report")
    def test_svg_badge(self, mock_load_report):
        class MockBundle:
            def total_size(self):
                return 1500000

        class MockBundleReport:
            def bundle_report(self, name):
                if name == "main":
                    return MockBundle()
                return None

        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitFactory(repository=repo, author=gh_owner)
        mock_load_report.return_value = MockBundleReport()

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "bundle": "main",
                "ext": "svg",
            }
        )

        badge = response.content.decode("utf-8")
        assert "bundle" in badge
        assert "1.5MB" in badge
        assert response.status_code == status.HTTP_200_OK