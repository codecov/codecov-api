from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from codecov_auth.models import OrganizationLevelToken


class GetOrgUploadToken(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, owner):
        self.validate()

        org_token = OrganizationLevelToken.objects.filter(owner=owner).first()
        if org_token:
            return org_token.token
