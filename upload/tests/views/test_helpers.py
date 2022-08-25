from codecov_auth.models import Service
from core.tests.factories import OwnerFactory, RepositoryFactory
from upload.views.helpers import get_repository_from_string


def test_get_repository_from_string(db):
    owners_to_repos_mapping = {
        Service.GITHUB: {"simpleusername": ["simplerepo", "anotherrepo"]},
        Service.BITBUCKET: {"simpleusername": ["simplerepo", "anotherrepo"]},
        Service.GITLAB: {
            "simpleusername": ["simplerepo", "anotherrepo"],
            "somegroup": ["simplerepo"],
            "somegroup:somesubgroup": ["simplerepo"],
            "somegroup:somesubgroup:subsub": ["simplerepo", "anotherrepo"],
        },
    }
    for service, owner_data in owners_to_repos_mapping.items():
        for username, repo_names in owner_data.items():
            o = OwnerFactory.create(service=service, username=username)
            o.save()
            for r_name in repo_names:
                r = RepositoryFactory.create(author=o, name=r_name)
                r.save()
    first_result = get_repository_from_string(
        Service.GITHUB, "simpleusername::::simplerepo"
    )
    assert first_result.name == "simplerepo"
    assert first_result.author.username == "simpleusername"
    assert first_result.author.service == Service.GITHUB
    second_result = get_repository_from_string(
        Service.BITBUCKET, "simpleusername::::simplerepo"
    )
    assert second_result.name == "simplerepo"
    assert second_result.author.username == "simpleusername"
    assert second_result.author.service == Service.BITBUCKET
    assert first_result != second_result
    assert (
        get_repository_from_string(Service.GITHUB, "somerandomlalala::::simplerepo")
        is None
    )
    assert (
        get_repository_from_string(
            Service.GITHUB, "simpleusername::::simplerepowrongname"
        )
        is None
    )
    assert (
        get_repository_from_string("badgithub", "simpleusername::::simplerepo") is None
    )
    first_gitlab_result = get_repository_from_string(
        Service.GITLAB, "somegroup::::simplerepo"
    )
    assert first_gitlab_result.name == "simplerepo"
    assert first_gitlab_result.author.username == "somegroup"
    assert first_gitlab_result.author.service == Service.GITLAB
    second_gitlab_result = get_repository_from_string(
        Service.GITLAB, "somegroup:::somesubgroup::::simplerepo"
    )
    assert second_gitlab_result.name == "simplerepo"
    assert second_gitlab_result.author.username == "somegroup:somesubgroup"
    assert second_gitlab_result.author.service == Service.GITLAB
    assert (
        get_repository_from_string(
            Service.GITLAB, "somegroup:::somebadsubgroup::::simplerepo"
        )
        is None
    )
