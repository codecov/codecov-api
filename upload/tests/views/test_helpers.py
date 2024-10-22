from django.test import TestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from codecov_auth.models import Service
from upload.views.helpers import (
    get_repository_and_owner_from_string,
    get_repository_from_string,
)


class ViewHelpersTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gh = Service.GITHUB
        cls.bb = Service.BITBUCKET
        cls.gl = Service.GITLAB
        cls.uname = "simpleusername"
        cls.repo_1_name = "simplerepo"
        cls.repo_2_name = "anotherrepo"
        cls.group = "somegroup"
        cls.subgroup = "somesubgroup"
        cls.sub_subgroup = "subsub"
        owners_to_repos_mapping = {
            cls.gh: {cls.uname: [cls.repo_1_name, cls.repo_2_name]},
            cls.bb: {cls.uname: [cls.repo_1_name, cls.repo_2_name]},
            cls.gl: {
                cls.uname: [cls.repo_1_name, cls.repo_2_name],
                cls.group: [cls.repo_1_name],
                f"{cls.group}:{cls.subgroup}": [cls.repo_1_name],
                f"{cls.group}:{cls.subgroup}:{cls.sub_subgroup}": [
                    cls.repo_1_name,
                    cls.repo_2_name,
                ],
            },
        }
        for service, owner_data in owners_to_repos_mapping.items():
            for username, repo_names in owner_data.items():
                RepositoryFactory()
                o = OwnerFactory(service=service, username=username)
                for r_name in repo_names:
                    RepositoryFactory(author=o, name=r_name)

    def test_get_repository_from_string(self):
        first_result = get_repository_from_string(
            self.gh, f"{self.uname}::::{self.repo_1_name}"
        )
        assert first_result.name == self.repo_1_name
        assert first_result.author.username == self.uname
        assert first_result.author.service == self.gh
        second_result = get_repository_from_string(
            self.bb, f"{self.uname}::::{self.repo_1_name}"
        )
        assert second_result.name == self.repo_1_name
        assert second_result.author.username == self.uname
        assert second_result.author.service == self.bb
        assert first_result != second_result
        assert (
            get_repository_from_string(
                self.gh, f"somerandomlalala::::{self.repo_1_name}"
            )
            is None
        )
        assert (
            get_repository_from_string(
                self.gh, f"{self.uname}::::{self.repo_1_name}wrongname"
            )
            is None
        )
        assert (
            get_repository_from_string(
                "badgithub", f"{self.uname}::::{self.repo_1_name}"
            )
            is None
        )
        first_gitlab_result = get_repository_from_string(
            self.gl, f"{self.group}::::{self.repo_1_name}"
        )
        assert first_gitlab_result.name == self.repo_1_name
        assert first_gitlab_result.author.username == self.group
        assert first_gitlab_result.author.service == self.gl
        second_gitlab_result = get_repository_from_string(
            self.gl, f"{self.group}:::{self.subgroup}::::{self.repo_1_name}"
        )
        assert second_gitlab_result.name == self.repo_1_name
        assert second_gitlab_result.author.username == f"{self.group}:{self.subgroup}"
        assert second_gitlab_result.author.service == self.gl
        assert (
            get_repository_from_string(
                self.gl, f"{self.group}:::somebadsubgroup::::{self.repo_1_name}"
            )
            is None
        )

    def test_get_repository_and_owner_from_string(self):
        first_result_repository, first_result_owner = (
            get_repository_and_owner_from_string(
                self.gh, f"{self.uname}::::{self.repo_1_name}"
            )
        )
        assert first_result_repository.name == self.repo_1_name
        assert first_result_repository.author.username == self.uname
        assert first_result_repository.author.service == self.gh
        assert first_result_repository.author == first_result_owner

        second_result_repository, second_result_owner = (
            get_repository_and_owner_from_string(
                self.bb, f"{self.uname}::::{self.repo_1_name}"
            )
        )
        assert second_result_repository.name == self.repo_1_name
        assert second_result_repository.author.username == self.uname
        assert second_result_repository.author.service == self.bb
        assert first_result_repository != second_result_repository
        assert second_result_repository.author == second_result_owner

        assert get_repository_and_owner_from_string(
            self.gh, f"somerandomlalala::::{self.repo_1_name}"
        ) == (None, None)
        assert get_repository_and_owner_from_string(
            self.gh, f"{self.uname}::::{self.repo_1_name}wrongname"
        ) == (None, None)
        assert get_repository_and_owner_from_string(
            "badgithub", f"{self.uname}::::{self.repo_1_name}"
        ) == (None, None)

        first_gitlab_result_repository, first_gitlab_result_owner = (
            get_repository_and_owner_from_string(
                self.gl, f"{self.group}::::{self.repo_1_name}"
            )
        )
        assert first_gitlab_result_repository.name == self.repo_1_name
        assert first_gitlab_result_repository.author.username == self.group
        assert first_gitlab_result_repository.author.service == self.gl
        assert first_gitlab_result_repository.author == first_gitlab_result_owner

        second_gitlab_result_repository, second_gitlab_result_owner = (
            get_repository_and_owner_from_string(
                self.gl, f"{self.group}:::{self.subgroup}::::{self.repo_1_name}"
            )
        )
        assert second_gitlab_result_repository.name == self.repo_1_name
        assert (
            second_gitlab_result_repository.author.username
            == f"{self.group}:{self.subgroup}"
        )
        assert second_gitlab_result_repository.author.service == self.gl
        assert second_gitlab_result_owner == second_gitlab_result_repository.author
        assert get_repository_and_owner_from_string(
            self.gl, f"{self.group}:::somebadsubgroup::::{self.repo_1_name}"
        ) == (None, None)
