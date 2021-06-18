from django.test import TestCase

from .factories import (
    ReportSessionFactory,
    RepositoryFlagFactory,
    ReportSessionFlagMembershipFactory,
)


class ReportSessionTests(TestCase):
    def test_get_download_url(self):
        storage_path = "v4/123/123.txt"
        session = ReportSessionFactory(storage_path=storage_path)
        repository = session.report.commit.repository
        assert (
            session.download_url
            == f"/api/gh/{repository.author.username}/{repository.name}/download/build?path={storage_path}"
        )

    def test_ci_url_when_no_provider(self):
        session = ReportSessionFactory(provider=None)
        assert session.ci_url is None

    def test_ci_url_when_provider_do_not_have_build_url(self):
        session = ReportSessionFactory(provider="azure_pipelines")
        assert session.ci_url is None

    def test_ci_url_when_provider_has_build_url(self):
        session = ReportSessionFactory(provider="travis", job_code="123")
        repo = session.report.commit.repository
        assert (
            session.ci_url
            == f"https://travis-ci.com/{repo.author.username}/{repo.name}/jobs/{session.job_code}"
        )

    def test_flags(self):
        session = ReportSessionFactory()
        flag_one = RepositoryFlagFactory()
        flag_two = RepositoryFlagFactory()
        # connect the flag and membership
        ReportSessionFlagMembershipFactory(flag=flag_one, report_session=session)
        ReportSessionFlagMembershipFactory(flag=flag_two, report_session=session)

        assert (
            session.flag_names.sort() == [flag_one.flag_name, flag_two.flag_name].sort()
        )
