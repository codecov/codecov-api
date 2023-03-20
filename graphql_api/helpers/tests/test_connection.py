from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from core.models import Repository
from core.tests.factories import RepositoryFactory
from graphql_api.types.enums import OrderingDirection, RepositoryOrdering


class RepositoryQuerySetTests(TransactionTestCase):
    def test_queryset_to_connection_deterministic_ordering(self):
        from graphql_api.helpers.connection import queryset_to_connection

        repo_1 = RepositoryFactory(name="c")
        repo_2 = RepositoryFactory(name="b")
        repo_3 = RepositoryFactory(name="b")
        repo_4 = RepositoryFactory(name="b")
        repo_5 = RepositoryFactory(name="a")

        connection = async_to_sync(queryset_to_connection)(
            Repository.objects.all(),
            ordering=(RepositoryOrdering.NAME.value, RepositoryOrdering.ID.value),
            ordering_direction=OrderingDirection.ASC,
        )
        repos = [edge["node"] for edge in connection.edges]

        self.assertEqual(repos, [repo_5, repo_2, repo_3, repo_4, repo_1])

        connection = async_to_sync(queryset_to_connection)(
            Repository.objects.all(),
            ordering=(RepositoryOrdering.NAME.value, RepositoryOrdering.ID.value),
            ordering_direction=OrderingDirection.DESC,
        )
        repos = [edge["node"] for edge in connection.edges]

        self.assertEqual(repos, [repo_1, repo_4, repo_3, repo_2, repo_5])

    def test_queryset_to_connection_accepts_enum_for_ordering(self):
        from graphql_api.helpers.connection import queryset_to_connection

        repo_1 = RepositoryFactory(name="a")
        repo_2 = RepositoryFactory(name="b")
        repo_3 = RepositoryFactory(name="c")

        connection = async_to_sync(queryset_to_connection)(
            Repository.objects.all(),
            ordering=(RepositoryOrdering.NAME,),
            ordering_direction=OrderingDirection.ASC,
        )
        repos = [edge["node"] for edge in connection.edges]

        self.assertEqual(repos, [repo_1, repo_2, repo_3])

    def test_queryset_to_connection_defers_count(self):
        from graphql_api.helpers.connection import queryset_to_connection

        RepositoryFactory(name="a")
        RepositoryFactory(name="b")
        RepositoryFactory(name="c")

        connection = async_to_sync(queryset_to_connection)(
            Repository.objects.all(),
            ordering=(RepositoryOrdering.NAME,),
            ordering_direction=OrderingDirection.ASC,
        )

        count = async_to_sync(connection.total_count)()
        assert count == 3
