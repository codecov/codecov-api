from contextlib import nullcontext

import pytest
from django.conf import settings
from rest_framework.exceptions import Throttled, ValidationError

from billing.constants import BASIC_PLAN_NAME
from core.tests.factories import CommitFactory, OwnerFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory, UploadFactory
from upload.helpers import (
    check_commit_upload_constraints,
    try_to_get_best_possible_bot_token,
    validate_activated_repo,
    validate_upload,
)


def test_try_to_get_best_possible_bot_token_no_repobot_no_ownerbot(db):
    owner = OwnerFactory.create(unencrypted_oauth_token="super")
    owner.save()
    repository = RepositoryFactory.create(author=owner)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "super",
        "secret": None,
    }


def test_try_to_get_best_possible_bot_token_no_repobot_yes_ownerbot(db):
    bot = OwnerFactory.create(unencrypted_oauth_token="bornana")
    bot.save()
    owner = OwnerFactory.create(unencrypted_oauth_token="super", bot=bot)
    owner.save()
    repository = RepositoryFactory.create(author=owner)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "bornana",
        "secret": None,
    }


def test_try_to_get_best_possible_bot_token_yes_repobot(db):
    bot = OwnerFactory.create(unencrypted_oauth_token="bornana")
    bot.save()
    another_bot = OwnerFactory.create(unencrypted_oauth_token="anotha_one")
    another_bot.save()
    owner = OwnerFactory.create(unencrypted_oauth_token="super", bot=bot)
    owner.save()
    repository = RepositoryFactory.create(author=owner, bot=another_bot)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "anotha_one",
        "secret": None,
    }


def test_try_to_get_best_possible_nothing_and_is_private(db):
    owner = OwnerFactory.create(oauth_token=None)
    owner.save()
    repository = RepositoryFactory.create(author=owner, bot=None, private=True)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) is None


def test_try_to_get_best_possible_nothing_and_not_private(db, mocker):
    something = mocker.MagicMock()
    mock_get_config = mocker.patch("upload.helpers.get_config", return_value=something)
    owner = OwnerFactory.create(service="github", oauth_token=None)
    owner.save()
    repository = RepositoryFactory.create(author=owner, bot=None, private=False)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) is something
    mock_get_config.assert_called_with("github", "bots", "tokenless")


def test_check_commit_contraints_settings_disabled(db, settings):
    settings.UPLOAD_THROTTLING_ENABLED = False
    repository = RepositoryFactory.create(author__plan=BASIC_PLAN_NAME, private=True)
    first_commit = CommitFactory.create(repository=repository)
    second_commit = CommitFactory.create(repository=repository)
    third_commit = CommitFactory.create(repository__author=repository.author)
    unrelated_commit = CommitFactory.create()
    report = CommitReportFactory.create(commit=first_commit)
    for i in range(300):
        UploadFactory.create(report=report)
    # no commit should be throttled
    check_commit_upload_constraints(first_commit)
    check_commit_upload_constraints(unrelated_commit)
    check_commit_upload_constraints(second_commit)
    check_commit_upload_constraints(third_commit)


def test_check_commit_contraints_settings_enabled(db, settings):
    settings.UPLOAD_THROTTLING_ENABLED = True
    author = OwnerFactory.create(plan=BASIC_PLAN_NAME)
    repository = RepositoryFactory.create(author=author, private=True)
    public_repository = RepositoryFactory.create(author=author, private=False)
    first_commit = CommitFactory.create(repository=repository)
    second_commit = CommitFactory.create(repository=repository)
    third_commit = CommitFactory.create(repository__author=repository.author)
    fourth_commit = CommitFactory.create(repository=repository)
    public_repository_commit = CommitFactory.create(repository=public_repository)
    unrelated_commit = CommitFactory.create()
    first_report = CommitReportFactory.create(commit=first_commit)
    fourth_report = CommitReportFactory.create(commit=fourth_commit)
    check_commit_upload_constraints(second_commit)
    for i in range(300):
        UploadFactory.create(report__commit__repository=public_repository)
    # ensuring public repos counts don't count torwards the quota
    check_commit_upload_constraints(second_commit)
    for i in range(150):
        UploadFactory.create(report=first_report)
        UploadFactory.create(report=fourth_report)
    # first and fourth commit already has uploads made, we won't block uploads to them
    check_commit_upload_constraints(first_commit)
    check_commit_upload_constraints(fourth_commit)
    # unrelated commit belongs to a different user. Ensuring we don't block it
    check_commit_upload_constraints(unrelated_commit)
    # public repositories commit should never be throttled
    check_commit_upload_constraints(public_repository_commit)
    with pytest.raises(Throttled):
        # second commit does not have uploads made, so we block it
        check_commit_upload_constraints(second_commit)
    with pytest.raises(Throttled) as excinfo:
        # third commit belongs to a different repo, but same user
        check_commit_upload_constraints(third_commit)
    assert (
        "Throttled due to limit on private repository coverage uploads"
        in excinfo.value.detail
    )


@pytest.mark.parametrize(
    "totals_column_count, rows_count, should_raise",
    [(151, 0, False), (151, 151, True), (0, 0, False), (0, 200, True)],
)
def test_validate_upload_too_many_uploads_for_commit(
    db, totals_column_count, rows_count, should_raise, mocker
):
    redis = mocker.MagicMock(sismember=mocker.MagicMock(return_value=False))
    owner = OwnerFactory.create(plan="users-free")
    repo = RepositoryFactory.create(author=owner)
    commit = CommitFactory.create(totals={"s": totals_column_count}, repository=repo)
    report = CommitReportFactory.create(commit=commit)
    for i in range(rows_count):
        UploadFactory.create(report=report)
    with pytest.raises(ValidationError) if should_raise else nullcontext():
        validate_upload({"commit": commit.commitid}, repo, redis)


def test_deactivated_repo(db, mocker):
    repository = RepositoryFactory.create(active=True, activated=False)
    settings_url = f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/settings"

    with pytest.raises(ValidationError) as exp:
        validate_activated_repo(repository)
    assert exp.match(
        f"This repository has been deactivated. To resume uploading to it, please activate the repository in the codecov UI: {settings_url}"
    )
