import json

import pytest
from django.urls import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.django_apps.rollouts.models import (
    FeatureFlag,
    FeatureFlagVariant,
    RolloutUniverse,
)

from utils.test_utils import Client


class FeatureEndpointTests(APITestCase):
    def setUp(self):
        self.client = Client()
        self.owner = OwnerFactory(plan="users-free", plan_user_count=5)
        self.client.force_login_owner(self.owner)

    def send_feature_request(self, data: dict):
        return self.client.post(
            reverse("features"), data=json.dumps(data), content_type="application/json"
        )

    def test_invalid_request_body(self):
        data = {
            "feature_flagsssss": ["fjdsioj"],
            "identifier_dataa": {
                "email": "dsfio",
                "user_id": 1,
                "org_id": 2,
                "repo_id": 3,
            },
        }

        res = self.send_feature_request(data)
        self.assertEqual(res.status_code, 400)

    def test_valid_request_body(self):
        data = {
            "feature_flags": [],
            "identifier_data": {
                "email": "daniel.yu@sentry.io",
                "user_id": 0,
                "org_id": 0,
                "repo_id": 0,
            },
        }

        res = self.send_feature_request(data)
        self.assertEqual(res.status_code, 200)

    def test_variant_assigned_true(self):
        feature_a = FeatureFlag.objects.create(
            name="feature_a", proportion=1.0, salt="random_salt"
        )
        FeatureFlagVariant.objects.create(
            name="enabled",
            feature_flag=feature_a,
            proportion=1.0,
            value=True,
        )

        feature_b = FeatureFlag.objects.create(
            name="feature_b", proportion=1.0, salt="random_salt"
        )
        FeatureFlagVariant.objects.create(
            name="enabled",
            feature_flag=feature_b,
            proportion=1.0,
            value=True,
        )

        data = {
            "feature_flags": ["feature_a", "feature_b"],
            "identifier_data": {
                "email": "d",
                "user_id": 1,
                "org_id": 1,
                "repo_id": 1,
            },
        }

        res = self.send_feature_request(data)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["feature_a"], True)
        self.assertEqual(res.data["feature_b"], True)

    def test_variant_assigned_false(self):
        feature_aaa = FeatureFlag.objects.create(
            name="feature_aaa", proportion=1.0, salt="random_salt"
        )
        FeatureFlagVariant.objects.create(
            name="disabled",
            feature_flag=feature_aaa,
            proportion=1.0,
            value=False,
        )

        feature_bbb = FeatureFlag.objects.create(
            name="feature_bbb", proportion=1.0, salt="random_salt"
        )
        FeatureFlagVariant.objects.create(
            name="disabled",
            feature_flag=feature_bbb,
            proportion=1.0,
            value=False,
        )

        data = {
            "feature_flags": ["feature_aaa", "feature_bbb"],
            "identifier_data": {
                "email": "d",
                "user_id": 1,
                "org_id": 1,
                "repo_id": 1,
            },
        }

        res = self.send_feature_request(data)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["feature_aaa"], False)
        self.assertEqual(res.data["feature_bbb"], False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rollout_universe,o_emails,o_owner_ids,o_repo_ids,o_org_ids,o_values",
    [
        (
            RolloutUniverse.EMAIL,
            (["david@gmail.com"], ["daniel@gmail.com"]),
            ([], []),
            ([], []),
            ([], []),
            (1, 2),
        ),
        (
            RolloutUniverse.OWNER_ID,
            ([], []),
            (["1"], ["2"]),
            ([], []),
            ([], []),
            (3, 4),
        ),
        (
            RolloutUniverse.REPO_ID,
            ([], []),
            ([], []),
            (["21"], ["31"]),
            ([], []),
            (5, 6),
        ),
        (
            RolloutUniverse.ORG_ID,
            ([], []),
            ([], []),
            ([], []),
            (["11"], ["21"]),
            (7, 8),
        ),
    ],
)
def test_overrides_by_email(
    rollout_universe, o_emails, o_owner_ids, o_repo_ids, o_org_ids, o_values
):
    overrides = FeatureFlag.objects.create(
        name="overrides_" + str(rollout_universe),
        proportion=1.0,
        rollout_universe=rollout_universe,
    )
    FeatureFlagVariant.objects.create(
        name="overrides_a",
        feature_flag=overrides,
        proportion=1 / 3,
        value=o_values[0],
        override_emails=o_emails[0],
        override_owner_ids=o_owner_ids[0],
        override_repo_ids=o_repo_ids[0],
        override_org_ids=o_org_ids[0],
    )
    FeatureFlagVariant.objects.create(
        name="overrides_b",
        feature_flag=overrides,
        proportion=1 / 3,
        value=o_values[1],
        override_emails=o_emails[1],
        override_owner_ids=o_owner_ids[1],
        override_repo_ids=o_repo_ids[1],
        override_org_ids=o_org_ids[1],
    )
    FeatureFlagVariant.objects.create(
        name="overrides_c",
        feature_flag=overrides,
        proportion=1 / 3,
        value="dfjosijsdiofjdos",
    )

    data1 = {
        "feature_flags": ["overrides_" + str(rollout_universe)],
        "identifier_data": {
            "email": o_emails[0][0] if o_emails[0] else "",
            "user_id": o_owner_ids[0][0] if o_owner_ids[0] else 0,
            "org_id": o_org_ids[0][0] if o_org_ids[0] else 0,
            "repo_id": o_repo_ids[0][0] if o_repo_ids[0] else 0,
        },
    }
    mock = FeatureEndpointTests()
    mock.setUp()
    res1 = mock.send_feature_request(data1)

    data2 = {
        "feature_flags": ["overrides_" + str(rollout_universe)],
        "identifier_data": {
            "email": o_emails[1][0] if o_emails[1] else "",
            "user_id": o_owner_ids[1][0] if o_owner_ids[1] else 0,
            "org_id": o_org_ids[1][0] if o_org_ids[1] else 0,
            "repo_id": o_repo_ids[1][0] if o_repo_ids[1] else 0,
        },
    }
    res2 = mock.send_feature_request(data2)

    assert res1.status_code == 200
    assert res1.data["overrides_" + str(rollout_universe)] == o_values[0]
    assert res2.status_code == 200
    assert res2.data["overrides_" + str(rollout_universe)] == o_values[1]
