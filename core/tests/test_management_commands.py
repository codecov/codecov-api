import csv
import os
import tempfile
import unittest.mock as mock
from io import StringIO

import pytest
from django.core.management import call_command
from shared.config import ConfigHelper
from shared.django_apps.codecov_auth.models import Plan, Tier
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from services.redis_configuration import get_redis_connection


@pytest.mark.django_db
def test_update_gitlab_webhook_command(mocker):
    edit_webhook = mocker.patch("shared.torngit.gitlab.Gitlab.edit_webhook")

    get_config = mocker.patch("shared.config._get_config_instance")
    config_helper = ConfigHelper()
    config_helper.set_params(
        {
            "setup": {
                "webhook_url": "http://example.com",
            },
        }
    )
    get_config.return_value = config_helper

    author = OwnerFactory(service="gitlab")
    repo1 = RepositoryFactory(hookid=123, author=author, webhook_secret=None)
    repo2 = RepositoryFactory(hookid=234, author=author, webhook_secret=None)
    repo3 = RepositoryFactory(hookid=345, author=author, webhook_secret=None)

    call_command(
        "update_gitlab_webhooks",
        stdout=StringIO(),
        stderr=StringIO(),
        starting_repoid=repo2.pk,
    )

    repo1.refresh_from_db()
    assert repo1.webhook_secret is None
    repo2.refresh_from_db()
    assert repo2.webhook_secret is not None
    repo3.refresh_from_db()
    assert repo3.webhook_secret is not None

    assert edit_webhook.mock_calls == [
        mock.call(
            hookid="234",
            name=None,
            url="http://example.com/webhooks/gitlab",
            events={
                "push_events": True,
                "issues_events": False,
                "merge_requests_events": True,
                "tag_push_events": False,
                "note_events": False,
                "job_events": False,
                "build_events": True,
                "pipeline_events": True,
                "wiki_events": False,
            },
            secret=repo2.webhook_secret,
        ),
        mock.call(
            hookid="345",
            name=None,
            url="http://example.com/webhooks/gitlab",
            events={
                "push_events": True,
                "issues_events": False,
                "merge_requests_events": True,
                "tag_push_events": False,
                "note_events": False,
                "job_events": False,
                "build_events": True,
                "pipeline_events": True,
                "wiki_events": False,
            },
            secret=repo3.webhook_secret,
        ),
    ]


@pytest.mark.django_db
def test_delete_rate_limit_keys_user_id():
    redis = get_redis_connection()
    redis.set("rl-user:1", 1)
    redis.set("rl-user:2", 1, ex=5000)
    redis.set("rl-ip:1", 1)

    call_command(
        "delete_rate_limit_keys",
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert redis.get("rl-user:1") is None
    assert redis.get("rl-user:2") is not None
    assert redis.get("rl-ip:1") is not None

    # Get rid of lingering keys
    redis.delete("rl-ip:1")
    redis.delete("rl-user:2")


@pytest.mark.django_db
def test_delete_rate_limit_keys_ip_option():
    redis = get_redis_connection()
    redis.set("rl-ip:1", 1)
    redis.set("rl-ip:2", 1, ex=5000)
    redis.set("rl-user:1", 1)

    call_command(
        "delete_rate_limit_keys", stdout=StringIO(), stderr=StringIO(), ip=True
    )

    assert redis.get("rl-ip:1") is None
    assert redis.get("rl-ip:2") is not None
    assert redis.get("rl-user:1") is not None

    # Get rid of lingering keys
    redis.delete("rl-user:1")
    redis.delete("rl-ip:2")


@pytest.mark.django_db
def test_insert_data_to_db_from_csv_for_plans_and_tiers():
    with tempfile.NamedTemporaryFile(mode="w", delete=False, newline="") as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(["id", "tier_name"])
        writer.writerow([1, "Tier 1"])
        writer.writerow([2, "Tier 2"])
        csv_path = temp_csv.name

    out = StringIO()
    call_command("insert_data_to_db_from_csv", csv_path, "--model", "tiers", stdout=out)

    # Check the output
    assert "Successfully inserted all data into tiers from CSV" in out.getvalue()

    # Verify the data was inserted correctly
    assert Tier.objects.filter(tier_name="Tier 1").exists()
    assert Tier.objects.filter(tier_name="Tier 2").exists()

    # Create a temporary CSV file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, newline="") as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(
            ["name", "marketing_name", "base_unit_price", "tier_id", "is_active"]
        )
        writer.writerow(["Plan A", "Marketing A", 100, 1, "true"])
        writer.writerow(["Plan B", "Marketing B", 200, 2, "false"])
        csv_path = temp_csv.name

    out = StringIO()
    call_command("insert_data_to_db_from_csv", csv_path, "--model", "plans", stdout=out)

    # Check the output
    assert "Successfully inserted all data into plans from CSV" in out.getvalue()

    # Verify the data was inserted correctly
    assert Plan.objects.filter(name="Plan A").exists()
    assert Plan.objects.filter(name="Plan B").exists()

    # Clean up the temporary file
    os.remove(csv_path)
