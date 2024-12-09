from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import RepositoryFactory

from codecov.commands.exceptions import ValidationError
from core.models import Repository
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

    def test_array_pagination_first_after(self):
        from graphql_api.helpers.connection import queryset_to_connection_sync

        data = [1, 2, 3, 4, 5]

        # Test first parameter
        connection = queryset_to_connection_sync(data, first=2)
        self.assertEqual([edge["node"] for edge in connection.edges], [1, 2])
        self.assertTrue(connection.page_info["has_next_page"])
        self.assertFalse(connection.page_info["has_previous_page"])

        # Test after parameter
        connection = queryset_to_connection_sync(data, first=2, after="1")
        self.assertEqual([edge["node"] for edge in connection.edges], [3, 4])
        self.assertTrue(connection.page_info["has_next_page"])
        self.assertTrue(connection.page_info["has_previous_page"])

    def test_array_pagination_last_before(self):
        from graphql_api.helpers.connection import queryset_to_connection_sync

        data = [1, 2, 3, 4, 5]

        # Test last parameter
        connection = queryset_to_connection_sync(data, last=2)
        self.assertEqual([edge["node"] for edge in connection.edges], [4, 5])
        self.assertFalse(connection.page_info["has_next_page"])
        self.assertTrue(connection.page_info["has_previous_page"])

        # Test before parameter
        connection = queryset_to_connection_sync(data, last=2, before="4")
        self.assertEqual([edge["node"] for edge in connection.edges], [3, 4])
        self.assertTrue(connection.page_info["has_next_page"])
        self.assertTrue(connection.page_info["has_previous_page"])

    def test_array_pagination_edge_cases(self):
        from graphql_api.helpers.connection import queryset_to_connection_sync

        data = [1, 2, 3]

        # Empty array
        connection = queryset_to_connection_sync([], first=2)
        self.assertEqual(connection.edges, [])
        self.assertEqual(connection.total_count, 0)

        # First greater than array length
        connection = queryset_to_connection_sync(data, first=5)
        self.assertEqual([edge["node"] for edge in connection.edges], [1, 2, 3])
        self.assertEqual(connection.total_count, 3)

        # Last greater than array length
        connection = queryset_to_connection_sync(data, last=5)
        self.assertEqual([edge["node"] for edge in connection.edges], [1, 2, 3])
        self.assertEqual(connection.total_count, 3)

    def test_array_pagination_edge_cases_with_before_cursor_2(self):
        from graphql_api.helpers.connection import queryset_to_connection_sync

        data = [1, 2, 3, 4, 5]

        connection = queryset_to_connection_sync(data, last=3, before="3")
        self.assertEqual([edge["node"] for edge in connection.edges], [1, 2, 3])

    def test_array_pagination_edge_cases_with_before_and_after(self):
        from graphql_api.helpers.connection import queryset_to_connection_sync

        data = [1, 2, 3, 4, 5]

        connection = queryset_to_connection_sync(data, last=3, before="3", after="0")
        self.assertEqual([edge["node"] for edge in connection.edges], [2, 3])

    def test_both_first_and_last(self):
        from graphql_api.helpers.connection import queryset_to_connection_sync

        data = [1, 2, 3, 4, 5]

        with self.assertRaises(ValidationError):
            queryset_to_connection_sync(data, last=3, first=2)

    def test_invalid_cursors(self):
        from graphql_api.helpers.connection import queryset_to_connection_sync

        data = [1, 2, 3, 4, 5]

        with self.assertRaises(ValidationError):
            queryset_to_connection_sync(data, last=3, before="invalid")

        with self.assertRaises(ValidationError):
            queryset_to_connection_sync(data, first=3, after="invalid")
