from shared.plan.service import PlanService

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthorized, ValidationError
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner


class StartTrialInteractor(BaseInteractor):
    def validate(self, current_org: Owner | None):
        if not current_org:
            raise ValidationError("Cannot find owner record in the database")
        if not current_user_part_of_org(self.current_owner, current_org):
            raise Unauthorized()

    def _start_trial(self, current_org: Owner) -> None:
        plan_service = PlanService(current_org=current_org)
        plan_service.start_trial(current_owner=self.current_owner)
        return

    @sync_to_async
    def execute(self, org_username: str) -> None:
        current_org = Owner.objects.filter(
            username=org_username, service=self.service
        ).first()
        self.validate(current_org=current_org)
        self._start_trial(current_org=current_org)
        return
