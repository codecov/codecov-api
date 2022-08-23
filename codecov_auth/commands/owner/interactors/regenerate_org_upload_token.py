import uuid

from asgiref.sync import sync_to_async

from billing.constants import ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS
from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import OrganizationLevelToken, Owner


class RegenerateOrgUploadTokenInteractor(BaseInteractor):
    def validate(self, owner_obj):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not owner_obj:
            raise ValidationError("Owner not found")
        if not owner_obj.plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS:
            raise ValidationError(
                "Organization-wide upload tokens are only available in enterprise-cloud plans."
            )

    @sync_to_async
    def execute(self, owner):
        owner_obj = Owner.objects.filter(name=owner, service=self.service).first()

        self.validate(owner_obj)

        upload_token = OrganizationLevelToken.objects.filter(owner=owner_obj).first()

        if not upload_token:
            upload_token = OrganizationLevelToken(owner=owner_obj)
            upload_token.save()

        upload_token.token = uuid.uuid4()
        upload_token.save()
        return upload_token.token
