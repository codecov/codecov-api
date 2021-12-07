import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from codecov_auth.helpers import (
    create_signed_value,
    current_user_part_of_org,
    decode_token_from_cookie,
    do_create_signed_value_v2,
)

from ..factories import OwnerFactory


def test_do_create_signed_value_v2():
    secret, name, value = "aaaaa", "name", "value"
    res = do_create_signed_value_v2(secret, name, value, clock=lambda: 12345678)
    assert decode_token_from_cookie(secret, res) == value
    assert (
        res
        == "2|1:0|8:12345678|4:name|8:dmFsdWU=|82ce7704ffb19faa13b0bd84f4f84fb4e17662c89eaf47a58683855305fa47f9"
    )


def test_create_signed_value():
    name, value = "name", "value"
    res = create_signed_value(name, value)
    assert len(res.split("|")) == 6
    (
        res_version,
        res_key_version,
        res_time,
        res_name,
        res_value,
        res_signature,
    ) = res.split("|")
    assert res_version == "2"
    assert res_key_version == "1:0"
    assert res_name == "4:name"
    assert res_value == "8:dmFsdWU="
    assert decode_token_from_cookie(settings.COOKIE_SECRET, res) == value


def test_create_signed_value_wrong_version():
    name, value = "name", "value"
    with pytest.raises(Exception) as exc:
        create_signed_value(name, value, version=4)
    assert exc.value.args == ("Unsupported version of signed cookie",)


def test_do_create_signed_value_v2_token_value():
    expected_result = "2|1:0|10:1557329312|15:bitbucket-token|48:OGY5YmM2Y2ItZmQxNC00M2JjLWJiYjUtYmUxZTdjOTQ4ZjM0|459669157b19d2e220f461e02c07c377a455bc532ad0c2b8b69b2648cfbe3914"
    value = "8f9bc6cb-fd14-43bc-bbb5-be1e7c948f34"
    secret, name = "abc123", "bitbucket-token"
    res = do_create_signed_value_v2(secret, name, value, clock=lambda: 1557329312)
    assert decode_token_from_cookie(secret, res) == value
    assert res == expected_result


@pytest.mark.django_db
def test_current_user_part_of_org_when_user_not_authenticated():
    org = OwnerFactory()
    current_user = AnonymousUser()
    assert current_user_part_of_org(current_user, org) is False


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
