import json

from shared.django_apps.codecov_metrics.service.codecov_metrics import (
    UserOnboardingMetricsService,
)

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner


class StoreCodecovMetricInteractor(BaseInteractor):
    def validate(self) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, org_username: str, event: str, json_string: str) -> None:
        self.validate()
        current_org = Owner.objects.filter(
            username=org_username, service=self.service
        ).first()
        if not current_org:
            raise ValidationError("Cannot find owner record in the database")

        try:
            payload = json.loads(json_string)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON string")

        UserOnboardingMetricsService.create_user_onboarding_metric(
            org_id=current_org.pk,
            event=event,
            payload=payload,
        )
