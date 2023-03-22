from dataclasses import dataclass
from datetime import datetime

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from codecov_auth.models import Owner, OwnerProfile


@dataclass
class TermsAgreementInput:
    email: str
    terms_agreement: bool = False


class SaveTermsAgreementInteractor(BaseInteractor):
    def update_terms_agreement(self, input: TermsAgreementInput):
        owner_profile, _ = OwnerProfile.objects.get_or_create(
            owner=self.current_user,
        )
        owner_profile.terms_agreement = input.terms_agreement
        owner_profile.terms_agreement_at = datetime.now()
        owner_profile.save()

        if input.email is not None and input.email != "":
            self.current_user.business_email = input.email
            self.current_user.save()

    @sync_to_async
    def execute(self, input):
        typed_input = TermsAgreementInput(
            email=input.get("email"), terms_agreement=input.get("termsAgreement")
        )
        return self.update_terms_agreement(typed_input)
