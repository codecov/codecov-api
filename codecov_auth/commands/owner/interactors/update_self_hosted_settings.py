from dataclasses import dataclass

from django.conf import settings

import services.self_hosted as self_hosted
from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async


@dataclass
class UpdateSelfHostedSettingsInput:
    auto_activate_members: bool = False


class UpdateSelfHostedSettingsInteractor(BaseInteractor):
    def validate(self) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        if not settings.IS_ENTERPRISE:
            raise ValidationError(
                "enable_autoactivation and disable_autoactivation are only available in self-hosted environments"
            )

    @sync_to_async
    def execute(self, input: UpdateSelfHostedSettingsInput) -> None:
        self.validate()
        typed_input = UpdateSelfHostedSettingsInput(
            auto_activate_members=input.get("should_auto_activate"),
        )

        should_auto_activate = typed_input.auto_activate_members
        if should_auto_activate:
            self_hosted.enable_autoactivation()
        else:
            self_hosted.disable_autoactivation()
