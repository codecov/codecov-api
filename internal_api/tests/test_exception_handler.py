import json

from unittest.mock import patch

from django.test import TestCase
from django.http import HttpResponse

from internal_api.exception_handler import codecov_exception_handler


class TestCodecovExceptionHandler(TestCase):
    @patch('rest_framework.views.exception_handler')
    def test_returns_http_response_with_500_if_drf_exception_handler_returns_none(self, mock_exception_handler):
        mock_exception_handler.return_value = None

        response = codecov_exception_handler(None, None)

        assert isinstance(response, HttpResponse)
        assert json.loads(response.content)['detail'] == "Server Error"
        assert response.status_code == 500
