from unittest.mock import patch

import pytest
from django.contrib.admin.models import LogEntry
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory

from codecov_auth.helpers import History, current_user_part_of_org


@pytest.mark.django_db
def test_current_user_part_of_org_when_user_not_authenticated():
    org = OwnerFactory()
    assert current_user_part_of_org(None, org) is False


@pytest.mark.django_db
def test_current_user_part_of_org_when_user_is_owner():
    current_user = OwnerFactory()
    assert current_user_part_of_org(current_user, current_user) is True


@pytest.mark.django_db
def test_current_user_part_of_org_when_user_doesnt_have_org():
    org = OwnerFactory()
    current_user = OwnerFactory(organizations=None)
    current_user.save()
    assert current_user_part_of_org(current_user, org) is False


@pytest.mark.django_db
def test_current_user_part_of_org_when_user_has_org():
    org = OwnerFactory()
    current_user = OwnerFactory(organizations=[org.ownerid])
    current_user.save()
    assert current_user_part_of_org(current_user, current_user) is True


@pytest.mark.django_db
@patch("codecov_auth.helpers.format_stack")
def test_log_entry(mocked_format_stack):
    mocked_format_stack.return_value = "test"
    orig_owner = OwnerFactory()
    impersonated_owner = OwnerFactory()
    History.log(
        impersonated_owner,
        "Impersonation successful",
        orig_owner.user,
        add_traceback=True,
    )
    log_entries = LogEntry.objects.all()
    assert (
        str(log_entries.first())
        == f"Changed “{str(impersonated_owner)}” — Impersonation successful: test"
    )


@pytest.mark.django_db
@patch("codecov_auth.helpers.format_stack")
def test_log_entry_no_object(mocked_format_stack):
    mocked_format_stack.return_value = "test"
    orig_owner = OwnerFactory()
    History.log(
        None,
        "Impersonation successful",
        orig_owner.user,
        add_traceback=True,
    )
    log_entries = LogEntry.objects.all()
    assert log_entries.first() is None
