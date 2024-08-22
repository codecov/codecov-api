from dataclasses import dataclass

from shared.django_apps.codecov_auth.models import AccountsUsers, User

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Account, OktaSettings, Owner


@dataclass
class SaveOktaConfigInput:
    enabled: bool | None
    enforced: bool | None
    client_id: str | None = None
    client_secret: str | None = None
    url: str | None = None
    org_username: str | None = None


class SaveOktaConfigInteractor(BaseInteractor):
    def validate(self, owner: Owner) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not owner:
            raise ValidationError("Cannot find owner record in the database")
        if not owner.is_admin(self.current_owner):
            raise Unauthorized()

    @sync_to_async
    def execute(self, input: dict) -> None:
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

        account = owner.account
        if not account:
            account = Account.objects.create(
                name=owner.username,
                plan=owner.plan,
                plan_seat_count=owner.plan_user_count,
                free_seat_count=owner.free,
                plan_auto_activate=owner.plan_auto_activate,
            )
            owner.account = account
            owner.save()

            # Update the activated users to be added to the account
            plan_activated_user_owners: list[int] = owner.plan_activated_users
            activated_connections: list[AccountsUsers] = []
            for activated_user_owner in plan_activated_user_owners:
                user_owner: Owner = Owner.objects.select_related("user").get(
                    pk=activated_user_owner
                )
                user = user_owner.user
                if user is None:
                    user = User(name=user_owner.name, email=user_owner.email)
                    user_owner.user = user
                    user.save()
                    user_owner.save()

                activated_connections.append(AccountsUsers(account=account, user=user))

                # Batch the user creation in batches of 50 users
                if len(activated_connections) > 50:
                    AccountsUsers.objects.bulk_create(activated_connections)
                    activated_connections = []

            if activated_connections:
                AccountsUsers.objects.bulk_create(activated_connections)

        okta_config, created = OktaSettings.objects.get_or_create(account=account)

        for field in ["client_id", "client_secret", "url", "enabled", "enforced"]:
            value = getattr(typed_input, field)
            if value is not None:
                # Strip the URL of any trailing spaces and slashes before saving it
                if field == "url":
                    value = value.strip("/ ")
                setattr(okta_config, field, value)

        okta_config.save()
