# from asgiref.sync import async_to_sync
# import pytest
# from django.test import TransactionTestCase
# from django.contrib.auth.models import AnonymousUser

# from codecov_auth.tests.factories import OwnerFactory
# from core.tests.factories import RepositoryFactory, CommitFactory
# from reports.tests.factories import ReportSessionFactory

# from ..fetch_pull_requests import FetchPullRequestsInteractor


# class FetchPullRequestsInteractorTest(TransactionTestCase):
#     def setUp(self):
#         self.repository_no_pull_requests = RepositoryFactory()

#     # helper to execute the interactor
#     def execute(self, user, *args):
#         service = user.service if user else "github"
#         current_user = user or AnonymousUser()
#         return FetchPullRequestsInteractor(current_user, service).execute(*args)

#     async def test_fetch_when_no_pulls(self):
#         repositories = await self.execute(None, self.repository_no_pull_requests)
#         print("repositories")
#         print(repositories)
#         assert len(repositories) is 0
