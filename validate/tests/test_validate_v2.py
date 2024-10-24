from unittest.mock import patch

from django.test import Client, TestCase
from rest_framework.reverse import reverse


@patch("validate.views.API_VALIDATE_V2_COUNTER.labels")
class TestValidateYamlV2Handler(TestCase):
    def _post(self, data, query_source=""):
        client = Client()
        if query_source:
            query_source = f"?source={query_source}"
        return client.post(
            reverse("validate-yaml-v2") + query_source,
            data=data,
            content_type="text/plain",
        )

    def test_no_data(self, mock_metrics):
        res = self._post("")
        assert res.status_code == 400
        assert res.json() == {"valid": False, "message": "YAML is empty"}
        mock_metrics.assert_called_once_with(**{"source": "unknown"})

    def test_list_type(self, mock_metrics):
        res = self._post("- testing: 123")
        assert res.status_code == 400
        assert res.json() == {
            "valid": False,
            "message": "YAML must be a dictionary type",
        }
        mock_metrics.assert_called_once_with(**{"source": "unknown"})

    def test_parse_error(self, mock_metrics):
        res = self._post("foo: - 123")
        assert res.status_code == 400
        assert res.json() == {
            "valid": False,
            "message": "YAML could not be parsed",
            "parse_error": {
                "line": 1,
                "column": 6,
                "problem": "sequence entries are not allowed here",
            },
        }
        mock_metrics.assert_called_once_with(**{"source": "unknown"})

    def test_parse_invalid(self, mock_metrics):
        res = self._post("comment: 123")
        assert res.status_code == 400
        assert res.json() == {
            "valid": False,
            "message": "YAML does not match the accepted schema",
            "validation_error": {"comment": ["must be of ['dict', 'boolean'] type"]},
        }
        mock_metrics.assert_called_once_with(**{"source": "unknown"})

    def test_parse_valid(self, mock_metrics):
        res = self._post("comment: true")
        assert res.status_code == 200
        assert res.json() == {
            "valid": True,
            "message": "YAML is valid",
            "validated_yaml": {
                "comment": True,
            },
        }
        mock_metrics.assert_called_once_with(**{"source": "unknown"})

    def test_query_source_metric(self, mock_metrics):
        self._post("comment: true", query_source="vscode")
        mock_metrics.assert_called()
        mock_metrics.assert_called_with(**{"source": "vscode"})
