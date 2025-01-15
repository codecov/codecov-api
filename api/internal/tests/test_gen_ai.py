from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from codecov_auth.models import GithubAppInstallation
from graphql_api.types.owner.owner import AI_FEATURES_GH_APP_ID
from utils.test_utils import Client


class GenAIAuthViewTests(APITestCase):
    def setUp(self):
        self.client = Client()

        self.owner = OwnerFactory(service="github")
        self.repo1 = RepositoryFactory(author=self.owner, name="Repo1")
        self.repo2 = RepositoryFactory(author=self.owner, name="Repo2")

        self.ai_install = GithubAppInstallation.objects.create(
            app_id=AI_FEATURES_GH_APP_ID,
            owner=self.owner,
            repository_service_ids=[self.repo1.service_id, self.repo2.service_id],
        )

    def test_no_owner_id(self):
        url = reverse("gen-ai-consent")
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data["is_valid"] is False

    def test_owner_without_install(self):
        # Remove the AI installation so it doesn't exist
        self.ai_install.delete()

        url = reverse("gen-ai-consent")
        response = self.client.get(url, data={"owner_id": self.owner.id})
        assert response.status_code == 200
        assert response.data["is_valid"] is False

    def test_valid_owner_with_install(self):
        url = reverse("gen-ai-consent")
        response = self.client.get(url, data={"owner_id": self.owner.id})
        assert response.status_code == 200
        assert response.data["is_valid"] is True
        assert len(response.data["repos"]) == 2
        assert set(response.data["repos"]) == {"Repo1", "Repo2"}
