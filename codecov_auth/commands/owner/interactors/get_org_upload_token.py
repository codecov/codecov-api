from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov_auth.models import OrganizationLevelToken


class GetOrgUploadToken(BaseInteractor):
    @sync_to_async
    def execute(self, owner):
        org_token = OrganizationLevelToken.objects.filter(owner=owner).first()
        if org_token:
            return org_token.token
