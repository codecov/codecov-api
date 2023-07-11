import uuid

from codecov_auth.helpers import current_user_part_of_org

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import OrganizationLevelToken, Owner


class RegenerateOrgUploadTokenInteractor(BaseInteractor):
    def validate(self, owner_obj):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not owner_obj:
            raise ValidationError("Owner not found")
        if not current_user_part_of_org(self.current_user, owner_obj):
            raise Unauthorized()

    @sync_to_async
    def execute(self, owner):
        owner_obj = Owner.objects.filter(name=owner, service=self.service).first()

        self.validate(owner_obj)

        upload_token, created = OrganizationLevelToken.objects.get_or_create(
            owner=owner_obj
        )
        if not created:
            upload_token.token = uuid.uuid4()
            upload_token.save()

        return upload_token.token
