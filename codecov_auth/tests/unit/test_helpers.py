import pytest

from codecov_auth.helpers import current_user_part_of_org

from ..factories import OwnerFactory


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
    assert current_user_part_of_org(current_user, current_user) is False


@pytest.mark.django_db
def test_current_user_part_of_org_when_user_doesnt_have_org():
    org = OwnerFactory()
    current_user = OwnerFactory(organizations=[org.ownerid])
    current_user.save()
    assert current_user_part_of_org(current_user, current_user) is True
