from dataclasses import dataclass

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner


@dataclass
class SetUploadTokenRequiredInput:
    upload_token_required: bool
    org_username: str


class SetUploadTokenRequiredInteractor(BaseInteractor):
    def validate(self, owner_obj, upload_token_required):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not owner_obj:
            raise ValidationError("Owner not found")
        if not current_user_part_of_org(self.current_owner, owner_obj):
            raise Unauthorized()
        if not owner_obj.is_admin(self.current_owner):
            raise Unauthorized("Admin authorization required")
        if upload_token_required is None:
            raise ValidationError("upload_token_required must be either True or False")

    @sync_to_async
    def execute(self, input: dict[str, bool]):
        typed_input = SetUploadTokenRequiredInput(
            upload_token_required=input.get("upload_token_required"),
            org_username=input.get("org_username"),
        )

        owner_obj = Owner.objects.filter(
            username=typed_input.org_username, service=self.service
        ).first()

        self.validate(owner_obj, typed_input.upload_token_required)

        owner_obj.upload_token_required_for_public_repos = bool(
            typed_input.upload_token_required
        )
        owner_obj.save()

        return
