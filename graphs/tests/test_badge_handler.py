from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory


class TestBadgeHandler(APITestCase):
    def _get(self, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/graphs/badge.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def _get_branch(self, kwargs={}, data={}):
        path = f"/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/branch/{kwargs.get('branch')}/graphs/badge.{kwargs.get('ext')}"
        return self.client.get(path, data=data)

    def test_invalid_precision(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "svg",
            },
            data={"precision": "3"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"]
            == "Coverage precision should be one of [ 0 || 1 || 2 ]"
        )

    def test_invalid_extension(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "png",
            }
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            response.data["detail"] == "File extension should be one of [ svg || txt ]"
        )

    def test_unknown_bagde_incorrect_service(self):
        response = self._get(
            kwargs={
                "service": "gih",
                "owner_username": "user",
                "repo_name": "repo",
                "ext": "svg",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_bagde_incorrect_owner(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "user1233",
                "repo_name": "repo",
                "ext": "svg",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_bagde_incorrect_repo(self):
        gh_owner = OwnerFactory(service="github")
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo",
                "ext": "svg",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_bagde_no_branch(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_bagde_no_commit(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        branch = BranchFactory(repository=repo, name="master")
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_bagde_no_totals(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitFactory(repository=repo, author=gh_owner, totals=None)
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_text_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "txt",
            }
        )

        badge = response.content.decode("utf-8")
        assert badge == "85"
        assert response.status_code == status.HTTP_200_OK

        # test precision = 1
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "txt",
            },
            data={"precision": "1"},
        )

        badge = response.content.decode("utf-8")
        assert badge == "85.0"
        assert response.status_code == status.HTTP_200_OK

        # test precision = 1
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "txt",
            },
            data={"precision": "2"},
        )

        badge = response.content.decode("utf-8")
        assert badge == "85.00"
        assert response.status_code == status.HTTP_200_OK

    def test_svg_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        commit = CommitFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            }
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="112" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#c0b01b" d="M76 0h36v20H76z" />
                    <path fill="url(#b)" d="M0 0h112v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="93" y="15" fill="#010101" fill-opacity=".3">85%</text>
                    <text x="93" y="14">85%</text>
                </g>
                <svg viewBox="120 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

        # test precision = 1
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"precision": "1"},
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="122" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="122" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#c0b01b" d="M76 0h46v20H76z" />
                    <path fill="url(#b)" d="M0 0h122v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="98" y="15" fill="#010101" fill-opacity=".3">85.0%</text>
                    <text x="98" y="14">85.0%</text>
                </g>
                <svg viewBox="140 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert response.status_code == status.HTTP_200_OK

        # test precision = 1
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"precision": "2"},
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="132" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="132" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#c0b01b" d="M76 0h56v20H76z" />
                    <path fill="url(#b)" d="M0 0h132v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="103" y="15" fill="#010101" fill-opacity=".3">85.00%</text>
                    <text x="103" y="14">85.00%</text>
                </g>
                <svg viewBox="156 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert response.status_code == status.HTTP_200_OK

    def test_private_badge_no_token(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
        )
        commit = CommitFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            }
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_private_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
        )
        commit = CommitFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"token": "12345678"},
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="112" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#c0b01b" d="M76 0h36v20H76z" />
                    <path fill="url(#b)" d="M0 0h112v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="93" y="15" fill="#010101" fill-opacity=".3">85%</text>
                    <text x="93" y="14">85%</text>
                </g>
                <svg viewBox="120 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_branch_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
            branch="branch1",
        )
        commit = CommitFactory(repository=repo, author=gh_owner)
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
        commit_2 = CommitFactory(
            repository=repo, author=gh_owner, totals=commit_2_totals
        )
        branch_2 = BranchFactory(
            repository=repo, name="branch1", head=commit_2.commitid
        )
        # test default precision
        response = self._get_branch(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "branch": "branch1",
            },
            data={"token": "12345678"},
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="112" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#8aca02" d="M76 0h36v20H76z" />
                    <path fill="url(#b)" d="M0 0h112v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="93" y="15" fill="#010101" fill-opacity=".3">95%</text>
                    <text x="93" y="14">95%</text>
                </g>
                <svg viewBox="120 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_badge_with_100_coverage(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
            branch="branch1",
        )
        commit = CommitFactory(repository=repo, author=gh_owner)
        commit_2_totals = {
            "C": 0,
            "M": 0,
            "N": 0,
            "b": 0,
            "c": "100.00000",
            "d": 0,
            "diff": [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
            "f": 3,
            "h": 17,
            "m": 3,
            "n": 20,
            "p": 0,
            "s": 1,
        }
        commit_2 = CommitFactory(
            repository=repo, author=gh_owner, totals=commit_2_totals
        )
        branch_2 = BranchFactory(
            repository=repo, name="branch1", head=commit_2.commitid
        )
        # test default precision
        response = self._get_branch(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "branch": "branch1",
            },
            data={"token": "12345678"},
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="122" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="122" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#4c1" d="M76 0h46v20H76z" />
                    <path fill="url(#b)" d="M0 0h122v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="98" y="15" fill="#010101" fill-opacity=".3">100%</text>
                    <text x="98" y="14">100%</text>
                </g>
                <svg viewBox="140 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_branch_badge_with_slash(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=True,
            name="repo1",
            image_token="12345678",
            branch="branch1",
        )
        commit = CommitFactory(repository=repo, author=gh_owner)
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
        commit_2 = CommitFactory(
            repository=repo, author=gh_owner, totals=commit_2_totals
        )
        branch_2 = BranchFactory(
            repository=repo, name="test/branch1", head=commit_2.commitid
        )
        # test default precision
        response = self._get_branch(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
                "branch": "test%2Fbranch1",
            },
            data={"token": "12345678"},
        )
        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="112" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#8aca02" d="M76 0h36v20H76z" />
                    <path fill="url(#b)" d="M0 0h112v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="93" y="15" fill="#010101" fill-opacity=".3">95%</text>
                    <text x="93" y="14">95%</text>
                </g>
                <svg viewBox="120 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""
        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_flag_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        report = {
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
                    "t": [3, 20, 17, 3, 0, "95.00000", 0, 0, 0, 0, 0, 0, 0],
                    "": None,
                }
            }
        }
        commit = CommitFactory(repository=repo, author=gh_owner, report=report)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"flag": "unittests"},
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="112" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#8aca02" d="M76 0h36v20H76z" />
                    <path fill="url(#b)" d="M0 0h112v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="93" y="15" fill="#010101" fill-opacity=".3">95%</text>
                    <text x="93" y="14">95%</text>
                </g>
                <svg viewBox="120 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_none_flag_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        report = {
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
                    "t": None,
                    "": None,
                }
            }
        }
        commit = CommitFactory(repository=repo, author=gh_owner, report=report)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"flag": "unittests"},
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="137" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                    <path fill="url(#b)" d="M0 0h137v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                    <text x="105.5" y="14">unknown</text>
                </g>
                <svg viewBox="161 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>
        """

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_flag_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        report = {
            "sessions": {
                "0": {
                    "N": None,
                    "a": "v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
                    "c": None,
                    "d": 1547084427,
                    "e": None,
                    "f": None,
                    "j": None,
                    "n": None,
                    "p": None,
                    "t": [3, 20, 17, 3, 0, "95.00000", 0, 0, 0, 0, 0, 0, 0],
                    "": None,
                }
            }
        }
        commit = CommitFactory(repository=repo, author=gh_owner, report=report)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"flag": "unittests"},
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
            <linearGradient id="b" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                <stop offset="1" stop-opacity=".1" />
            </linearGradient>
            <mask id="a">
                <rect width="137" height="20" rx="3" fill="#fff" />
            </mask>
            <g mask="url(#a)">
                <path fill="#555" d="M0 0h76v20H0z" />
                <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                <path fill="url(#b)" d="M0 0h137v20H0z" />
            </g>
            <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                <text x="46" y="14">codecov</text>
                <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                <text x="105.5" y="14">unknown</text>
            </g>
            <svg viewBox="161 -8 60 60">
                <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
            </svg>
        </svg>
        """

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_sessions_flag_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        report = {}
        commit = CommitFactory(repository=repo, author=gh_owner, report=report)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"flag": "unittests"},
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
            <linearGradient id="b" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                <stop offset="1" stop-opacity=".1" />
            </linearGradient>
            <mask id="a">
                <rect width="137" height="20" rx="3" fill="#fff" />
            </mask>
            <g mask="url(#a)">
                <path fill="#555" d="M0 0h76v20H0z" />
                <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                <path fill="url(#b)" d="M0 0h137v20H0z" />
            </g>
            <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                <text x="46" y="14">codecov</text>
                <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                <text x="105.5" y="14">unknown</text>
            </g>
            <svg viewBox="161 -8 60 60">
                <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
            </svg>
        </svg>
        """

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_unknown_report_flag_badge(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner, active=True, private=False, name="repo1"
        )
        report = None
        commit = CommitFactory(repository=repo, author=gh_owner, report=report)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            },
            data={"flag": "unittests"},
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="137" height="20">
            <linearGradient id="b" x2="0" y2="100%">
                <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                <stop offset="1" stop-opacity=".1" />
            </linearGradient>
            <mask id="a">
                <rect width="137" height="20" rx="3" fill="#fff" />
            </mask>
            <g mask="url(#a)">
                <path fill="#555" d="M0 0h76v20H0z" />
                <path fill="#9f9f9f" d="M76 0h61v20H76z" />
                <path fill="url(#b)" d="M0 0h137v20H0z" />
            </g>
            <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                <text x="46" y="14">codecov</text>
                <text x="105.5" y="15" fill="#010101" fill-opacity=".3">unknown</text>
                <text x="105.5" y="14">unknown</text>
            </g>
            <svg viewBox="161 -8 60 60">
                <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
            </svg>
        </svg>
        """

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_yaml_range(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=False,
            name="repo1",
            yaml={"coverage": {"range": [0.0, 0.8]}},
        )
        commit = CommitFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            }
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="112" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#4c1" d="M76 0h36v20H76z" />
                    <path fill="url(#b)" d="M0 0h112v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="93" y="15" fill="#010101" fill-opacity=".3">85%</text>
                    <text x="93" y="14">85%</text>
                </g>
                <svg viewBox="120 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK

    def test_yaml_empty_range(self):
        gh_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(
            author=gh_owner,
            active=True,
            private=False,
            name="repo1",
            yaml={"coverage": {}},
        )
        commit = CommitFactory(repository=repo, author=gh_owner)

        # test default precision
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": gh_owner.username,
                "repo_name": "repo1",
                "ext": "svg",
            }
        )

        expected_badge = """<svg xmlns="http://www.w3.org/2000/svg" width="112" height="20">
                <linearGradient id="b" x2="0" y2="100%">
                    <stop offset="0" stop-color="#bbb" stop-opacity=".1" />
                    <stop offset="1" stop-opacity=".1" />
                </linearGradient>
                <mask id="a">
                    <rect width="112" height="20" rx="3" fill="#fff" />
                </mask>
                <g mask="url(#a)">
                    <path fill="#555" d="M0 0h76v20H0z" />
                    <path fill="#c0b01b" d="M76 0h36v20H76z" />
                    <path fill="url(#b)" d="M0 0h112v20H0z" />
                </g>
                <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
                    <text x="46" y="15" fill="#010101" fill-opacity=".3">codecov</text>
                    <text x="46" y="14">codecov</text>
                    <text x="93" y="15" fill="#010101" fill-opacity=".3">85%</text>
                    <text x="93" y="14">85%</text>
                </g>
                <svg viewBox="120 -8 60 60">
                    <path d="M23.013 0C10.333.009.01 10.22 0 22.762v.058l3.914 2.275.053-.036a11.291 11.291 0 0 1 8.352-1.767 10.911 10.911 0 0 1 5.5 2.726l.673.624.38-.828c.368-.802.793-1.556 1.264-2.24.19-.276.398-.554.637-.851l.393-.49-.484-.404a16.08 16.08 0 0 0-7.453-3.466 16.482 16.482 0 0 0-7.705.449C7.386 10.683 14.56 5.016 23.03 5.01c4.779 0 9.272 1.84 12.651 5.18 2.41 2.382 4.069 5.35 4.807 8.591a16.53 16.53 0 0 0-4.792-.723l-.292-.002a16.707 16.707 0 0 0-1.902.14l-.08.012c-.28.037-.524.074-.748.115-.11.019-.218.041-.327.063-.257.052-.51.108-.75.169l-.265.067a16.39 16.39 0 0 0-.926.276l-.056.018c-.682.23-1.36.511-2.016.838l-.052.026c-.29.145-.584.305-.899.49l-.069.04a15.596 15.596 0 0 0-4.061 3.466l-.145.175c-.29.36-.521.666-.723.96-.17.247-.34.513-.552.864l-.116.199c-.17.292-.32.57-.449.824l-.03.057a16.116 16.116 0 0 0-.843 2.029l-.034.102a15.65 15.65 0 0 0-.786 5.174l.003.214a21.523 21.523 0 0 0 .04.754c.009.119.02.237.032.355.014.145.032.29.049.432l.01.08c.01.067.017.133.026.197.034.242.074.48.119.72.463 2.419 1.62 4.836 3.345 6.99l.078.098.08-.095c.688-.81 2.395-3.38 2.539-4.922l.003-.029-.014-.025a10.727 10.727 0 0 1-1.226-4.956c0-5.76 4.545-10.544 10.343-10.89l.381-.014a11.403 11.403 0 0 1 6.651 1.957l.054.036 3.862-2.237.05-.03v-.056c.006-6.08-2.384-11.793-6.729-16.089C34.932 2.361 29.16 0 23.013 0" fill="#F01F7A" fill-rule="evenodd"/>
                </svg>
            </svg>"""

        badge = response.content.decode("utf-8")
        badge = [line.strip() for line in badge.split("\n")]
        expected_badge = [line.strip() for line in expected_badge.split("\n")]
        assert expected_badge == badge
        assert response.status_code == status.HTTP_200_OK
