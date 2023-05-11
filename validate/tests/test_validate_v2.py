from django.test import Client, TestCase
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from yaml import YAMLError


class TestValidateYamlV2Handler(TestCase):
    def _post(self, data):
        client = Client()
        return client.post(
            reverse("validate-yaml-v2"), data=data, content_type="text/plain"
        )

    def test_no_data(self):
        res = self._post("")
        assert res.status_code == 400
        assert res.json() == {"valid": False, "message": "YAML is empty"}

    def test_list_type(self):
        res = self._post("- testing: 123")
        assert res.status_code == 400
        assert res.json() == {
            "valid": False,
            "message": "YAML must be a dictionary type",
        }

    def test_parse_error(self):
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

    def test_parse_invalid(self):
        res = self._post("comment: 123")
        assert res.status_code == 400
        assert res.json() == {
            "valid": False,
            "message": "YAML does not match the accepted schema",
            "validation_error": {"comment": ["must be of ['dict', 'boolean'] type"]},
        }

    def test_parse_valid(self):
        res = self._post("comment: true")
        assert res.status_code == 200
        assert res.json() == {
            "valid": True,
            "message": "YAML is valid",
            "validated_yaml": {
                "comment": True,
            },
        }
