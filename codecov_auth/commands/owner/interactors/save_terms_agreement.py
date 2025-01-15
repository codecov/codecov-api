from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from services.analytics import AnalyticsService


@dataclass
class TermsAgreementInput:
    business_email: str
    name: str
    terms_agreement: bool = False
    marketing_consent: bool = False


class SaveTermsAgreementInteractor(BaseInteractor):
    requires_service = False

    def validate(self, input: TermsAgreementInput) -> None:
        if not input.business_email:
            raise ValidationError("Email is required")
        if not input.name:
            raise ValidationError("Name is required")
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def update_terms_agreement(self, input: TermsAgreementInput) -> None:
        self.current_user.terms_agreement = input.terms_agreement
        self.current_user.terms_agreement_at = timezone.now()
        self.current_user.email_opt_in = input.marketing_consent
        self.current_user.name = input.name
        self.current_user.save()

        if input.business_email and input.business_email != "":
            self.current_user.email = input.business_email
            self.current_user.save()

        if input.marketing_consent:
            self.send_data_to_marketo()

    def send_data_to_marketo(self) -> None:
        event_data = {
            "email": self.current_user.email,
        }
        AnalyticsService().opt_in_email(self.current_user.id, event_data)

    @sync_to_async
    def execute(self, input: Any) -> None:
        typed_input = TermsAgreementInput(
            business_email=input.get("business_email", ""),
            terms_agreement=input.get("terms_agreement", False),
            marketing_consent=input.get("marketing_consent", False),
            name=input.get("name", ""),
        )
        self.validate(typed_input)
        return self.update_terms_agreement(typed_input)
