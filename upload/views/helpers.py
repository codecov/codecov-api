import typing

from codecov_auth.models import Owner, Service
from core.models import Repository


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
