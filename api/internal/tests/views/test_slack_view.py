from django.test import override_settings
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.internal.slack.views import GenerateAccessTokenView
from codecov_auth.models import Owner, UserToken

codecov_internal_token = "17603a9e-0463-45e1-883e-d649fccf4ae8"


class SlackViewSetTests(APITestCase):
    def setUp(self):
        self.owner = Owner.objects.create(
            username="test", service="github", name="test"
        )
        self.view = GenerateAccessTokenView.as_view()

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
            HTTP_USERNAME="test",
            HTTP_SERVICE="github",
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
            HTTP_USERNAME="invalid",
            HTTP_SERVICE="github",
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
            HTTP_USERNAME="test",
            HTTP_SERVICE="invalid",
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
            HTTP_USERNAME="test",
            HTTP_SERVICE="github",
            HTTP_AUTHORIZATION=f"Bearer {codecov_internal_token}",
        )
        assert response.status_code == 200
        assert response.data["token"] == self.owner.user_tokens.first().token

    @override_settings(CODECOV_INTERNAL_TOKEN=codecov_internal_token)
    def test_generate_access_token_success(self):
        response = self.client.post(
            reverse(
                "generate-token",
            ),
            HTTP_USERNAME="test",
            HTTP_SERVICE="github",
            HTTP_AUTHORIZATION=f"Bearer {codecov_internal_token}",
        )
        assert response.status_code == 200
        assert response.data["token"] == self.owner.user_tokens.first().token
