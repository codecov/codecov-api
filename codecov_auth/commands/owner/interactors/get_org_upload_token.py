from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import OrganizationLevelToken


class GetOrgUploadToken(BaseInteractor):
    def validate(self, owner):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        if not current_user_part_of_org(self.current_owner, owner):
            raise Unauthorized()

    @sync_to_async
    def execute(self, owner):
        self.validate(owner)

        org_token = OrganizationLevelToken.objects.filter(owner=owner).first()
        if org_token:
            return org_token.token
