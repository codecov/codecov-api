from django.test import override_settings
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov_auth.models import UserToken

codecov_internal_token = "test3n4d079myhiy9fu7d3j7gsepz80df3da"


class SlackViewSetTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory()
        self.data = {"username": self.owner.username, "service": self.owner.service}

    def test_generate_access_token_missing_headers(self):
        response = self.client.post(
            reverse(
                "generate-token",
            )
        )

        assert response.status_code == 401
        assert response.data == {
            "detail": "Authentication credentials were not provided."
        }

    def test_generate_access_token_with_invalid_token(self):
        response = self.client.post(
            reverse(
                "generate-token",
            ),
            data=self.data,
            HTTP_AUTHORIZATION=f"Bearer {codecov_internal_token}",
        )
        assert response.status_code == 401
        assert response.data == {"detail": "Invalid token."}

    @override_settings(CODECOV_INTERNAL_TOKEN=codecov_internal_token)
    def test_generate_access_token_with_invalid_owner(self):
        response = self.client.post(
            reverse(
                "generate-token",
            ),
            HTTP_AUTHORIZATION=f"Bearer {codecov_internal_token}",
            data={
                "username": "random-owner",
                "service": self.owner.service,
            },
        )

        assert response.status_code == 404
        assert response.data == {"detail": "Owner not found"}

    @override_settings(CODECOV_INTERNAL_TOKEN=codecov_internal_token)
    def test_generate_access_token_with_invalid_service(self):
        response = self.client.post(
            reverse(
                "generate-token",
            ),
            HTTP_AUTHORIZATION=f"Bearer {codecov_internal_token}",
            data={
                "username": self.owner.username,
                "service": "random-service",
            },
        )

        assert response.status_code == 400

    @override_settings(CODECOV_INTERNAL_TOKEN=codecov_internal_token)
    def test_generate_access_token_already_exists(self):
        UserToken.objects.create(
            name="slack-codecov-access-token",
            owner=self.owner,
            token_type=UserToken.TokenType.API.value,
        )
        response = self.client.post(
            reverse(
                "generate-token",
            ),
            HTTP_AUTHORIZATION=f"Bearer {codecov_internal_token}",
            data=self.data,
        )

        assert response.status_code == 200
        assert response.data["token"] == self.owner.user_tokens.first().token

    @override_settings(CODECOV_INTERNAL_TOKEN=codecov_internal_token)
    def test_generate_access_token_success(self):
        response = self.client.post(
            reverse(
                "generate-token",
            ),
            data=self.data,
            HTTP_AUTHORIZATION=f"Bearer {codecov_internal_token}",
        )

        assert response.status_code == 200
        assert response.data["token"] == self.owner.user_tokens.first().token
