from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from plan.service import PlanService


class StartTrialInteractor(BaseInteractor):
    def validate(self, owner: Owner):
        if not owner:
            raise ValidationError("Cannot find owner record in the database")

    def _start_trial(self, owner: Owner) -> None:
        plan_service = PlanService(current_org=owner)
        plan_service.start_trial()
        return

    @sync_to_async
    def execute(self, org_username: str) -> None:
        owner = Owner.objects.filter(
            username=org_username, service=self.service
        ).first()
        self.validate(owner=owner)
        self._start_trial(owner=owner)
        return
