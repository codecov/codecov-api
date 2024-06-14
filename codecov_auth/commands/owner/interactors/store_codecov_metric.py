from dataclasses import dataclass
import json

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from shared.django_apps.codecov_metrics.service.codecov_metrics import UserOnboardingMetricsService

class StoreCodecovMetricInteractor(BaseInteractor):
    def validate(self) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, event: str, json_string: str) -> None:
        self.validate()
        try:
            payload = json.loads(json_string)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON string")
        
        UserOnboardingMetricsService.create_user_onboarding_metric(
            org_id=self.current_owner.pk,
            event=event,
            payload=payload,
        )
