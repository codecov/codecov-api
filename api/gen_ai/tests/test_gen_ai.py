import hmac, json
from hashlib import sha256
from unittest.mock import patch

from django.urls import reverse
from django.utils.crypto import constant_time_compare
from rest_framework import status
from rest_framework.test import APITestCase

from codecov_auth.models import Owner, GithubAppInstallation
from utils.config import get_config
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

PAYLOAD_SECRET = b"testixik8qdauiab1yiffydimvi72ekq"
VIEW_URL = reverse("auth")

def sign_payload(payload, secret=PAYLOAD_SECRET):
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(secret, data, digestmod=sha256).hexdigest()
    return signature, data

class GenAIAuthViewTests(APITestCase):
    @patch("utils.config.get_config", return_value=PAYLOAD_SECRET)
    def test_missing_parameters(self, mock_config):
        payload = {}
        sig, data = sign_payload(payload)
        response = self.client.post(
            VIEW_URL,
            data=payload,
            content_type="application/json",
            HTTP_X_GEN_AI_AUTH_SIGNATURE=sig,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required parameters", response.data)

    @patch("utils.config.get_config", return_value=PAYLOAD_SECRET)
    def test_invalid_signature(self, mock_config):
        payload = {"external_owner_id": "owner1", "repo_service_id": "101"}
        # Create a wrong signature by altering the payload before signing
        wrong_sig = "sha256=" + hmac.new(PAYLOAD_SECRET, b"{}", digestmod=sha256).hexdigest()
        response = self.client.post(
            VIEW_URL,
            data=payload,
            content_type="application/json",
            HTTP_X_GEN_AI_AUTH_SIGNATURE=wrong_sig,
        )
        self.assertEqual(response.status_code, 403)

    @patch("utils.config.get_config", return_value=PAYLOAD_SECRET)
    def test_owner_not_found(self, mock_config):
        payload = {'external_owner_id': 'nonexistent_owner', 'repo_service_id': '101'}
        sig, serialized_data = sign_payload(payload)
        response = self.client.post(
            VIEW_URL,
            HTTP_X_GEN_AI_AUTH_SIGNATURE=sig,
            data=serialized_data,
            content_type="application/json",
            
        )
        self.assertEqual(response.status_code, 404)

    @patch("utils.config.get_config", return_value=PAYLOAD_SECRET)
    def test_no_installation(self, mock_config):
        _ = OwnerFactory(service="github", service_id="owner1", username="test1")
        payload = {'external_owner_id': 'owner1', 'repo_service_id': '101'}
        sig, data = sign_payload(payload)
        response = self.client.post(
            VIEW_URL,
            data=data,
            content_type="application/json",
            HTTP_X_GEN_AI_AUTH_SIGNATURE=sig,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"is_valid": False})

    @patch("utils.config.get_config", return_value=PAYLOAD_SECRET)
    def test_authorized(self, mock_config):
        owner = OwnerFactory(service="github", service_id="owner2", username="test2")
        app_install = GithubAppInstallation(
            installation_id=12345,
            owner=owner,
            name="ai-features",
            repository_service_ids=['101', '202']
        )
        app_install.save()
        payload = {"external_owner_id": "owner2", "repo_service_id": '101'}
        sig, data = sign_payload(payload)
        response = self.client.post(
            VIEW_URL,
            data=data,
            content_type="application/json",
            HTTP_X_GEN_AI_AUTH_SIGNATURE=sig,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"is_valid": True})

    @patch("utils.config.get_config", return_value=PAYLOAD_SECRET)
    def test_unauthorized(self, mock_config):
        owner = OwnerFactory(service="github", service_id="owner3", username="test3")
        # Create a GithubAppInstallation where the list does not include the requested repo_service_id.
        app_install = GithubAppInstallation.objects.create(
            installation_id=2,
            owner=owner,
            name="ai-features",
            repository_service_ids=["303", "404"]
        )
        app_install.save()
        payload = {'external_owner_id': 'owner3', 'repo_service_id': '101'}
        sig, data = sign_payload(payload)
        response = self.client.post(
            VIEW_URL,
            data=data,
            content_type="application/json",
            HTTP_X_GEN_AI_AUTH_SIGNATURE=sig,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"is_valid": False})
