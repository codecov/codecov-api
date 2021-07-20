from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist
from django.test import TransactionTestCase

from codecov_auth.tests.factories import SessionFactory, OwnerFactory


class LogoutViewTest(TransactionTestCase):
    def _get(self, url):
        headers = {"HTTP_TOKEN_TYPE": "github-token"}
        return self.client.get(url, content_type="application/json", **headers)

    @patch("codecov_auth.authentication.decode_token_from_cookie")
    def test_logout_when_unauthenticated(self, mock_decode_token_from_cookie):
        res = self._get("/logout/gh")
        assert res.status_code == 302

    @patch("codecov_auth.authentication.decode_token_from_cookie")
    @patch("codecov_auth.views.logout.decode_token_from_cookie")
    def test_logout_when_authenticated(
        self, mock_decode_token_from_cookie, mock_decode_token_from_cookie_2
    ):
        user = OwnerFactory()
        session = SessionFactory(owner=user)
        mock_decode_token_from_cookie.return_value = session.token
        mock_decode_token_from_cookie_2.return_value = session.token
        self.client.cookies["github-token"] = session.token

        res = self._get("/internal/profile/")
        self.assertEqual(res.status_code, 200)

        res = self._get("/logout/gh")
        assert res.url is "/"
        self.assertEqual(res.status_code, 302)
        with self.assertRaises(ObjectDoesNotExist):
            # test if session is properly deleted
            session.refresh_from_db()

        res = self._get("/internal/profile/")
        self.assertEqual(res.status_code, 401)
