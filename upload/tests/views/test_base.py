import pytest
from rest_framework.exceptions import ValidationError

from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport
from upload.views.base import GetterMixin


def test_get_repo(db):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    repository.save()
    generic_class = GetterMixin()
    generic_class.kwargs = dict(repo="codecov::::the_repo", service="github")
    recovered_repo = generic_class.get_repo()
    assert recovered_repo == repository


def test_get_repo_with_invalid_service(db):
    generic_class = GetterMixin()
    generic_class.kwargs = dict(repo="repo", service="wrong service")
    with pytest.raises(ValidationError) as exp:
        generic_class.get_repo()
    assert exp.match("Service not found: wrong service")


def test_get_repo_not_found(db):
    generic_class = GetterMixin()
    generic_class.kwargs = dict(repo="repo", service="github")
    with pytest.raises(ValidationError) as exp:
        generic_class.get_repo()
    assert exp.match("Repository not found")


def test_get_commit(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()
    generic_class = GetterMixin()
    generic_class.kwargs = dict(repo=repository.name, commit_sha=commit.commitid)
    recovered_commit = generic_class.get_commit(repository)
    assert recovered_commit == commit


def test_get_commit_error(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    repository.save()
    generic_class = GetterMixin()
    generic_class.kwargs = dict(repo=repository.name, commit_sha="missing_commit")
    with pytest.raises(ValidationError) as exp:
        generic_class.get_commit(repository)
    assert exp.match("Commit SHA not found")


def test_get_report(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    report = CommitReport(commit=commit)
    repository.save()
    commit.save()
    report.save()
    generic_class = GetterMixin()
    generic_class.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, report_code=report.code
    )
    recovered_report = generic_class.get_report(commit)
    assert recovered_report == report


def test_get_report_error(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()
    generic_class = GetterMixin()
    generic_class.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, report_code="random_code"
    )
    with pytest.raises(ValidationError) as exp:
        generic_class.get_report(commit)
    assert exp.match("Report not found")
