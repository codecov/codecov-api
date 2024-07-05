from dataclasses import dataclass
from typing import Optional

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Account, OktaSettings, Owner


@dataclass
class SaveOktaConfigInput:
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    url: Optional[str] = None
    enabled: bool = False
    enforced: bool = False
    org_username: str = None

class SaveOktaConfigInteractor(BaseInteractor):
    def validate(self, owner: Owner):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not owner:
            raise ValidationError("Cannot find owner record in the database")
        if not owner.is_admin(self.current_owner):
            raise Unauthorized()

    @sync_to_async
    def execute(self, input: dict):
        typed_input = SaveOktaConfigInput(
            client_id=input.get("client_id"),
            client_secret=input.get("client_secret"),
            url=input.get("url"),
            enabled=input.get("enabled"),
            enforced=input.get("enforced"),
            org_username=input.get("org_username"),
        )

        owner = Owner.objects.filter(
            username=typed_input.org_username, service=self.service
        ).first()
        self.validate(owner=owner)

        account_id = owner.account_id
        if not account_id:
            account = Account.objects.create()
            account_id = account.id
            owner.account_id = account_id
            owner.save()

        okta_config, created = OktaSettings.objects.get_or_create(account_id=account_id)

        for field in ["client_id", "client_secret", "url", "enabled", "enforced"]:
            value = getattr(typed_input, field)
            if value is not None:
                setattr(okta_config, field, value)

        okta_config.save()
