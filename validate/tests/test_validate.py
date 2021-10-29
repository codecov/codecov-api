from json import dumps
from unittest.mock import patch

from django.conf import settings
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from yaml import YAMLError


class TestValidateYamlHandler(APITestCase):

    # Wrap get and post client calls

    def _get(self):
        return self.client.get(reverse("validate-yaml"))

    def _post(self, data=None):
        return self.client.post(reverse("validate-yaml"), data=data, format="json")

    # Unit tests

    def test_get(self):
        response = self._get()

        assert response.status_code == status.HTTP_200_OK

        expected_result = f"Usage:\n\ncurl -X POST --data-binary @codecov.yml {settings.CODECOV_URL}/validate\n"
        assert response.content.decode() == expected_result

    def test_post_no_data(self):
        response = self._post()
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        expected_result = "No content posted."
        assert response.content.decode() == expected_result

    @patch("validate.views.safe_load")
    def test_post_malformed_yaml(self, mock_safe_load):
        mock_safe_load.side_effect = YAMLError("Can't parse YAML")

        response = self._post(data="malformed yaml")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        expected_result = "Can't parse YAML\n"
        assert response.content.decode() == expected_result

    def test_post_valid_yaml(self):
        yaml = {
            "ignore": ["Pods/.*",],
            "coverage": {
                "round": "down",
                "precision": 2,
                "range": [70.0, 100.0],
                "status": {"project": {"default": {"base": "auto",}}},
                "notify": {
                    "slack": {
                        "default": {
                            "url": "secret:c/nCgqn5v1HY5VFIs9i4W3UY6eleB2rTBdBKK/ilhPR7Ch4N0FE1aO6SRfAxp3Zlm4tLNusaPY7ettH6dTYj/YhiRohxiNqJMJ4L9YQmESo="
                        }
                    }
                },
            },
        }
        response = self._post(data=yaml)

        assert response.status_code == status.HTTP_200_OK
        expected_result = f"Valid!\n\n{dumps(yaml, indent=2)}\n"
        assert response.content.decode() == expected_result

    def test_post_invalid_yaml(self):
        yaml = {
            "ignore": ["Pods/.*",],
            "coverage": {
                "round": "down",
                "precision": 2,
                "range": [70.0, 100.0],
                "status": {"project": {"default": {"base": "auto",}}, "patch": "nope",},
            },
        }

        response = self._post(data=yaml)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        expected_result = "Error at ['coverage', 'status', 'patch']: \nmust be of ['dict', 'boolean'] type\n"
        assert response.content.decode() == expected_result

    def test_request_body_not_parsable_as_dict(self):
        # String
        response = self._post(data="codecov.yml")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        expected_result = "No file posted."
        assert response.content.decode() == expected_result

        # Number
        response = self._post(data=123)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        expected_result = "No file posted."
        assert response.content.decode() == expected_result
