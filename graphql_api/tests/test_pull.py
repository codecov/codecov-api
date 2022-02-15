from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from compare.tests.factories import CommitComparisonFactory
from core.models import Pull
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory, ReportLevelTotalsFactory

from .helper import GraphQLTestHelper, paginate_connection

query_list_pull_request = """{
    me {
        owner {
            repository(name: "test-repo-for-pull") {
                name
                pulls {
                    edges {
                        node {
                            title
                            pullId
                        }
                    }
                }
            }
        }
    }
}
"""

query_pull_request_detail = """{
    me {
        owner {
            repository(name: "test-repo-for-pull") {
                name
                pull(id: %s) {
                    title
                    state
                    pullId
                    updatestamp
                    author {
                        username
                    }
                    head {
                        totals {
                            coverage
                        }
                    }
                    comparedTo {
                        commitid
                    }
                    compareWithBase {
                        patchTotals {
                            coverage
                        }
                    }
                }
            }
        }
    }
}
"""


class TestPullRequestList(GraphQLTestHelper, TransactionTestCase):
    def fetch_list_pull_request(self):
        data = self.gql_request(query_list_pull_request, user=self.user)
        return paginate_connection(data["me"]["owner"]["repository"]["pulls"])

    def fetch_one_pull_request(self, id):
        data = self.gql_request(query_pull_request_detail % id, user=self.user)
        return data["me"]["owner"]["repository"]["pull"]

    def setUp(self):
        self.user = OwnerFactory(username="test-pull-user")
        self.repository = RepositoryFactory(
            author=self.user, active=True, private=True, name="test-repo-for-pull"
        )

    def test_fetch_list_pull_request(self):
        pull_1 = PullFactory(repository=self.repository, title="a")
        pull_2 = PullFactory(repository=self.repository, title="b")
        pulls = self.fetch_list_pull_request()
        pull_titles = [pull["title"] for pull in pulls]
        assert pull_1.title in pull_titles
        assert pull_2.title in pull_titles

    @freeze_time("2021-02-02")
    def test_when_repository_has_null_compared_to(self):
        my_pull = PullFactory(
            repository=self.repository,
            title="test-null-base",
            author=self.user,
            head=CommitFactory(
                repository=self.repository,
                author=self.user,
                commitid="5672734ij1n234918231290j12nasdfioasud0f9",
            ).commitid,
            compared_to=None,
        )
        pull = self.fetch_one_pull_request(my_pull.pullid)
        assert pull == {
            "title": "test-null-base",
            "state": "OPEN",
            "pullId": my_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": {"totals": None},
            "comparedTo": None,
            "compareWithBase": None,
        }

    @freeze_time("2021-02-02")
    def test_when_repository_has_null_author(self):
        my_pull = PullFactory(
            repository=self.repository,
            title="test-null-author",
            author=None,
            head=None,
            compared_to=None,
        )
        pull = self.fetch_one_pull_request(my_pull.pullid)
        assert pull == {
            "title": "test-null-author",
            "state": "OPEN",
            "pullId": my_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": None,
            "head": None,
            "comparedTo": None,
            "compareWithBase": None,
        }

    @freeze_time("2021-02-02")
    def test_when_repository_has_null_head(self):
        my_pull = PullFactory(
            repository=self.repository,
            title="test-null-head",
            author=self.user,
            head=None,
        )
        pull = self.fetch_one_pull_request(my_pull.pullid)
        assert pull == {
            "title": "test-null-head",
            "state": "OPEN",
            "pullId": my_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": None,
            "comparedTo": None,
            "compareWithBase": None,
        }

    @freeze_time("2021-02-02")
    def test_with_complete_pull_request(self):
        head = CommitFactory(
            repository=self.repository,
            author=self.user,
            commitid="5672734ij1n234918231290j12nasdfioasud0f9",
            totals={"c": "78.38", "diff": [0, 0, 0, 0, 0, "14"]},
        )
        report = CommitReportFactory(commit=head)
        ReportLevelTotalsFactory(report=report, coverage=78.38)
        compared_to = CommitFactory(
            repository=self.repository,
            author=self.user,
            commitid="9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s",
        )
        CommitComparisonFactory(
            base_commit=compared_to,
            compare_commit=head,
            patch_totals={"coverage": 87.39},
        )
        my_pull = PullFactory(
            repository=self.repository,
            title="test-pull-request",
            author=self.user,
            head=head.commitid,
            compared_to=compared_to.commitid,
        )
        pull = self.fetch_one_pull_request(my_pull.pullid)
        assert pull == {
            "title": "test-pull-request",
            "state": "OPEN",
            "pullId": my_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": {"totals": {"coverage": 78.38}},
            "comparedTo": {"commitid": "9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s"},
            "compareWithBase": {"patchTotals": {"coverage": 87.39}},
        }
