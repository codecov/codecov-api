from json import loads

from django.test import TestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from codecov_auth.models import Service, User


class OwnerAutocompleteSearchTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(name="staff", is_staff=True)
        self.unauthorized_user = User.objects.create(name="nonstaff", is_staff=False)
        OwnerFactory(service=Service.GITHUB, service_id=1, username="user1")
        OwnerFactory(service=Service.GITLAB, service_id=2, username="user2")
        OwnerFactory(service=Service.GITHUB, service_id=3, username="user3")

    def test_unauthorized_access(self):
        self.client.force_login(self.unauthorized_user)
        response = self.client.get("/admin-owner-autocomplete/", {"q": "github/user1"})
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["results"]), 0)

    def test_search_by_two_terms(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-owner-autocomplete/", {"q": "github/user1"})
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["results"]), 1)

    def test_search_by_one_term_service(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-owner-autocomplete/", {"q": "github"})
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 2)

    def test_search_by_one_term_owner(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-owner-autocomplete/", {"q": "user1"})
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 1)


class RepositoryAutocompleteSearchTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(name="staff", is_staff=True)
        self.unauthorized_user = User.objects.create(name="nonstaff", is_staff=False)

        a = OwnerFactory(service=Service.GITHUB, service_id=4, username="user1")
        b = OwnerFactory(service=Service.GITHUB, service_id=5, username="user3")
        c = OwnerFactory(service=Service.GITLAB, service_id=6, username="user2")

        RepositoryFactory(author=a, name="repo1")
        RepositoryFactory(author=a, name="repo2")
        RepositoryFactory(author=b, name="repo3")
        RepositoryFactory(author=c, name="repo4")

    def test_unauthorized_access(self):
        self.client.force_login(self.unauthorized_user)
        response = self.client.get(
            "/admin-repository-autocomplete/", {"q": Service.GITHUB}
        )
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["results"]), 0)

    def test_search_by_three_terms(self):
        self.client.force_login(self.user)
        response = self.client.get(
            "/admin-repository-autocomplete/", {"q": "github/user1/repo"}
        )
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 2)

    def test_search_by_three_terms_invalid_service(self):
        self.client.force_login(self.user)
        response = self.client.get(
            "/admin-repository-autocomplete/", {"q": "geehub/user1/repo"}
        )
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 0)

    def test_search_by_two_terms_service(self):
        self.client.force_login(self.user)
        response = self.client.get(
            "/admin-repository-autocomplete/", {"q": "github/user1"}
        )
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 2)

    def test_search_by_two_terms_owner(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-repository-autocomplete/", {"q": "user2/re"})
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 1)

    def test_search_by_one_term_repo(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-repository-autocomplete/", {"q": "repo4"})
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 1)

    def test_search_by_one_term_service(self):
        self.client.force_login(self.user)
        response = self.client.get("/admin-repository-autocomplete/", {"q": "github"})
        json_string = response._container[0].decode("utf-8")
        data = loads(json_string)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(data["results"]) == 3)
