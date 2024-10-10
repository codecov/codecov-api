import logging
import typing

from shared.django_apps.core.models import Commit

from codecov_auth.models import Owner, Service
from core.models import Repository

log = logging.getLogger(__name__)


def get_repository_and_owner_from_string(
    service: Service, repo_identifier: str
) -> tuple[Repository | None, Owner | None]:
    if not isinstance(service, Service):
        # if we pass this value to the db, it just raises DataError
        # No need for that
        return None, None

    if "::::" not in repo_identifier:
        return None, None

    owner_identifier, repo_name_identifier = repo_identifier.rsplit("::::", 1)
    owner = _get_owner_from_string(service, owner_identifier)
    if not owner:
        return None, None
    try:
        repository = Repository.objects.get(author=owner, name=repo_name_identifier)
    except Repository.DoesNotExist:
        return None, None

    return repository, owner


def _get_owner_from_string(
    service: Service, owner_identifier: str
) -> typing.Optional[Owner]:
    if ":::" in owner_identifier:
        owner_identifier = owner_identifier.replace(":::", ":")
    try:
        return Owner.objects.get(service=service, username=owner_identifier)
    except Owner.DoesNotExist:
        return None


def get_repository_from_string(
    service: Service, repo_identifier: str
) -> Repository | None:
    repository, _ = get_repository_and_owner_from_string(
        service=service, repo_identifier=repo_identifier
    )
    return repository


def get_repository_and_owner_from_slug_and_commit(
    slug: str, commitid: str
) -> tuple[Repository | None, Owner | None]:
    if "::::" not in slug:
        return None, None

    owner_username, repository_name = slug.rsplit("::::", 1)

    # formatting for GL subgroups
    if ":::" in owner_username:
        owner_username = owner_username.replace(":::", ":")

    matching_repositories = Repository.objects.filter(
        author__username=owner_username, name=repository_name
    ).select_related("author")
    if matching_repositories.count() == 1:
        log.info(
            "get_repository_and_owner_from_slug_and_commit success",
            extra=dict(slug=slug),
        )
        repository = matching_repositories.first()
        return repository, repository.author
    else:
        # commit might not exist yet (if this is first upload for it)
        try:
            # Commit has UniqueConstraint on commitid + repository
            commit = Commit.objects.select_related(
                "repository", "repository__author"
            ).get(commitid=commitid, repository__in=matching_repositories)
            log.info(
                "get_repository_and_owner_from_slug_and_commit multiple matches success",
                extra=dict(slug=slug),
            )
            return commit.repository, commit.repository.author
        except (Commit.DoesNotExist, Commit.MultipleObjectsReturned):
            log.info(
                "get_repository_and_owner_from_slug_and_commit fail",
                extra=dict(slug=slug),
            )
            return None, None
