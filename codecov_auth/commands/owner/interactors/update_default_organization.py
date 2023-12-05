from typing import Optional

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner, OwnerProfile
from services.activation import try_auto_activate


class UpdateDefaultOrganizationInteractor(BaseInteractor):
    def validate(
        self,
        default_org: Optional[Owner],
    ) -> Optional[Owner]:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        if default_org is None:
            return

        if (
            default_org.ownerid not in self.current_owner.organizations
            and default_org.ownerid != self.current_owner.ownerid
        ):
            raise ValidationError(
                "Organization does not belong in current user's organization list"
            )

    def update_default_organization(self, default_org: Optional[Owner]):
        owner_profile, _ = OwnerProfile.objects.get_or_create(
            owner_id=self.current_owner.ownerid
        )
        owner_profile.default_org = default_org
        saved_owner_profile = owner_profile.save()
        if default_org:
            try_auto_activate(default_org, owner_profile.owner)
        return saved_owner_profile

    @sync_to_async
    def execute(self, default_org_username: str):
        default_org = None
        if default_org_username is not None:
            default_org = Owner.objects.filter(
                username=default_org_username, service=self.service
            ).first()
        self.validate(default_org)
        self.update_default_organization(default_org)
        return default_org_username
