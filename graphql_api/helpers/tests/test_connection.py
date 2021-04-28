from asgiref.sync import async_to_sync
from django.test import TestCase

from core.models import Repository
from core.tests.factories import RepositoryFactory

from graphql_api.types.enums import RepositoryOrdering, OrderingDirection


class RepositoryQuerySetTests(TestCase):
    def test_queryset_to_connection_deterministic_ordering(self):
        from graphql_api.helpers.connection import queryset_to_connection

        repo_1 = RepositoryFactory(name="c")
        repo_2 = RepositoryFactory(name="b")
        repo_3 = RepositoryFactory(name="b")
        repo_4 = RepositoryFactory(name="b")
        repo_5 = RepositoryFactory(name="a")

        connections = async_to_sync(queryset_to_connection)(
            Repository.objects.all(),
            ordering=RepositoryOrdering.NAME.value,
            ordering_direction=OrderingDirection.ASC,
        )
        repos = [edge["node"] for edge in connections["edges"]]

        self.assertEqual(repos, [repo_5, repo_2, repo_3, repo_4, repo_1])

        connections = async_to_sync(queryset_to_connection)(
            Repository.objects.all(),
            ordering=RepositoryOrdering.NAME.value,
            ordering_direction=OrderingDirection.DESC,
        )
        repos = [edge["node"] for edge in connections["edges"]]

        self.assertEqual(repos, [repo_1, repo_4, repo_3, repo_2, repo_5])

    def test_queryset_to_connection_accepts_enum_for_ordering(self):
        from graphql_api.helpers.connection import queryset_to_connection

        repo_1 = RepositoryFactory(name="a")
        repo_2 = RepositoryFactory(name="b")
        repo_3 = RepositoryFactory(name="c")

        connections = async_to_sync(queryset_to_connection)(
            Repository.objects.all(),
            ordering=RepositoryOrdering.NAME,
            ordering_direction=OrderingDirection.ASC,
        )
        repos = [edge["node"] for edge in connections["edges"]]

        self.assertEqual(repos, [repo_1, repo_2, repo_3])
