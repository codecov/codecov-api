from django.test import TestCase
from shared.django_apps.codecov_auth.models import Owner
from shared.django_apps.core.models import Repository

from codecov_auth.models import Service
from core.tests.factories import CommitFactory, OwnerFactory, RepositoryFactory
from upload.views.helpers import (
    get_repository_and_owner_from_slug_and_commit,
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
        cls.commitid = CommitFactory().commitid
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
                o = OwnerFactory(service=service, username=username)
                for r_name in repo_names:
                    r = RepositoryFactory(author=o, name=r_name)
                    CommitFactory(repository=r, commitid=cls.commitid)

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

    def test_get_repository_and_owner_from_slug_and_commit(self):
        # the test cases from setUpClass won't work on this method, they all have
        # same username, repo name, and commitid
        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"{self.uname}::::{self.repo_1_name}", commitid=self.commitid
        ) == (None, None)

        # can identify by unique commitid
        gh_owner = Owner.objects.get(service=self.gh, username=self.uname)
        gh_repo = Repository.objects.get(author=gh_owner, name=self.repo_1_name)
        unique_commit = CommitFactory(repository=gh_repo)
        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"{self.uname}::::{self.repo_1_name}", commitid=unique_commit.commitid
        ) == (gh_repo, gh_owner)

        # can identify by unique username
        gl_owner = Owner.objects.get(service=self.gl, username=self.uname)
        gl_repo = Repository.objects.get(author=gl_owner, name=self.repo_1_name)
        gl_owner.username = "other"
        gl_owner.save()
        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"other::::{self.repo_1_name}", commitid=self.commitid
        ) == (gl_repo, gl_owner)

        # can identify by unique repo name
        another_gh_repo = RepositoryFactory(author=gh_owner, name="another")
        CommitFactory(repository=another_gh_repo, commitid=self.commitid)
        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"{self.uname}::::another", commitid=self.commitid
        ) == (another_gh_repo, gh_owner)

        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"somerandomlalala::::{self.repo_1_name}", commitid=self.commitid
        ) == (None, None)
        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"{self.uname}::::{self.repo_1_name}wrongname", commitid=self.commitid
        ) == (None, None)
        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"{self.uname}::::{self.repo_1_name}", commitid="nonsense"
        ) == (None, None)
        assert get_repository_and_owner_from_slug_and_commit(
            slug=f"{self.group}:::somebadsubgroup::::{self.repo_1_name}",
            commitid=self.commitid,
        ) == (None, None)

        # gitlab group
        gitlab_group_repository, gitlab_group = (
            get_repository_and_owner_from_slug_and_commit(
                slug=f"{self.group}::::{self.repo_1_name}", commitid=self.commitid
            )
        )
        assert gitlab_group_repository.name == self.repo_1_name
        assert gitlab_group_repository.author.username == self.group
        assert gitlab_group_repository.author.service == self.gl
        assert gitlab_group_repository.author == gitlab_group

        # gitlab subgroup
        gitlab_subgroup_repository, gitlab_subgroup = (
            get_repository_and_owner_from_slug_and_commit(
                slug=f"{self.group}:::{self.subgroup}::::{self.repo_1_name}",
                commitid=self.commitid,
            )
        )
        assert gitlab_subgroup_repository.name == self.repo_1_name
        assert (
            gitlab_subgroup_repository.author.username
            == f"{self.group}:{self.subgroup}"
        )
        assert gitlab_subgroup_repository.author.service == self.gl
        assert gitlab_subgroup_repository.author == gitlab_subgroup

        # gitlab subgroup of a subgroup
        gitlab_sub_subgroup_repository, gitlab_sub_subgroup = (
            get_repository_and_owner_from_slug_and_commit(
                slug=f"{self.group}:::{self.subgroup}:::{self.sub_subgroup}::::{self.repo_1_name}",
                commitid=self.commitid,
            )
        )
        assert gitlab_sub_subgroup_repository.name == self.repo_1_name
        assert (
            gitlab_sub_subgroup_repository.author.username
            == f"{self.group}:{self.subgroup}:{self.sub_subgroup}"
        )
        assert gitlab_sub_subgroup_repository.author.service == self.gl
        assert gitlab_sub_subgroup_repository.author == gitlab_sub_subgroup
