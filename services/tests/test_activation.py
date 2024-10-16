import pytest
from shared.django_apps.core.tests.factories import OwnerFactory

from services.activation import _get_activator


@pytest.mark.django_db
def test_get_activator():
    org = OwnerFactory()
    owner = OwnerFactory()
    org.plan_activated_users = [owner.pk]
    activator = _get_activator(org, owner)

    assert activator.org == org
    assert activator.owner == owner
    assert activator.is_autoactivation_enabled() == True
    assert activator.can_activate_user() == False
    assert activator.is_activated() == True


@pytest.mark.django_db
def test_get_activator_no_activated_users():
    org = OwnerFactory()
    org.plan_activated_users = None
    owner = OwnerFactory()
    activator = _get_activator(org, owner)

    assert activator.org == org
    assert activator.owner == owner
    assert activator.is_autoactivation_enabled() == True
    assert activator.can_activate_user() == True
    assert activator.is_activated() == False
