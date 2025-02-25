from contextlib import nullcontext
from unittest.mock import patch

import jwt
import pytest
from django.conf import settings
from django.test import TestCase
from rest_framework.exceptions import Throttled, ValidationError
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.django_apps.reports.models import ReportType
from shared.plan.constants import DEFAULT_FREE_PLAN
from shared.upload.utils import UploaderType, insert_coverage_measurement

from billing.helpers import mock_all_plans_and_tiers
from codecov_auth.models import GithubAppInstallation, Service
from reports.tests.factories import CommitReportFactory, UploadFactory
from upload.helpers import (
    check_commit_upload_constraints,
    determine_repo_for_upload,
    ghapp_installation_id_to_use,
    try_to_get_best_possible_bot_token,
    validate_activated_repo,
    validate_upload,
)


class TestGithubAppInstallationUsage(TestCase):
    def test_not_github_provider(self):
        repo = RepositoryFactory(author__service=Service.GITLAB.value)
        assert ghapp_installation_id_to_use(repo) is None

    def test_github_app_installation_flow(self):
        owner = OwnerFactory(service=Service.GITHUB.value, integration_id=None)
        covered_repo = RepositoryFactory(author=owner)
        not_covered_repo = RepositoryFactory(author=owner)
        ghapp_installation = GithubAppInstallation(
            owner=owner,
            repository_service_ids=[covered_repo.service_id],
            installation_id=200,
        )
        ghapp_installation.save()
        assert ghapp_installation_id_to_use(covered_repo) == 200
        assert ghapp_installation_id_to_use(not_covered_repo) is None


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


@patch("upload.helpers.get_github_integration_token")
@pytest.mark.django_db
def test_try_to_get_best_possible_bot_token_using_integration(
    get_github_integration_token,
):
    get_github_integration_token.return_value = "test-token"
    owner = OwnerFactory.create(integration_id=12345)
    owner.save()
    repository = RepositoryFactory.create(author=owner, using_integration=True)
    repository.save()
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "test-token",
    }
    get_github_integration_token.assert_called_once_with(
        "github", installation_id=12345
    )


@patch("upload.helpers.get_github_integration_token")
@pytest.mark.django_db
def test_try_to_get_best_possible_bot_token_using_invalid_integration(
    get_github_integration_token,
):
    from shared.github import InvalidInstallationError  # circular imports

    get_github_integration_token.side_effect = InvalidInstallationError(
        error_cause="installation_not_found"
    )
    bot = OwnerFactory.create(unencrypted_oauth_token="bornana")
    bot.save()
    owner = OwnerFactory.create(integration_id=12345, bot=bot)
    owner.save()
    repository = RepositoryFactory.create(author=owner, using_integration=True)
    repository.save()
    # falls back to bot token
    assert try_to_get_best_possible_bot_token(repository) == {
        "key": "bornana",
        "secret": None,
    }
    get_github_integration_token.assert_called_once_with(
        "github", installation_id=12345
    )


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


def test_check_commit_constraints_settings_disabled(db, settings):
    settings.UPLOAD_THROTTLING_ENABLED = False
    repository = RepositoryFactory.create(author__plan=DEFAULT_FREE_PLAN, private=True)
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


def test_check_commit_constraints_settings_enabled(db, settings, mocker):
    settings.UPLOAD_THROTTLING_ENABLED = True
    mock_all_plans_and_tiers()
    author = OwnerFactory.create(plan=DEFAULT_FREE_PLAN)
    repository = RepositoryFactory.create(author=author, private=True)
    public_repository = RepositoryFactory.create(author=author, private=False)
    first_commit = CommitFactory.create(repository=repository)
    second_commit = CommitFactory.create(repository=repository)
    third_commit = CommitFactory.create(repository__author=repository.author)
    fourth_commit = CommitFactory.create(repository=repository)
    public_repository_commit = CommitFactory.create(repository=public_repository)
    unrelated_commit = CommitFactory.create()
    first_report = CommitReportFactory.create(
        commit=first_commit, report_type=ReportType.COVERAGE.value
    )
    fourth_report = CommitReportFactory.create(
        commit=fourth_commit, report_type=ReportType.COVERAGE.value
    )
    check_commit_upload_constraints(second_commit)
    for i in range(300):
        UploadFactory.create(report__commit__repository=public_repository)
        first_upload = UploadFactory(report=first_report)
        insert_coverage_measurement(
            owner_id=author.ownerid,
            repo_id=public_repository.repoid,
            commit_id=public_repository_commit.id,
            upload_id=first_upload.id,
            uploader_used=UploaderType.CLI.value,
            private_repo=public_repository.private,
            report_type=first_report.report_type,
        )
    # ensuring public repos counts don't count towards the quota
    check_commit_upload_constraints(second_commit)
    for i in range(150):
        another_first_upload = UploadFactory.create(report=first_report)
        insert_coverage_measurement(
            owner_id=author.ownerid,
            repo_id=repository.repoid,
            commit_id=first_commit.id,
            upload_id=another_first_upload.id,
            uploader_used=UploaderType.CLI.value,
            private_repo=repository.private,
            report_type=first_report.report_type,
        )
        fourth_upload = UploadFactory.create(report=fourth_report)
        insert_coverage_measurement(
            owner_id=author.ownerid,
            repo_id=repository.repoid,
            commit_id=fourth_commit.id,
            upload_id=fourth_upload.id,
            uploader_used=UploaderType.CLI.value,
            private_repo=repository.private,
            report_type=fourth_report.report_type,
        )
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
    config_url = f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/config/general"

    with pytest.raises(ValidationError) as exp:
        validate_activated_repo(repository)
    assert exp.match(
        f"This repository is deactivated. To resume uploading to it, please activate the repository in the codecov UI: {config_url}"
    )


@pytest.mark.django_db
def test_determine_repo_for_upload_token():
    token = "80cd8016-5d26-40e5-8c71-f1c44e04aba0"
    repository = RepositoryFactory.create(upload_token=token)
    assert determine_repo_for_upload({"token": token}) == repository


# random keypair for RS256 JWTs used below
public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u
+qKhbwKfBstIs+bMY2Zkp18gnTxKLxoS2tFczGkPLPgizskuemMghRniWaoLcyeh
kd3qqGElvW/VDL5AaWTg0nLVkjRo9z+40RQzuVaE8AkAFmxZzow3x+VJYKdjykkJ
0iT9wCS0DRTXu269V264Vf/3jvredZiKRkgwlL9xNAwxXFg0x/XFw005UWVRIkdg
cKWTjpBP2dPwVZ4WWC+9aGVd+Gyn1o0CLelf4rEjGoXbAAEgAqeGUxrcIlbjXfbc
mwIDAQAB
-----END PUBLIC KEY-----"""
private_key = """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC7VJTUt9Us8cKj
MzEfYyjiWA4R4/M2bS1GB4t7NXp98C3SC6dVMvDuictGeurT8jNbvJZHtCSuYEvu
NMoSfm76oqFvAp8Gy0iz5sxjZmSnXyCdPEovGhLa0VzMaQ8s+CLOyS56YyCFGeJZ
qgtzJ6GR3eqoYSW9b9UMvkBpZODSctWSNGj3P7jRFDO5VoTwCQAWbFnOjDfH5Ulg
p2PKSQnSJP3AJLQNFNe7br1XbrhV//eO+t51mIpGSDCUv3E0DDFcWDTH9cXDTTlR
ZVEiR2BwpZOOkE/Z0/BVnhZYL71oZV34bKfWjQIt6V/isSMahdsAASACp4ZTGtwi
VuNd9tybAgMBAAECggEBAKTmjaS6tkK8BlPXClTQ2vpz/N6uxDeS35mXpqasqskV
laAidgg/sWqpjXDbXr93otIMLlWsM+X0CqMDgSXKejLS2jx4GDjI1ZTXg++0AMJ8
sJ74pWzVDOfmCEQ/7wXs3+cbnXhKriO8Z036q92Qc1+N87SI38nkGa0ABH9CN83H
mQqt4fB7UdHzuIRe/me2PGhIq5ZBzj6h3BpoPGzEP+x3l9YmK8t/1cN0pqI+dQwY
dgfGjackLu/2qH80MCF7IyQaseZUOJyKrCLtSD/Iixv/hzDEUPfOCjFDgTpzf3cw
ta8+oE4wHCo1iI1/4TlPkwmXx4qSXtmw4aQPz7IDQvECgYEA8KNThCO2gsC2I9PQ
DM/8Cw0O983WCDY+oi+7JPiNAJwv5DYBqEZB1QYdj06YD16XlC/HAZMsMku1na2T
N0driwenQQWzoev3g2S7gRDoS/FCJSI3jJ+kjgtaA7Qmzlgk1TxODN+G1H91HW7t
0l7VnL27IWyYo2qRRK3jzxqUiPUCgYEAx0oQs2reBQGMVZnApD1jeq7n4MvNLcPv
t8b/eU9iUv6Y4Mj0Suo/AU8lYZXm8ubbqAlwz2VSVunD2tOplHyMUrtCtObAfVDU
AhCndKaA9gApgfb3xw1IKbuQ1u4IF1FJl3VtumfQn//LiH1B3rXhcdyo3/vIttEk
48RakUKClU8CgYEAzV7W3COOlDDcQd935DdtKBFRAPRPAlspQUnzMi5eSHMD/ISL
DY5IiQHbIH83D4bvXq0X7qQoSBSNP7Dvv3HYuqMhf0DaegrlBuJllFVVq9qPVRnK
xt1Il2HgxOBvbhOT+9in1BzA+YJ99UzC85O0Qz06A+CmtHEy4aZ2kj5hHjECgYEA
mNS4+A8Fkss8Js1RieK2LniBxMgmYml3pfVLKGnzmng7H2+cwPLhPIzIuwytXywh
2bzbsYEfYx3EoEVgMEpPhoarQnYPukrJO4gwE2o5Te6T5mJSZGlQJQj9q4ZB2Dfz
et6INsK0oG8XVGXSpQvQh3RUYekCZQkBBFcpqWpbIEsCgYAnM3DQf3FJoSnXaMhr
VBIovic5l0xFkEHskAjFTevO86Fsz1C2aSeRKSqGFoOQ0tmJzBEs1R6KqnHInicD
TQrKhArgLXX4v3CddjfTRJkFWDbE/CkvKZNOrcf1nhaGCPspRJj2KUkj1Fhl9Cnc
dn/RsYEONbwQSjIfMPkvxF+8HQ==
-----END PRIVATE KEY-----"""


@pytest.mark.django_db
def test_determine_repo_for_upload_github_actions(codecov_vcr):
    # This test recorded a VCR cassette while making a request to
    # https://token.actions.githubusercontent.com/.well-known/jwks
    #
    # I modified this request to include the modulus and exponent corresponding
    # to the random keypair I generated above.
    #
    # I did this offline so as not to need an additional dependency - here's the code
    # if we ever need to regenerate these:
    #
    # from Crypto.PublicKey import RSA
    # import base64
    # pub = RSA.importKey(public_key)
    # modulus = base64.b64encode(pub.n.to_bytes(256, "big")).decode("ascii")
    # exponent = base64.b64encode(pub.e.to_bytes(3, "big")).decode("ascii")

    repository = RepositoryFactory.create()
    token = jwt.encode(
        {
            "iss": "https://token.actions.githubusercontent.com/abcdefg",
            "aud": [f"{settings.CODECOV_API_URL}"],
            "repository": f"{repository.author.username}/{repository.name}",
            "repository_owner": repository.author.username,
        },
        private_key,
        algorithm="RS256",
        headers={
            "kid": "78167F727DEC5D801DD1C8784C704A1C880EC0E1"
        },  # from the JWKS response
    )
    assert (
        determine_repo_for_upload({"token": token, "service": "github-actions"})
        == repository
    )
