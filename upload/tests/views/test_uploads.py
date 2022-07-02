import re
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpRequest, QueryDict
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory


def test_uploads_get_not_allowed(client, db):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "report-id"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/report-id/uploads"
    client.force_login(OwnerFactory(plan=BASIC_PLAN_NAME))
    res = client.get(url)
    assert res.status_code == 405


def test_uploads_post_empty(client, db):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "report-id"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/report-id/uploads"
    client.force_login(OwnerFactory(plan=BASIC_PLAN_NAME))
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 404
