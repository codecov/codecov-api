from shared.plan.service import PlanService

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner


class CancelTrialInteractor(BaseInteractor):
    def validate(self, owner: Owner | None):
        if not owner:
            raise ValidationError("Cannot find owner record in the database")
        if not current_user_part_of_org(self.current_owner, owner):
            raise Unauthorized()

    def _cancel_trial(self, owner: Owner):
        plan_service = PlanService(current_org=owner)
        plan_service.cancel_trial()
        return

    @sync_to_async
    def execute(self, org_username: str) -> None:
        owner = Owner.objects.filter(
            username=org_username, service=self.service
        ).first()
        self.validate(owner=owner)
        self._cancel_trial(owner=owner)
        return
