import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import (
    NotFound,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from codecov_auth.tests.factories import OwnerFactory

from ..set_yaml_on_owner import SetYamlOnOwnerInteractor

good_yaml = """
codecov:
  require_ci_to_pass: yes
"""

good_yaml_with_quotes = """
codecov:
  bot: 'codecov'
"""

bad_yaml_not_dict = """
hey
"""

bad_yaml_wrong_keys = """
toto:
  tata: titi
"""


class SetYamlOnOwnerInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.current_user = OwnerFactory(
            organizations=[self.org.ownerid], service=self.org.service
        )
        self.random_user = OwnerFactory(service=self.org.service)

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return SetYamlOnOwnerInteractor(current_user, service).execute(*args)

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(None, self.org.username, good_yaml)

    async def test_when_not_path_of_org_raise(self):
        with pytest.raises(Unauthorized):
            await self.execute(self.random_user, self.org.username, good_yaml)

    async def test_when_owner_not_found_raise(self):
        with pytest.raises(NotFound):
            await self.execute(
                self.current_user, "thing that should not exist", good_yaml
            )

    async def test_user_is_part_of_org_and_yaml_is_good(self):
        owner_updated = await self.execute(
            self.current_user, self.org.username, good_yaml
        )
        # check the interactor returns the right owner
        assert owner_updated.ownerid == self.org.ownerid
        assert owner_updated.yaml == {"codecov": {"require_ci_to_pass": True}}

    async def test_user_is_part_of_org_and_yaml_has_quotes(self):
        owner_updated = await self.execute(
            self.current_user, self.org.username, good_yaml_with_quotes
        )
        # check the interactor returns the right owner
        assert owner_updated.ownerid == self.org.ownerid
        assert owner_updated.yaml == {"codecov": {"bot": "codecov"}}

    async def test_user_is_part_of_org_and_yaml_is_empty(self):
        owner_updated = await self.execute(self.current_user, self.org.username, "")
        assert owner_updated.yaml is None

    async def test_user_is_part_of_org_and_yaml_is_not_dict(self):
        with pytest.raises(ValidationError) as e:
            owner_updated = await self.execute(
                self.current_user, self.org.username, bad_yaml_not_dict
            )
        assert str(e.value) == "Error at []: Yaml needs to be a dict"

    async def test_user_is_part_of_org_and_yaml_is_not_codecov_valid(self):
        with pytest.raises(ValidationError) as e:
            owner_updated = await self.execute(
                self.current_user, self.org.username, bad_yaml_wrong_keys
            )
        assert str(e.value) == "Error at ['toto']: unknown field"
